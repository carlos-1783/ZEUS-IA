"""
Endpoints para el módulo de Control Horario Universal
"""
from datetime import datetime, timedelta, timezone
import re
from typing import Dict, Any, List, Optional, Tuple
import copy
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
import logging

from app.db.session import get_db
from app.core.auth import get_current_active_user
from app.core.config import settings
from app.models.user import User
from app.models.company import Company, UserCompany
from app.models.company_employee import CompanyEmployee
from app.models.time_tracking import EmployeeSchedule
from app.models.tpv_table import TPVTable
from app.models.time_tracking import TimeTrackingRecord, RecordStatus
from services.control_horario_service import HorarioBusinessProfile, CheckInMethod
from services.control_horario_singleton import control_horario_service
from services import smart_time_control_service as sm
from services.event_bus import emit_time_control_event
from services.checkin_biometric_block import BIOMETRIC_BLOCK_REASON, is_biometric_method, reject_biometric
from services.thalos_request_guard_v1 import thalos_request_guard

router = APIRouter()
logger = logging.getLogger(__name__)


def _company_ids_for_control_horario(db: Session, user: User) -> List[int]:
    rows = db.query(UserCompany.company_id).filter(UserCompany.user_id == user.id).all()
    return [r[0] for r in rows]


def _tt_scope_filter(user: User, cids: List[int]):
    """
    E1 (backlog ejecutor-produccion): TimeTrackingRecord.user_id == user.id excluia a
    cualquier segundo usuario de la misma empresa (vinculado via UserCompany) de ver o
    cerrar/pausar los fichajes registrados por otro usuario de esa empresa -> fichajes
    "huerfanos" no visibles y riesgo de sesiones activas duplicadas. Fallback a
    company_id IS NULL AND user_id == user.id para filas legado sin company_id.
    """
    if cids:
        return or_(
            TimeTrackingRecord.company_id.in_(cids),
            and_(TimeTrackingRecord.company_id.is_(None), TimeTrackingRecord.user_id == user.id),
        )
    return TimeTrackingRecord.user_id == user.id


def _normalize_phone(phone: Optional[str]) -> str:
    return re.sub(r"\D+", "", str(phone or ""))


def _requires_phone_verification(user: User) -> bool:
    tpv_profile = str(getattr(user, "tpv_business_profile", "") or "").strip().lower()
    if tpv_profile in {"bar", "restaurante", "restaurant"}:
        return True
    # Perfil del PROPIO usuario (antes: el del singleton global, que dependia de la
    # ultima empresa que hubiera hecho una peticion en este proceso).
    own = str(getattr(user, "control_horario_business_profile", "") or "").strip().lower()
    return own == HorarioBusinessProfile.RESTAURANTE.value


def _verify_employee_phone_or_raise(
    db: Session,
    *,
    user: User,
    employee_id: str,
    employee_phone: Optional[str],
) -> None:
    if not _requires_phone_verification(user):
        return
    phone = _normalize_phone(employee_phone)
    if not phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verificación requerida: indique el móvil del empleado.",
        )
    company_ids = _company_ids_for_control_horario(db, user)
    if not company_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No hay empresas asociadas al usuario para validar empleados.",
        )
    emp = (
        db.query(CompanyEmployee)
        .filter(
            CompanyEmployee.company_id.in_(company_ids),
            CompanyEmployee.is_active.is_(True),
            CompanyEmployee.employee_code == str(employee_id),
        )
        .first()
    )
    if not emp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empleado no encontrado para esta empresa.",
        )
    db_phone = _normalize_phone(emp.phone)
    if not db_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Empleado {employee_id} sin móvil registrado. Configúralo en RRHH.",
        )
    if phone != db_phone:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verificación de identidad fallida: móvil no coincide.",
        )


def _employees_roster_from_db(db: Session, user: User) -> Optional[List[Dict[str, Any]]]:
    """
    None = modo memoria (lista vacía → el front puede mostrar demo emp1/emp2).
    Lista = roster desde company_employees (empresas del usuario vía user_companies).

    - Si hay al menos un company_employee activo para esas empresas → siempre se devuelve
      lista (dueño/CEO ve nombres reales sin variable de entorno).
    - Si no hay filas: con CONTROL_HORARIO_DB_EMPLOYEES=true → []; con false → None (compat. demo).
    """
    company_ids = _company_ids_for_control_horario(db, user)
    if not company_ids:
        return None
    rows = (
        db.query(CompanyEmployee)
        .filter(
            CompanyEmployee.company_id.in_(company_ids),
            CompanyEmployee.is_active.is_(True),
        )
        .order_by(CompanyEmployee.full_name.asc())
        .all()
    )
    env_empty_roster = bool(settings.CONTROL_HORARIO_DB_EMPLOYEES)
    if not rows and not env_empty_roster:
        return None
    return [
        {
            "id": str(r.employee_code),
            "name": r.full_name,
            "role_title": r.role_title or "",
            "source": (r.source or "database"),
            # Solo si hay PIN asignado (nunca el PIN ni su hash).
            "pin_configured": bool(r.tpv_pin_hash),
        }
        for r in rows
    ]


def _merge_roster_with_status(
    roster: List[Dict[str, Any]],
    status_employees: Dict[str, Any],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in roster:
        emp_id = str(row["id"])
        st = status_employees.get(emp_id) or {}
        out.append(
            {
                **row,
                "status": st.get("status", "outside"),
                "check_in_time": st.get("check_in_time"),
            }
        )
    return out


def _today_range_utc() -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start, end


def _active_status_from_db(db: Session, user: User) -> Dict[str, Any]:
    """
    Estado en tiempo real: inside | on_break | (ausentes del mapa = fuera).
    total_active cuenta dentro + en pausa.
    """
    smart_map, total_active = sm.build_employees_smart_status(db, user)
    rid_list = [int(p["record_id"]) for p in smart_map.values() if p.get("record_id")]
    by_id: Dict[int, TimeTrackingRecord] = {}
    if rid_list:
        for row in db.query(TimeTrackingRecord).filter(TimeTrackingRecord.id.in_(rid_list)).all():
            by_id[row.id] = row
    employees: Dict[str, Any] = {}
    for eid, payload in smart_map.items():
        row = by_id.get(int(payload["record_id"])) if payload.get("record_id") else None
        method_s = ""
        if row:
            method_s = str(
                row.check_in_method.value if hasattr(row.check_in_method, "value") else row.check_in_method
            )
        employees[eid] = {
            "status": payload.get("status", "outside"),
            "check_in_time": payload.get("check_in_time"),
            "check_in_method": method_s,
            "record_id": payload.get("record_id"),
        }
    return {"success": True, "employees": employees, "total_active": total_active}


def _today_records_from_db(db: Session, user: User) -> List[Dict[str, Any]]:
    start, end = _today_range_utc()
    cids = _company_ids_for_control_horario(db, user)
    rows = (
        db.query(TimeTrackingRecord)
        .filter(
            _tt_scope_filter(user, cids),
            TimeTrackingRecord.check_in_time >= start,
            TimeTrackingRecord.check_in_time < end,
        )
        .order_by(TimeTrackingRecord.check_in_time.desc())
        .limit(100)
        .all()
    )
    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": f"in-{r.id}",
                "employee_id": str(r.employee_id),
                "type": "check-in",
                "time": r.check_in_time.isoformat() if r.check_in_time else None,
                "method": str(r.check_in_method.value if hasattr(r.check_in_method, "value") else (r.check_in_method or "code")),
            }
        )
        if r.check_out_time:
            out.append(
                {
                    "id": f"out-{r.id}",
                    "employee_id": str(r.employee_id),
                    "type": "check-out",
                    "time": r.check_out_time.isoformat(),
                    "method": str(r.check_out_method.value if hasattr(r.check_out_method, "value") else (r.check_out_method or "code")),
                }
            )
    out.sort(key=lambda x: str(x.get("time") or ""), reverse=True)
    try:
        return sm.merge_today_timeline(db, user, out)
    except Exception:
        return out


def _primary_company_id(db: Session, user: User) -> Optional[int]:
    link = (
        db.query(UserCompany)
        .filter(UserCompany.user_id == user.id)
        .order_by(UserCompany.id.asc())
        .first()
    )
    return int(link.company_id) if link else None


def _db_row_to_service_record(r: TimeTrackingRecord) -> Dict[str, Any]:
    method_val = str(r.check_in_method.value if hasattr(r.check_in_method, "value") else (r.check_in_method or "code"))
    return {
        "id": f"record_{r.employee_id}_{r.id}",
        "employee_id": str(r.employee_id),
        "user_id": r.user_id,
        "check_in_time": r.check_in_time,
        "check_in_method": method_val,
        "check_in_location": r.check_in_location or "Oficina Principal",
        "check_in_latitude": r.check_in_latitude,
        "check_in_longitude": r.check_in_longitude,
        "status": "active",
        "irregularities": r.irregularities or [],
        "irregularities_count": int(r.irregularities_count or 0),
        "is_late_check_in": bool(r.is_late_check_in),
        "synced_with_afrodita": bool(r.synced_with_afrodita),
        "synced_with_rafael": bool(r.synced_with_rafael),
        "db_record_id": r.id,
    }


def _infer_profile_from_company_context(db: Session, user: User) -> Optional[HorarioBusinessProfile]:
    """
    Inferencia defensiva para entornos donde user.control_horario_business_profile no está poblado.
    Prioriza tpv_business_profile y sector/nombre de empresa.
    """
    tpv = str(getattr(user, "tpv_business_profile", "") or "").strip().lower()
    if tpv in ("restaurante", "bar"):
        return HorarioBusinessProfile.RESTAURANTE
    if tpv in ("tienda_minorista", "farmacia"):
        return HorarioBusinessProfile.TIENDA
    if tpv in ("peluquería", "centro_estético", "taller", "clínica", "servicios"):
        return HorarioBusinessProfile.SERVICIOS

    link = (
        db.query(UserCompany)
        .filter(UserCompany.user_id == user.id)
        .order_by(UserCompany.id.asc())
        .first()
    )
    company = db.query(Company).filter(Company.id == link.company_id).first() if link else None
    if company and isinstance(company.metadata_, dict):
        bt = str(company.metadata_.get("business_type", "") or "").strip().lower()
        if bt in ("restaurant", "restaurante", "bar"):
            return HorarioBusinessProfile.RESTAURANTE
        if bt in ("retail", "tienda"):
            return HorarioBusinessProfile.TIENDA
        if bt in ("services", "servicios"):
            return HorarioBusinessProfile.SERVICIOS

    # Si existen mesas TPV, es hostelería casi seguro.
    try:
        if company and db.query(TPVTable).filter(TPVTable.company_id == company.id).count() > 0:
            return HorarioBusinessProfile.RESTAURANTE
    except Exception:
        pass

    sector = str(getattr(company, "sector", "") or "").strip().lower()
    cname = str(getattr(company, "company_name", "") or "").strip().lower()
    haystack = f"{sector} {cname}"
    if any(k in haystack for k in ("restaurante", "bar", "cafeter")):
        return HorarioBusinessProfile.RESTAURANTE
    if any(k in haystack for k in ("tienda", "retail", "comercio")):
        return HorarioBusinessProfile.TIENDA
    if any(k in haystack for k in ("servicio", "oficina", "asesor", "consult")):
        return HorarioBusinessProfile.SERVICIOS
    return None


def _backfill_default_schedules_if_missing(db: Session, user: User) -> None:
    """
    Autorreparación para empleados antiguos sin turnos: crea L-V 09:00-17:00.
    """
    company_ids = _company_ids_for_control_horario(db, user)
    if not company_ids:
        return
    employees = (
        db.query(CompanyEmployee)
        .filter(
            CompanyEmployee.company_id.in_(company_ids),
            CompanyEmployee.is_active.is_(True),
        )
        .all()
    )
    created = 0
    for emp in employees:
        code = str(emp.employee_code)
        has_any = (
            db.query(EmployeeSchedule)
            .filter(EmployeeSchedule.employee_id == code)
            .first()
        )
        if has_any:
            continue
        for dow in range(5):  # L-V
            db.add(
                EmployeeSchedule(
                    employee_id=code,
                    user_id=user.id,
                    day_of_week=dow,
                    start_time="09:00",
                    end_time="17:00",
                    shift_type="completo",
                    is_active=True,
                )
            )
            created += 1
    if created > 0:
        db.commit()


# Modelos Pydantic
class CheckInRequest(BaseModel):
    employee_id: str = Field(..., description="ID del empleado")
    method: str = Field(..., description="Método de fichaje: face, qr, code, location, remote")
    employee_phone: Optional[str] = Field(None, description="Móvil del empleado para verificación")
    location: Optional[str] = Field(None, description="Ubicación del fichaje")
    latitude: Optional[float] = Field(None, description="Latitud GPS")
    longitude: Optional[float] = Field(None, description="Longitud GPS")
    pin: Optional[str] = Field(None, description="PIN del empleado (método code)")
    qr_token: Optional[str] = Field(None, description="Código QR del centro (método qr)")


class CheckOutRequest(BaseModel):
    employee_id: str = Field(..., description="ID del empleado")
    method: Optional[str] = Field(None, description="Método de fichaje: qr, code, location, remote")
    employee_phone: Optional[str] = Field(None, description="Móvil del empleado para verificación")
    location: Optional[str] = Field(None, description="Ubicación del fichaje")
    latitude: Optional[float] = Field(None, description="Latitud GPS")
    longitude: Optional[float] = Field(None, description="Longitud GPS")
    pin: Optional[str] = Field(None, description="PIN del empleado (método code)")
    qr_token: Optional[str] = Field(None, description="Código QR del centro (método qr)")


class BreakToggleRequest(BaseModel):
    employee_id: str = Field(..., description="ID del empleado")
    method: Optional[str] = Field(None, description="Método de fichaje: qr, code, location, remote")
    employee_phone: Optional[str] = Field(None, description="Móvil del empleado para verificación")
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    pin: Optional[str] = None
    qr_token: Optional[str] = None


class SetBusinessProfileRequest(BaseModel):
    business_profile: str = Field(..., description="Perfil de negocio para control horario")


class CalculateHoursRequest(BaseModel):
    employee_id: str
    start_date: str  # ISO format
    end_date: str  # ISO format


def _scoped_counts(user: User, db: Optional[Session]) -> Dict[str, int]:
    if db is None:
        from app.db.base import SessionLocal

        with SessionLocal() as own:
            return _scoped_counts(user, own)
    cids = _company_ids_for_control_horario(db, user)
    active = (
        db.query(TimeTrackingRecord)
        .filter(_tt_scope_filter(user, cids), TimeTrackingRecord.status == RecordStatus.ACTIVE)
        .count()
    )
    employees = (
        db.query(CompanyEmployee)
        .filter(CompanyEmployee.company_id.in_(cids), CompanyEmployee.is_active.is_(True))
        .count()
        if cids
        else 0
    )
    return {"active_records_count": int(active), "employees_count": int(employees)}


def _resolve_profile_config(db: Session, user: User) -> Tuple[HorarioBusinessProfile, Dict[str, Any]]:
    """Perfil y configuracion del Control Horario calculados POR PETICION para el usuario.

    Antes se guardaban en el singleton global (`business_profile`/`config`), compartido por
    todas las empresas del proceso: la configuracion de una empresa podia salir en la
    respuesta de otra. Ahora no hay estado: se lee de BD (perfil guardado del usuario o
    inferido de su empresa) y la config es una copia del catalogo de perfiles."""
    row = db.query(User).filter(User.id == user.id).first() or user
    stored = str(getattr(row, "control_horario_business_profile", "") or "").strip().lower()
    profile: Optional[HorarioBusinessProfile] = None
    if stored:
        try:
            profile = HorarioBusinessProfile(stored)
        except ValueError:
            logger.warning("control_horario_business_profile invalido user_id=%s valor=%s", user.id, stored)
    if profile is None:
        profile = control_horario_service._auto_detect_business_profile(
            {"tpv_business_profile": getattr(row, "tpv_business_profile", None)}
        )
        # Si quedo en oficina por datos incompletos, inferir de la empresa real.
        inferred = _infer_profile_from_company_context(db, row)
        if inferred and profile == HorarioBusinessProfile.OFICINA:
            profile = inferred
    config = copy.deepcopy(control_horario_service.get_business_config(profile))
    # Bloqueo legal: el fichaje biometrico nunca se ofrece como habilitado.
    if isinstance(config.get("methods_enabled"), list):
        config["methods_enabled"] = [m for m in config["methods_enabled"] if not is_biometric_method(m)]
    return profile, config


async def _get_control_horario_info(current_user: User, db: Optional[Session] = None):
    """Informacion del Control Horario del usuario (sin estado compartido entre empresas)."""
    is_superuser = getattr(current_user, 'is_superuser', False)
    own_db = False
    if db is None:
        from app.db.base import SessionLocal
        db = SessionLocal()
        own_db = True
    try:
        profile, config = _resolve_profile_config(db, current_user)
        try:
            _backfill_default_schedules_if_missing(db, current_user)
        except Exception:
            logger.exception("backfill de horarios por defecto fallo user_id=%s", current_user.id)
            db.rollback()
        counts = _scoped_counts(current_user, db)
    finally:
        if own_db:
            db.close()

    return {
        "success": True,
        "service": "Control Horario Universal Enterprise",
        "version": "1.0.0",
        "user": {
            "email": current_user.email,
            "is_superuser": is_superuser,
            "is_active": current_user.is_active
        },
        "business_profile": profile.value,
        "config": config,
        "blocked_methods": {"face": BIOMETRIC_BLOCK_REASON},
        # Conteos de SU empresa desde BD (antes: singleton compartido entre empresas).
        **counts,
        "integrations": {
            "afrodita": control_horario_service.afrodita_integration is not None,
            "rafael": control_horario_service.rafael_integration is not None,
            "tpv": control_horario_service.tpv_integration is not None
        }
    }


@router.get("", include_in_schema=True)
@router.get("/", include_in_schema=True)
async def get_control_horario_root(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Endpoint raíz del Control Horario - Devuelve información básica"""
    return await _get_control_horario_info(current_user, db)


@router.get("/bootstrap")
async def get_control_horario_bootstrap(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Carga inicial optimizada del módulo: evita 3 requests secuenciales desde frontend.
    Devuelve info + status + employees en una sola respuesta.
    """
    info = await _get_control_horario_info(current_user, db)
    status_data = _active_status_from_db(db, current_user)
    raw_status_employees = status_data.get("employees") or {}
    if not isinstance(raw_status_employees, dict):
        raw_status_employees = {}

    db_roster = _employees_roster_from_db(db, current_user)
    if db_roster is not None:
        employees_payload = _merge_roster_with_status(db_roster, raw_status_employees)
        employees_source = "database"
    else:
        employees_payload = raw_status_employees
        if isinstance(employees_payload, dict):
            employees_payload = [
                {"id": emp_id, **(emp or {})}
                for emp_id, emp in employees_payload.items()
            ]
        employees_source = "memory"

    roster_for_ai: List[Dict[str, Any]] = []
    if db_roster is not None:
        roster_for_ai = list(db_roster)
    elif isinstance(employees_payload, list):
        roster_for_ai = [
            {"id": str(e.get("id")), "name": e.get("name", "")}
            for e in employees_payload
            if e.get("id") is not None
        ]
    st_emp = raw_status_employees if isinstance(raw_status_employees, dict) else {}
    try:
        sm.evaluate_alerts(db, current_user, roster=roster_for_ai, employees_status=st_emp)
    except Exception as e:
        logger.warning("evaluate_alerts omitido: %s", e)

    smart_payload: Dict[str, Any] = {
        "mode": "ZEUS_SMART_TIME_CONTROL",
        "alerts": sm.fetch_recent_alerts(db, current_user),
        "patterns": sm.detect_patterns(
            db,
            current_user,
            [str(x["id"]) for x in roster_for_ai if x.get("id")],
        ),
        "tpv": sm.tpv_sales_window(db, current_user),
        "today_completed_hours_by_employee": sm.today_completed_hours_by_employee(db, current_user),
        "integrations": {"afrodita_activity_feed": True, "tpv_sales_window": True},
    }

    cost_engine: Dict[str, Any] = {}
    cid = _primary_company_id(db, current_user)
    if cid:
        try:
            from services.time_cost_engine_v1 import (
                get_active_sessions,
                get_cost_analytics,
                refresh_partial_costs,
            )

            refresh_partial_costs(db, company_id=cid)
            cost_engine = get_cost_analytics(db, user=current_user, company_id=cid)
            cost_engine["active_sessions"] = get_active_sessions(
                db, user=current_user, company_id=cid
            )
            cost_engine["company_id"] = cid
        except Exception as e:
            logger.warning("cost_engine bootstrap omitido: %s", e)

    return {
        "success": True,
        "info": info,
        "status": status_data,
        "today_records": _today_records_from_db(db, current_user),
        "employees": employees_payload,
        "total_active": status_data.get("total_active", 0),
        "employees_source": employees_source,
        "smart": smart_payload,
        "cost_engine": cost_engine,
    }


@router.get("/status")
async def get_control_horario_status(
    employee_id: Optional[str] = Query(None, description="ID del empleado (opcional)"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Obtener estado actual del Control Horario"""
    is_superuser = getattr(current_user, 'is_superuser', False)
    
    profile, config = _resolve_profile_config(db, current_user)

    # Obtener estado
    status_data = _active_status_from_db(db, current_user)
    if employee_id:
        emps = status_data.get("employees", {}) or {}
        status_data = {
            "success": True,
            "employee_id": employee_id,
            "status": emps.get(employee_id, {}).get("status", "outside"),
            "check_in_time": emps.get(employee_id, {}).get("check_in_time"),
        }
    
    return {
        "success": True,
        "business_profile": profile.value,
        "config": config,
        "blocked_methods": {"face": BIOMETRIC_BLOCK_REASON},
        "status": status_data,
        "is_superuser": is_superuser
    }


# --------------------------------------------------------------------------------------
# Endpoints legacy de fichaje -> motor v1 (services/time_cost_engine_v1.register_checkin)
#
# Antes usaban el singleton global `control_horario_service` (active_records en memoria
# por employee_id, compartido entre TODAS las empresas: dos empresas con el mismo codigo
# de empleado se pisaban) y aceptaban cualquier metodo sin verificarlo. Ahora delegan en
# el motor v1: empresa del usuario, PIN contra hash, QR firmado por empresa, lat/lng para
# geolocalizacion, bloqueo biometrico 501, registro en BD y log. Sin estado en memoria.
# Ruta recomendada: POST /api/v1/checkin.
# --------------------------------------------------------------------------------------

_LEGACY_TO_V1_METHOD = {
    "code": "pin",
    "pin": "pin",
    "qr": "qr",
    "location": "geo",
    "on_site": "geo",
    "geo": "geo",
    "remote": "device",
    "device": "device",
}


def _legacy_checkin(
    *,
    db: Session,
    http_req: Request,
    current_user: User,
    employee_id: str,
    checkin_type: str,
    method: Optional[str],
    employee_phone: Optional[str],
    pin: Optional[str],
    qr_token: Optional[str],
    latitude: Optional[float],
    longitude: Optional[float],
    location: Optional[str],
) -> Dict[str, Any]:
    from app.core.security_middleware import get_real_client_ip
    from services.time_cost_engine_v1 import register_checkin

    cid = _primary_company_id(db, current_user)
    reject_biometric(method, user_id=current_user.id, company_id=cid)
    if not cid:
        raise HTTPException(status_code=400, detail="No hay empresa asociada. Configura la empresa antes de fichar.")
    raw_method = str(method or "remote").strip().lower()
    v1_method = _LEGACY_TO_V1_METHOD.get(raw_method)
    if v1_method is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Método inválido: {method}. Métodos válidos: qr, code, location, remote",
        )
    _verify_employee_phone_or_raise(db, user=current_user, employee_id=employee_id, employee_phone=employee_phone)

    user_agent = (http_req.headers.get("user-agent") or "")[:512] or None
    device_id = (http_req.headers.get("x-device-id") or "").strip() or (user_agent or "")[:128] or None
    metadata: Dict[str, Any] = {"source": "control_horario_legacy"}
    if pin:
        metadata["pin"] = pin
    if qr_token:
        metadata["qr_token"] = qr_token
    if latitude is not None:
        metadata["lat"] = latitude
    if longitude is not None:
        metadata["lng"] = longitude
    if location:
        metadata["location"] = location[:255]
    if device_id:
        metadata["device_id"] = device_id

    out = register_checkin(
        db,
        user=current_user,
        company_id=cid,
        employee_id=str(employee_id),
        checkin_type=checkin_type,
        method=v1_method,
        metadata=metadata,
        client_ip=get_real_client_ip(http_req),
        device_id=device_id,
        user_agent=user_agent,
    )
    logger.info(
        "control_horario legacy -> v1 type=%s method=%s employee=%s company_id=%s user_id=%s",
        checkin_type, v1_method, employee_id, cid, current_user.id,
    )
    return {**out, "success": True, "via": "/api/v1/checkin"}


@router.post("/check-in")
async def check_in(
    request: CheckInRequest,
    http_req: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Registrar entrada (delegado en el motor v1 por empresa)."""
    return _legacy_checkin(
        db=db, http_req=http_req, current_user=current_user, employee_id=request.employee_id,
        checkin_type="entrada", method=request.method, employee_phone=request.employee_phone,
        pin=request.pin, qr_token=request.qr_token, latitude=request.latitude,
        longitude=request.longitude, location=request.location,
    )


@router.post("/check-out")
async def check_out(
    request: CheckOutRequest,
    http_req: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Registrar salida (delegado en el motor v1 por empresa)."""
    return _legacy_checkin(
        db=db, http_req=http_req, current_user=current_user, employee_id=request.employee_id,
        checkin_type="salida", method=request.method, employee_phone=request.employee_phone,
        pin=request.pin, qr_token=request.qr_token, latitude=request.latitude,
        longitude=request.longitude, location=request.location,
    )


@router.post("/break-start")
async def break_start(
    request: BreakToggleRequest,
    http_req: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Iniciar pausa (delegado en el motor v1 por empresa)."""
    return _legacy_checkin(
        db=db, http_req=http_req, current_user=current_user, employee_id=request.employee_id,
        checkin_type="pausa_inicio", method=request.method, employee_phone=request.employee_phone,
        pin=request.pin, qr_token=request.qr_token, latitude=request.latitude,
        longitude=request.longitude, location=request.location,
    )


@router.post("/break-end")
async def break_end(
    request: BreakToggleRequest,
    http_req: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Finalizar pausa (delegado en el motor v1 por empresa)."""
    return _legacy_checkin(
        db=db, http_req=http_req, current_user=current_user, employee_id=request.employee_id,
        checkin_type="pausa_fin", method=request.method, employee_phone=request.employee_phone,
        pin=request.pin, qr_token=request.qr_token, latitude=request.latitude,
        longitude=request.longitude, location=request.location,
    )


# ----------------------------------------------------------------------------------------------
# PIN de fichaje ("Código manual"): el motor (time_cost_engine_v1._verify_pin) exige
# company_employees.tpv_pin_hash, pero nada lo asignaba -> el método era inutilizable.
# ----------------------------------------------------------------------------------------------
PIN_MANAGER_ROLES = frozenset({"owner", "company_admin"})
_PIN_RE = re.compile(r"^\d{4,8}$")


class EmployeePinRequest(BaseModel):
    pin: str = Field(..., min_length=4, max_length=8, description="PIN numérico de 4 a 8 dígitos")


@router.put("/employees/{employee_code}/pin", dependencies=[Depends(thalos_request_guard)])
async def set_employee_pin(
    employee_code: str,
    body: EmployeePinRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Fija o cambia el PIN de fichaje de un empleado de TU empresa (dueño o encargado).

    El PIN se guarda solo como hash (`get_password_hash`, el mismo esquema que verifica
    `verify_password` en el motor de fichajes). Empleado de otra empresa -> 404 (no se revela
    que existe).
    """
    from app.core.security import get_password_hash
    from services.thalos_request_guard_v1 import record_security_event

    pin = str(body.pin or "").strip()
    if not _PIN_RE.match(pin):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El PIN debe tener entre 4 y 8 dígitos (solo números).",
        )
    if str(getattr(current_user, "role", "") or "").lower() == "employee":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el dueño o un encargado de la empresa puede asignar PIN de fichaje.",
        )

    links = db.query(UserCompany).filter(UserCompany.user_id == current_user.id).all()
    roles = {int(l.company_id): str(l.role or "").lower() for l in links}
    emp = None
    if roles:
        emp = (
            db.query(CompanyEmployee)
            .filter(
                CompanyEmployee.company_id.in_(list(roles)),
                CompanyEmployee.employee_code == str(employee_code),
                CompanyEmployee.is_active.is_(True),
            )
            .first()
        )
    if emp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empleado no encontrado para esta empresa.")
    if roles.get(int(emp.company_id)) not in PIN_MANAGER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el dueño o un encargado de la empresa puede asignar PIN de fichaje.",
        )

    had_pin = bool(emp.tpv_pin_hash)
    emp.tpv_pin_hash = get_password_hash(pin)
    db.commit()

    record_security_event(
        db,
        event_type="employee_pin_set",
        severity="info",
        source="control_horario",
        details={
            "employee_code": emp.employee_code,
            "employee_id": emp.id,
            "changed": had_pin,
        },
        user=current_user,
        company_id=int(emp.company_id),
        action_taken="allow",
        decision_rule="pin_set_by_company_manager",
    )
    logger.info(
        "PIN de fichaje %s: empresa=%s empleado=%s por usuario=%s",
        "cambiado" if had_pin else "asignado", emp.company_id, emp.employee_code, current_user.id,
    )
    return {
        "success": True,
        "employee_id": emp.employee_code,
        "name": emp.full_name,
        "pin_configured": True,
        "changed": had_pin,
        "message": f"PIN de fichaje {'cambiado' if had_pin else 'asignado'} para {emp.full_name}.",
    }


@router.get("/employees")
async def get_employees(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Listar empleados con estado actual"""
    try:

        status_data = _active_status_from_db(db, current_user)
        raw = status_data.get("employees") or {}
        if not isinstance(raw, dict):
            raw = {}
        db_roster = _employees_roster_from_db(db, current_user)
        if db_roster is not None:
            merged = _merge_roster_with_status(db_roster, raw)
            employees_out = {
                e["id"]: {
                    "status": e["status"],
                    "check_in_time": e.get("check_in_time"),
                    "name": e["name"],
                    "role_title": e.get("role_title", ""),
                    "source": e.get("source"),
                }
                for e in merged
            }
        return {
            "success": True,
                "employees": employees_out,
                "total_active": status_data.get("total_active", 0),
                "employees_source": "database",
            }
        return {
            "success": True,
            "employees": raw,
            "total_active": status_data.get("total_active", 0),
            "employees_source": "memory",
        }
        
    except Exception as e:
        logger.exception("Error obteniendo empleados")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo obtener la lista de empleados. Inténtalo de nuevo."
        )


@router.post("/calculate-hours")
async def calculate_hours(
    request: CalculateHoursRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Calcular horas trabajadas en un período"""
    try:
        
        start_date = datetime.fromisoformat(request.start_date.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(request.end_date.replace('Z', '+00:00'))
        
        # Antes: suma de active_records del singleton en memoria (todas las empresas,
        # ignorando el periodo). Ahora: registros cerrados de SU empresa en el periodo.
        cids = _company_ids_for_control_horario(db, current_user)
        rows = (
            db.query(TimeTrackingRecord)
            .filter(
                _tt_scope_filter(current_user, cids),
                TimeTrackingRecord.employee_id == str(request.employee_id),
                TimeTrackingRecord.check_in_time >= start_date,
                TimeTrackingRecord.check_in_time < end_date,
                TimeTrackingRecord.hours_worked.isnot(None),
            )
            .all()
        )
        total_hours = sum(float(r.hours_worked or 0) for r in rows)
        days = {r.check_in_time.date() for r in rows if r.check_in_time}
        return {
            "success": True,
            "employee_id": request.employee_id,
            "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "total_hours": round(total_hours, 2),
            "records_count": len(rows),
            "average_hours_per_day": round(total_hours / len(days), 2) if days else 0,
        }

    except ValueError:
        raise HTTPException(status_code=400, detail="Fechas inválidas: usa formato ISO 8601.")
    except Exception as e:
        logger.exception("Error calculando horas")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudieron calcular las horas trabajadas. Inténtalo de nuevo."
        )


@router.post("/set-business-profile")
async def set_business_profile(
    request: SetBusinessProfileRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Establecer business_profile para Control Horario"""
    try:
        profile_str = request.business_profile.lower()

        try:
            profile = HorarioBusinessProfile(profile_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Perfil inválido: {profile_str}. Perfiles válidos: {[p.value for p in HorarioBusinessProfile]}"
            )

        # Se guarda solo en BD (perfil del usuario); nada en el singleton compartido.
        user = db.query(User).filter(User.id == current_user.id).first()
        if user is None:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        try:
            user.control_horario_business_profile = profile.value
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("No se pudo guardar control_horario_business_profile user_id=%s", current_user.id)
            raise HTTPException(status_code=500, detail="No se pudo guardar el perfil de negocio.")
        logger.info("control horario perfil actualizado user_id=%s perfil=%s", current_user.id, profile.value)
        _, config = _resolve_profile_config(db, user)

        return {
            "success": True,
            "message": f"Business profile actualizado a: {profile.value}",
            "business_profile": profile.value,
            "config": config,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error estableciendo business profile")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo establecer el perfil de negocio. Inténtalo de nuevo."
        )


@router.get("/reports")
async def get_reports(
    employee_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Obtener reportes de asistencia"""
    try:
        
        # Por ahora, devolver datos básicos
        # En producción, consultaría la base de datos
        
        status_data = _active_status_from_db(db, current_user)
        
        return {
            "success": True,
            "reports": {
                "current_status": status_data,
                "active_records": status_data.get("total_active", 0),
                "today_records": _today_records_from_db(db, current_user),
            }
        }
        
    except Exception as e:
        logger.exception("Error obteniendo reportes")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudieron obtener los reportes. Inténtalo de nuevo."
        )
