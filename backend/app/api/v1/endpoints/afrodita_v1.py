"""AFRODITA v1 API — control layer, empleados y turnos (lectura)."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from services.afrodita_control_layer_v1 import global_status_payload, wrap_response
from services.afrodita_workspace_service_v1 import list_company_employees, list_employee_schedules

router = APIRouter(prefix="/afrodita/v1", tags=["afrodita-v1"])


@router.get("/status")
def afrodita_v1_status(
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    return global_status_payload()


@router.get("/employees")
def afrodita_v1_employees(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    body = list_company_employees(db, current_user)
    return wrap_response(
        {"success": True, **body},
        "employee_manager",
        data_origin="backend",
        real_execution=True,
        ui_badge="REAL",
    )


@router.get("/schedules")
def afrodita_v1_schedules(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    body = list_employee_schedules(db, current_user)
    real = bool(body.get("schedules"))
    return wrap_response(
        {"success": True, **body},
        "shift_generator",
        data_origin="backend",
        real_execution=real,
        ui_badge="REAL" if real else "SIMULADO",
    )
