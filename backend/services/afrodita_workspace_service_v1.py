"""
AFRODITA workspace RRHH v1 — conecta UI a company_employees, employee_schedules y register_checkin.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.company import UserCompany
from app.models.company_employee import CompanyEmployee
from app.models.time_tracking import EmployeeSchedule
from app.models.user import User
from services.afrodita_control_layer_v1 import (
    DAY_NAMES,
    can_execute_checkin,
    current_flags,
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
        "read_only": True,
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
        "executed": False,
        "disabled": True,
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
        return {
            "status": "dry_run",
            "executed": False,
            "message": (
                "Modo lectura: validación OK pero fichaje requiere "
                "AFRODITA_EXECUTION_ENABLED + READ_ONLY=false"
            ),
            **validation,
        }

    if code.upper().startswith(("ZEUS|", "ZEUSQR|")):
        flow = process_qr_scan(db, user, data=code)
    else:
        flow = process_nfc_scan(db, user, text=code, checkin_type="entrada")

    executed = bool(flow.get("executed", flow.get("success")))
    return {
        **flow,
        "executed": executed,
        "validation": validation,
        "entry_point": "register_checkin",
    }


def validate_qr_before_checkin(db: Session, user: User, code: str) -> Dict[str, Any]:
    """Pre-validación QR: frescura + empleado en BD."""
    from services.afrodita_control_layer_v1 import parse_zeuscheck_code

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
