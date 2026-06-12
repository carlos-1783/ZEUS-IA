"""
Endpoints para el módulo de Control Horario Universal
"""
from datetime import datetime, timedelta, timezone
import re
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
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

router = APIRouter()
logger = logging.getLogger(__name__)


def _company_ids_for_control_horario(db: Session, user: User) -> List[int]:
    rows = db.query(UserCompany.company_id).filter(UserCompany.user_id == user.id).all()
    return [r[0] for r in rows]


def _normalize_phone(phone: Optional[str]) -> str:
    return re.sub(r"\D+", "", str(phone or ""))


def _requires_phone_verification(user: User) -> bool:
    tpv_profile = str(getattr(user, "tpv_business_profile", "") or "").strip().lower()
    if tpv_profile in {"bar", "restaurante", "restaurant"}:
        return True
    current = control_horario_service.business_profile
    return current == HorarioBusinessProfile.RESTAURANTE


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
    rows = (
        db.query(TimeTrackingRecord)
        .filter(
            TimeTrackingRecord.user_id == user.id,
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


def _load_schedules_into_runtime(db: Session, user: User) -> None:
    """
    Carga horarios desde BD al runtime del servicio para validación strict_check_in.
    """
    company_ids = _company_ids_for_control_horario(db, user)
    if not company_ids:
        control_horario_service.schedules = {}
        return

    rows = (
        db.query(CompanyEmployee, EmployeeSchedule)
        .join(EmployeeSchedule, EmployeeSchedule.employee_id == CompanyEmployee.employee_code)
        .filter(
            CompanyEmployee.company_id.in_(company_ids),
            CompanyEmployee.is_active.is_(True),
            EmployeeSchedule.is_active.is_(True),
        )
        .all()
    )
    schedules_map: Dict[str, List[Dict[str, Any]]] = {}
    for _, sch in rows:
        emp_id = str(sch.employee_id)
        schedules_map.setdefault(emp_id, []).append(
            {
                "day_of_week": int(sch.day_of_week),
                "start_time": str(sch.start_time),
                "end_time": str(sch.end_time),
                "shift_type": str(sch.shift_type or "completo"),
            }
        )
    control_horario_service.schedules = schedules_map


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


class CheckOutRequest(BaseModel):
    employee_id: str = Field(..., description="ID del empleado")
    method: Optional[str] = Field(None, description="Método de fichaje: face, qr, code, location, remote")
    employee_phone: Optional[str] = Field(None, description="Móvil del empleado para verificación")
    location: Optional[str] = Field(None, description="Ubicación del fichaje")
    latitude: Optional[float] = Field(None, description="Latitud GPS")
    longitude: Optional[float] = Field(None, description="Longitud GPS")


class BreakToggleRequest(BaseModel):
    employee_id: str = Field(..., description="ID del empleado")
    employee_phone: Optional[str] = Field(None, description="Móvil del empleado para verificación")
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class SetBusinessProfileRequest(BaseModel):
    business_profile: str = Field(..., description="Perfil de negocio para control horario")


class CalculateHoursRequest(BaseModel):
    employee_id: str
    start_date: str  # ISO format
    end_date: str  # ISO format


async def _get_control_horario_info(current_user: User, db: Optional[Session] = None):
    """Función auxiliar para obtener información del Control Horario"""
    is_superuser = getattr(current_user, 'is_superuser', False)
    
    # Cargar business_profile del usuario (reusar sesión del request si existe).
    own_db = False
    if db is None:
        from app.db.base import SessionLocal
        db = SessionLocal()
        own_db = True
    try:
        user = db.query(User).filter(User.id == current_user.id).first()
        if user:
            user_data = {
                "id": user.id,
                "control_horario_business_profile": getattr(user, 'control_horario_business_profile', None),
                "tpv_business_profile": getattr(user, 'tpv_business_profile', None),
                "company_name": getattr(user, 'company_name', None)
            }
            try:
                control_horario_service.load_user_profile(user_data)
            except Exception as e:
                logger.warning(f"Error cargando perfil de usuario: {e}")
                if not control_horario_service.business_profile and not is_superuser:
                    control_horario_service.set_business_profile(HorarioBusinessProfile.OFICINA)
                elif not control_horario_service.business_profile and is_superuser:
                    control_horario_service.set_business_profile(HorarioBusinessProfile.OFICINA)

            # Corrección automática: si quedó en oficina por datos incompletos, inferir perfil real de negocio.
            inferred = _infer_profile_from_company_context(db, user)
            current = control_horario_service.business_profile
            if inferred and (current is None or current == HorarioBusinessProfile.OFICINA):
                control_horario_service.set_business_profile(inferred, user.id)
            _backfill_default_schedules_if_missing(db, user)
            _load_schedules_into_runtime(db, user)
        else:
            if not control_horario_service.business_profile:
                user_data = {
                    "id": current_user.id,
                    "company_name": getattr(current_user, 'company_name', None)
                }
                control_horario_service.load_user_profile(user_data)
                if not control_horario_service.business_profile and not is_superuser:
                    control_horario_service.set_business_profile(HorarioBusinessProfile.OFICINA)
                elif not control_horario_service.business_profile and is_superuser:
                    control_horario_service.set_business_profile(HorarioBusinessProfile.OFICINA)
    except Exception as e:
        logger.error(f"Error cargando perfil de usuario: {e}")
        if not control_horario_service.business_profile:
            control_horario_service.set_business_profile(HorarioBusinessProfile.OFICINA)
    finally:
        if own_db:
            db.close()

    config = control_horario_service.config if control_horario_service.business_profile else {}
    
    # Para superusuarios, asegurar configuración completa
    if is_superuser and not config:
        config = {
            "strict_check_in": True,
            "gps_required": False,
            "multiple_shifts_per_day": True,
            "break_time_required": True,
            "auto_check_out": False,
            "irregularity_alerts": True,
            "methods_enabled": ["face", "qr", "code", "location", "remote"],
            "location_tracking": False,
            "remote_allowed": True,
            "flexible_hours": True,
            "superuser_override": True
        }
    
    return {
        "success": True,
        "service": "Control Horario Universal Enterprise",
        "version": "1.0.0",
        "user": {
            "email": current_user.email,
            "is_superuser": is_superuser,
            "is_active": current_user.is_active
        },
        "business_profile": control_horario_service.business_profile.value if control_horario_service.business_profile else None,
        "config": config,
        "active_records_count": len(control_horario_service.active_records),
        "employees_count": len(control_horario_service.employees),
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
    
    # Cargar perfil si no está cargado
    if not control_horario_service.business_profile:
        await _get_control_horario_info(current_user, db)
    
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
        "business_profile": control_horario_service.business_profile.value if control_horario_service.business_profile else None,
        "config": control_horario_service.config if control_horario_service.business_profile else {},
        "status": status_data,
        "is_superuser": is_superuser
    }


@router.post("/check-in")
async def check_in(
    request: CheckInRequest,
    http_req: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Registrar entrada de un empleado"""
    try:
        if not control_horario_service.business_profile:
            await _get_control_horario_info(current_user, db)
        _verify_employee_phone_or_raise(
            db,
            user=current_user,
            employee_id=request.employee_id,
            employee_phone=request.employee_phone,
        )

        sm.sync_runtime_active_records(db, current_user, control_horario_service)

        pex = sm.geo_payload_for_event(request.latitude, request.longitude)
        if (
            getattr(settings, "CONTROL_HORARIO_FAIL_IF_OUTSIDE_ZONE", False)
            and pex.get("geo_validated")
            and pex.get("location_ok") is False
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Fichaje fuera de la zona permitida",
            )

        try:
            method = CheckInMethod(request.method.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Método inválido: {request.method}. Métodos válidos: face, qr, code, location, remote, on_site",
            )

        method_val = method.value
        if method_val == "on_site":
            method_val = "location"

        device = (http_req.headers.get("user-agent") or "")[:512] or None

        existing_pre = (
            db.query(TimeTrackingRecord)
            .filter(
                TimeTrackingRecord.user_id == current_user.id,
                TimeTrackingRecord.employee_id == request.employee_id,
                TimeTrackingRecord.status == RecordStatus.ACTIVE,
            )
            .order_by(TimeTrackingRecord.id.desc())
            .first()
        )

        if existing_pre:
            now_ts = datetime.now(timezone.utc)
            existing_pre.check_in_time = now_ts
            existing_pre.check_in_method = method_val
            if request.location:
                existing_pre.check_in_location = request.location
            if request.latitude is not None:
                existing_pre.check_in_latitude = request.latitude
            if request.longitude is not None:
                existing_pre.check_in_longitude = request.longitude
            db.add(existing_pre)
            db.flush()
            db.commit()
            sm.sync_runtime_active_records(db, current_user, control_horario_service)
            if getattr(settings, "SMART_TIME_CONTROL_LOG_AFRODITA", True):
                emit_time_control_event(
                    user_id=current_user.id,
                    user_email=current_user.email,
                    company_id=_primary_company_id(db, current_user),
                    employee_id=str(request.employee_id),
                    event_type="check-in",
                    record_id=existing_pre.id,
                    details={"idempotent": True, "geo": pex or {}},
                )
            return {
                "success": True,
                "record": _db_row_to_service_record(existing_pre),
                "message": "Entrada ya activa; datos actualizados",
            }

        result = control_horario_service.check_in(
            employee_id=request.employee_id,
            method=method,
            location=request.location,
            latitude=request.latitude,
            longitude=request.longitude,
            user_id=current_user.id,
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Error al registrar entrada"),
            )

        rec = result.get("record", {}) or {}
        check_in_time = rec.get("check_in_time")
        if isinstance(check_in_time, str):
            check_in_time = datetime.fromisoformat(check_in_time.replace("Z", "+00:00"))
        if not isinstance(check_in_time, datetime):
            check_in_time = datetime.now(timezone.utc)

        existing = (
            db.query(TimeTrackingRecord)
            .filter(
                TimeTrackingRecord.user_id == current_user.id,
                TimeTrackingRecord.employee_id == request.employee_id,
                TimeTrackingRecord.status == RecordStatus.ACTIVE,
            )
            .order_by(TimeTrackingRecord.id.desc())
            .first()
        )
        if existing:
            existing.check_in_time = check_in_time
            existing.check_in_method = rec.get("check_in_method", method_val)
            existing.check_in_location = rec.get("check_in_location") or request.location
            existing.check_in_latitude = rec.get("check_in_latitude") or request.latitude
            existing.check_in_longitude = rec.get("check_in_longitude") or request.longitude
            existing.irregularities = rec.get("irregularities") or []
            existing.irregularities_count = int(rec.get("irregularities_count") or 0)
            existing.is_late_check_in = bool(rec.get("is_late_check_in") or False)
            db.add(existing)
        else:
            db.add(
                TimeTrackingRecord(
                    employee_id=request.employee_id,
                    user_id=current_user.id,
                    check_in_time=check_in_time,
                    check_in_method=rec.get("check_in_method", method_val),
                    check_in_location=rec.get("check_in_location") or request.location,
                    check_in_latitude=rec.get("check_in_latitude") or request.latitude,
                    check_in_longitude=rec.get("check_in_longitude") or request.longitude,
                    status=RecordStatus.ACTIVE,
                    irregularities=rec.get("irregularities") or [],
                    irregularities_count=int(rec.get("irregularities_count") or 0),
                    is_late_check_in=bool(rec.get("is_late_check_in") or False),
                )
            )
        db.flush()
        row = (
            db.query(TimeTrackingRecord)
            .filter(
                TimeTrackingRecord.user_id == current_user.id,
                TimeTrackingRecord.employee_id == request.employee_id,
                TimeTrackingRecord.status == RecordStatus.ACTIVE,
            )
            .order_by(TimeTrackingRecord.id.desc())
            .first()
        )
        if row:
            sm.append_event(
                db,
                user_id=current_user.id,
                employee_id=str(request.employee_id),
                record_id=row.id,
                event_type="check-in",
                occurred_at=row.check_in_time or check_in_time,
                location=request.location,
                latitude=request.latitude,
                longitude=request.longitude,
                device=device,
                extra_payload={"geo": pex or {}},
            )
        db.commit()
        sm.sync_runtime_active_records(db, current_user, control_horario_service)

        if getattr(settings, "SMART_TIME_CONTROL_LOG_AFRODITA", True) and row:
            emit_time_control_event(
                user_id=current_user.id,
                user_email=current_user.email,
                company_id=_primary_company_id(db, current_user),
                employee_id=str(request.employee_id),
                event_type="check-in",
                record_id=row.id,
                details={"geo": pex or {}},
            )

        if control_horario_service.afrodita_integration:
            control_horario_service.sync_with_afrodita(request.employee_id, result["record"])
        
        logger.info("Check-in registrado: %s", request.employee_id)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en check-in: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno: {str(e)}",
        )


@router.post("/check-out")
async def check_out(
    request: CheckOutRequest,
    http_req: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Registrar salida de un empleado"""
    try:
        if not control_horario_service.business_profile:
            await _get_control_horario_info(current_user, db)
        _verify_employee_phone_or_raise(
            db,
            user=current_user,
            employee_id=request.employee_id,
            employee_phone=request.employee_phone,
        )

        sm.sync_runtime_active_records(db, current_user, control_horario_service)

        method = None
        if request.method:
            try:
                method = CheckInMethod(request.method.lower())
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Método inválido: {request.method}",
                )
        
        result = control_horario_service.check_out(
            employee_id=request.employee_id,
            method=method,
            location=request.location,
            latitude=request.latitude,
            longitude=request.longitude,
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Error al registrar salida"),
            )

        rec = result.get("record", {}) or {}
        check_out_time = rec.get("check_out_time")
        if isinstance(check_out_time, str):
            check_out_time = datetime.fromisoformat(check_out_time.replace("Z", "+00:00"))
        if not isinstance(check_out_time, datetime):
            check_out_time = datetime.now(timezone.utc)

        device = (http_req.headers.get("user-agent") or "")[:512] or None
        pex = sm.geo_payload_for_event(request.latitude, request.longitude)

        active = (
            db.query(TimeTrackingRecord)
            .filter(
                TimeTrackingRecord.user_id == current_user.id,
                TimeTrackingRecord.employee_id == request.employee_id,
                TimeTrackingRecord.status == RecordStatus.ACTIVE,
            )
            .order_by(TimeTrackingRecord.id.desc())
            .first()
        )
        fallback_break = 0.0
        if active:
            net, brk, extra = sm.compute_hours_with_break_events(
                db,
                user_id=current_user.id,
                record=active,
                check_out_time=check_out_time,
                fallback_break_hours=fallback_break,
            )
            active.check_out_time = check_out_time
            active.check_out_method = rec.get("check_out_method", request.method or "code")
            active.check_out_location = rec.get("check_out_location") or request.location
            active.check_out_latitude = rec.get("check_out_latitude") or request.latitude
            active.check_out_longitude = rec.get("check_out_longitude") or request.longitude
            active.hours_worked = net
            active.break_duration = brk
            active.extra_hours = extra
            active.status = RecordStatus.COMPLETED
            active.irregularities = rec.get("irregularities") or []
            active.irregularities_count = int(rec.get("irregularities_count") or 0)
            active.is_early_check_out = bool(rec.get("is_early_check_out") or False)
            db.add(active)
            db.flush()
            sm.append_event(
                db,
                user_id=current_user.id,
                employee_id=str(request.employee_id),
                record_id=active.id,
                event_type="check-out",
                occurred_at=check_out_time,
                location=request.location,
                latitude=request.latitude,
                longitude=request.longitude,
                device=device,
                extra_payload={"geo": pex or {}, "hours_worked": net, "extra_hours": extra},
            )
        else:
            db.add(
                TimeTrackingRecord(
                    employee_id=request.employee_id,
                    user_id=current_user.id,
                    check_in_time=datetime.now(timezone.utc) - timedelta(hours=float(result.get("hours_worked") or 0)),
                    check_out_time=check_out_time,
                    check_in_method="code",
                    check_out_method=rec.get("check_out_method", request.method or "code"),
                    status=RecordStatus.COMPLETED,
                    hours_worked=float(result.get("hours_worked") or 0),
                    break_duration=float(rec.get("break_duration") or 0),
                    irregularities=rec.get("irregularities") or [],
                    irregularities_count=int(rec.get("irregularities_count") or 0),
                )
            )
        db.commit()
        sm.sync_runtime_active_records(db, current_user, control_horario_service)

        if active:
            result["hours_worked"] = float(active.hours_worked or 0)

        if getattr(settings, "SMART_TIME_CONTROL_LOG_AFRODITA", True) and active:
            emit_time_control_event(
                user_id=current_user.id,
                user_email=current_user.email,
                company_id=_primary_company_id(db, current_user),
                employee_id=str(request.employee_id),
                event_type="check-out",
                record_id=active.id,
                details={
                    "hours_worked": float(active.hours_worked or 0),
                    "extra_hours": float(active.extra_hours or 0),
                    "geo": pex or {},
                },
            )

        if control_horario_service.rafael_integration and result.get("hours_worked"):
            control_horario_service.sync_with_rafael(
                request.employee_id,
                {
                    "hours_worked": result.get("hours_worked"),
                    "date": datetime.now(timezone.utc).date().isoformat(),
                    "record": result.get("record"),
                },
            )

        if control_horario_service.afrodita_integration:
            control_horario_service.sync_with_afrodita(request.employee_id, result["record"])
        
        logger.info(
            "Check-out registrado: %s — %sh",
            request.employee_id,
            result.get("hours_worked", 0),
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en check-out: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno: {str(e)}",
        )


@router.post("/break-start")
async def break_start(
    request: BreakToggleRequest,
    http_req: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Inicio de pausa (requiere entrada activa)."""
    try:
        if not control_horario_service.business_profile:
            await _get_control_horario_info(current_user, db)
        _verify_employee_phone_or_raise(
            db,
            user=current_user,
            employee_id=request.employee_id,
            employee_phone=request.employee_phone,
        )
        sm.sync_runtime_active_records(db, current_user, control_horario_service)
        active = (
            db.query(TimeTrackingRecord)
            .filter(
                TimeTrackingRecord.user_id == current_user.id,
                TimeTrackingRecord.employee_id == request.employee_id,
                TimeTrackingRecord.status == RecordStatus.ACTIVE,
            )
            .order_by(TimeTrackingRecord.id.desc())
            .first()
        )
        if not active:
            raise HTTPException(status_code=400, detail="No hay fichaje de entrada activo")
        try:
            sm.validate_break_transition(db, current_user.id, active, "break-start")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        now_ts = datetime.now(timezone.utc)
        device = (http_req.headers.get("user-agent") or "")[:512] or None
        pex = sm.geo_payload_for_event(request.latitude, request.longitude)
        sm.append_event(
            db,
            user_id=current_user.id,
            employee_id=str(request.employee_id),
            record_id=active.id,
            event_type="break-start",
            occurred_at=now_ts,
            location=request.location,
            latitude=request.latitude,
            longitude=request.longitude,
            device=device,
            extra_payload={"geo": pex or {}},
        )
        db.commit()
        if getattr(settings, "SMART_TIME_CONTROL_LOG_AFRODITA", True):
            emit_time_control_event(
                user_id=current_user.id,
                user_email=current_user.email,
                company_id=_primary_company_id(db, current_user),
                employee_id=str(request.employee_id),
                event_type="break-start",
                record_id=active.id,
                details={"geo": pex or {}},
            )
        return {"success": True, "message": "Pausa iniciada", "employee_id": request.employee_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("break_start: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/break-end")
async def break_end(
    request: BreakToggleRequest,
    http_req: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Fin de pausa."""
    try:
        if not control_horario_service.business_profile:
            await _get_control_horario_info(current_user, db)
        _verify_employee_phone_or_raise(
            db,
            user=current_user,
            employee_id=request.employee_id,
            employee_phone=request.employee_phone,
        )
        sm.sync_runtime_active_records(db, current_user, control_horario_service)
        active = (
            db.query(TimeTrackingRecord)
            .filter(
                TimeTrackingRecord.user_id == current_user.id,
                TimeTrackingRecord.employee_id == request.employee_id,
                TimeTrackingRecord.status == RecordStatus.ACTIVE,
            )
            .order_by(TimeTrackingRecord.id.desc())
            .first()
        )
        if not active:
            raise HTTPException(status_code=400, detail="No hay fichaje de entrada activo")
        try:
            sm.validate_break_transition(db, current_user.id, active, "break-end")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        now_ts = datetime.now(timezone.utc)
        device = (http_req.headers.get("user-agent") or "")[:512] or None
        pex = sm.geo_payload_for_event(request.latitude, request.longitude)
        sm.append_event(
            db,
            user_id=current_user.id,
            employee_id=str(request.employee_id),
            record_id=active.id,
            event_type="break-end",
            occurred_at=now_ts,
            location=request.location,
            latitude=request.latitude,
            longitude=request.longitude,
            device=device,
            extra_payload={"geo": pex or {}},
        )
        db.commit()
        if getattr(settings, "SMART_TIME_CONTROL_LOG_AFRODITA", True):
            emit_time_control_event(
                user_id=current_user.id,
                user_email=current_user.email,
                company_id=_primary_company_id(db, current_user),
                employee_id=str(request.employee_id),
                event_type="break-end",
                record_id=active.id,
                details={"geo": pex or {}},
            )
        return {"success": True, "message": "Pausa finalizada", "employee_id": request.employee_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("break_end: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/employees")
async def get_employees(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Listar empleados con estado actual"""
    try:
        if not control_horario_service.business_profile:
            await _get_control_horario_info(current_user, db)

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
        logger.error(f"Error obteniendo empleados: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/calculate-hours")
async def calculate_hours(
    request: CalculateHoursRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Calcular horas trabajadas en un período"""
    try:
        if not control_horario_service.business_profile:
            await _get_control_horario_info(current_user, db)
        
        start_date = datetime.fromisoformat(request.start_date.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(request.end_date.replace('Z', '+00:00'))
        
        result = control_horario_service.calculate_hours(
            employee_id=request.employee_id,
            start_date=start_date,
            end_date=end_date
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error calculando horas: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
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
        
        # Actualizar en base de datos
        user = db.query(User).filter(User.id == current_user.id).first()
        if user:
            try:
                setattr(user, 'control_horario_business_profile', profile.value)
                db.commit()
                logger.info(f"✅ Business profile actualizado: {profile.value}")
            except Exception as e:
                logger.warning(f"Error actualizando control_horario_business_profile: {e}")
                db.rollback()
        
        # Actualizar servicio
        control_horario_service.set_business_profile(profile, current_user.id)
        
        return {
            "success": True,
            "message": f"Business profile actualizado a: {profile.value}",
            "business_profile": profile.value,
            "config": control_horario_service.config
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error estableciendo business profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
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
        if not control_horario_service.business_profile:
            await _get_control_horario_info(current_user, db)
        
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
        logger.error(f"Error obteniendo reportes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
