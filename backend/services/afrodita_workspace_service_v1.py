"""
AFRODITA workspace RRHH v1 — conecta UI a company_employees, employee_schedules y register_checkin.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.company import UserCompany
from app.models.company_employee import CompanyEmployee
from app.models.time_tracking import EmployeeSchedule
from app.models.user import User
from services.afrodita_unified_control import (
    DAY_NAMES,
    can_create_employee,
    can_execute_checkin,
    current_flags,
    log_execution_attempt,
    validate_qr_freshness,
)
from services.workspace_deliverables import primary_company_id_for_user


def _company_ids_for_user(db: Session, user: User) -> List[int]:
    rows = db.query(UserCompany.company_id).filter(UserCompany.user_id == user.id).all()
    return [int(r[0]) for r in rows]


def employee_exists(db: Session, *, company_id: int, employee_code: str) -> bool:
    return (
        db.query(CompanyEmployee.id)
        .filter(
            CompanyEmployee.company_id == company_id,
            CompanyEmployee.employee_code == str(employee_code),
            CompanyEmployee.is_active.is_(True),
        )
        .first()
        is not None
    )


def list_company_employees(db: Session, user: User) -> Dict[str, Any]:
    flags = current_flags()
    if not flags["AFRODITA_USE_REAL_EMPLOYEES"]:
        return {
            "employees": [],
            "count": 0,
            "source": "disabled",
            "read_only": True,
        }

    company_ids = _company_ids_for_user(db, user)
    if not company_ids:
        return {"employees": [], "count": 0, "source": "company_employees", "read_only": True}

    rows = (
        db.query(CompanyEmployee)
        .filter(
            CompanyEmployee.company_id.in_(company_ids),
            CompanyEmployee.is_active.is_(True),
        )
        .order_by(CompanyEmployee.full_name.asc())
        .all()
    )
    employees = [
        {
            "id": r.id,
            "employee_code": str(r.employee_code),
            "full_name": r.full_name,
            "role_title": r.role_title or "",
            "company_id": r.company_id,
            "phone": r.phone,
            "source": r.source or "database",
        }
        for r in rows
    ]
    return {
        "employees": employees,
        "count": len(employees),
        "source": "company_employees",
        "read_only": not can_create_employee(),
    }


def _employee_to_dict(row: CompanyEmployee) -> Dict[str, Any]:
    return {
        "id": row.id,
        "employee_code": str(row.employee_code),
        "full_name": row.full_name,
        "role_title": row.role_title or "",
        "company_id": row.company_id,
        "phone": row.phone,
        "source": row.source or "database",
    }


def create_company_employee(
    db: Session,
    user: User,
    *,
    full_name: str,
    employee_code: str,
    role_title: Optional[str] = None,
    phone: Optional[str] = None,
    hourly_rate: Optional[float] = None,
) -> Dict[str, Any]:
    """Inserta fila real en company_employees — sin mock ni plantillas."""
    if not can_create_employee():
        raise HTTPException(
            status_code=403,
            detail=(
                "Creación de empleados requiere AFRODITA_EXECUTION_ENABLED=true "
                "y AFRODITA_READ_ONLY_MODE=false"
            ),
        )

    flags = current_flags()
    if not flags["AFRODITA_USE_REAL_EMPLOYEES"]:
        raise HTTPException(status_code=503, detail="AFRODITA_USE_REAL_EMPLOYEES=false")

    company_id = primary_company_id_for_user(db, user)
    if not company_id:
        raise HTTPException(status_code=404, detail="Usuario sin empresa asociada")

    name = (full_name or "").strip()
    code = (employee_code or "").strip()
    if len(name) < 2:
        raise HTTPException(status_code=422, detail="full_name requerido (mín. 2 caracteres)")
    if len(code) < 2:
        raise HTTPException(status_code=422, detail="employee_code requerido (mín. 2 caracteres)")

    dup = (
        db.query(CompanyEmployee.id)
        .filter(
            CompanyEmployee.company_id == company_id,
            CompanyEmployee.employee_code == code,
        )
        .first()
    )
    if dup:
        raise HTTPException(status_code=409, detail=f"employee_code {code} ya existe en la empresa")

    emp = CompanyEmployee(
        company_id=company_id,
        full_name=name[:255],
        role_title=(role_title or "").strip()[:100] or None,
        employee_code=code[:80],
        phone=(phone or "").strip()[:32] or None,
        hourly_rate=float(hourly_rate or 0.0),
        is_active=True,
        source="afrodita_rrhh_v1",
    )
    db.add(emp)
    db.flush()
    db.refresh(emp)

    log_execution_attempt(
        domain="rrhh",
        action="create_employee",
        allowed=True,
        actor_id=user.id,
    )

    return {
        "employee": _employee_to_dict(emp),
        "message": f"Empleado {emp.full_name} creado ({emp.employee_code}).",
    }


def list_employee_schedules(db: Session, user: User) -> Dict[str, Any]:
    flags = current_flags()
    if not flags["AFRODITA_USE_REAL_SCHEDULES"]:
        return {
            "schedules": [],
            "count": 0,
            "source": "employee_schedules",
            "read_only": True,
            "note": "AFRODITA_USE_REAL_SCHEDULES=false — activar flag para lectura real.",
        }

    company_ids = _company_ids_for_user(db, user)
    if not company_ids:
        return {"schedules": [], "count": 0, "source": "employee_schedules", "read_only": True}

    emp_codes = {
        str(r.employee_code)
        for r in db.query(CompanyEmployee.employee_code)
        .filter(
            CompanyEmployee.company_id.in_(company_ids),
            CompanyEmployee.is_active.is_(True),
        )
        .all()
    }
    if not emp_codes:
        return {"schedules": [], "count": 0, "source": "employee_schedules", "read_only": True}

    rows = (
        db.query(EmployeeSchedule)
        .filter(
            EmployeeSchedule.user_id == user.id,
            EmployeeSchedule.employee_id.in_(list(emp_codes)),
            EmployeeSchedule.is_active.is_(True),
        )
        .order_by(EmployeeSchedule.employee_id.asc(), EmployeeSchedule.day_of_week.asc())
        .all()
    )
    schedules = [
        {
            "employee_id": str(r.employee_id),
            "day_of_week": r.day_of_week,
            "day_name": DAY_NAMES[r.day_of_week] if 0 <= r.day_of_week < 7 else str(r.day_of_week),
            "start_time": r.start_time,
            "end_time": r.end_time,
            "shift_type": r.shift_type,
            "location": r.location,
            "break_start": r.break_start,
            "break_duration": r.break_duration,
        }
        for r in rows
    ]
    return {
        "schedules": schedules,
        "count": len(schedules),
        "source": "employee_schedules",
        "read_only": True,
    }


def execute_face_checkin(db: Session, user: User, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Deshabilitado en afrodita_finalization_v1 — sin motor biométrico."""
    _ = db, user, payload
    return {
        "disabled": True,
        "dry_run": True,
        "reason": "no_biometric_engine",
        "ui_method": "face",
        "message": "Fichaje facial deshabilitado. Use fichaje QR en dominio RRHH.",
        "redirect": "/api/v1/afrodita/rrhh/v1/checkin/qr",
    }


def execute_qr_checkin(db: Session, user: User, code: str) -> Dict[str, Any]:
    """Fichaje QR real vía scan_flow → register_checkin cuando flags lo permiten."""
    from services.scan_flow_service_v1 import process_nfc_scan, process_qr_scan

    validation = validate_qr_before_checkin(db, user, code)

    if not can_execute_checkin():
        from services.afrodita_unified_control import assert_can_write

        assert_can_write(db)

    log_execution_attempt(
        domain="rrhh",
        action="register_checkin",
        allowed=True,
        actor_id=user.id,
    )

    if code.upper().startswith(("ZEUS|", "ZEUSQR|")):
        flow = process_qr_scan(db, user, data=code)
    else:
        flow = process_nfc_scan(db, user, text=code, checkin_type="entrada")

    session = flow.get("session") if isinstance(flow.get("session"), dict) else {}
    checkin_id = flow.get("checkin_id") or session.get("checkin_id")
    persisted = bool(flow.get("executed", flow.get("success"))) and bool(checkin_id)

    if not persisted:
        raise HTTPException(
            status_code=500,
            detail="Fichaje no persistido en time_cost_checkins pese a ejecución habilitada",
        )

    return {
        **flow,
        "checkin_id": int(checkin_id),
        "status": "executed",
        "validation": validation,
        "entry_point": "register_checkin",
        "message": flow.get("message") or f"Fichaje registrado (checkin_id={checkin_id}).",
    }


def validate_qr_before_checkin(db: Session, user: User, code: str) -> Dict[str, Any]:
    """Pre-validación QR: frescura + empleado en BD."""
    from services.afrodita_unified_control import parse_zeuscheck_code

    flags = current_flags()
    fresh_ok, fresh_reason = validate_qr_freshness(code)
    info: Dict[str, Any] = {"freshness_ok": fresh_ok, "freshness_reason": fresh_reason}

    zeus = parse_zeuscheck_code(code)
    if zeus and zeus.get("employee_id"):
        cid = primary_company_id_for_user(db, user)
        info["employee_id"] = zeus["employee_id"]
        info["employee_exists"] = bool(
            cid and employee_exists(db, company_id=cid, employee_code=str(zeus["employee_id"]))
        )
    else:
        info["employee_exists"] = None

    if flags["AFRODITA_USE_REAL_CHECKINS"] and zeus:
        if not fresh_ok:
            raise HTTPException(
                status_code=422,
                detail=f"QR ZEUSCHECK inválido: {fresh_reason} (máx 5 min)",
            )
        if info.get("employee_exists") is False:
            raise HTTPException(
                status_code=404,
                detail=f"Empleado {zeus.get('employee_id')} no existe en company_employees",
            )

    info["execution_allowed"] = can_execute_checkin()
    return info
