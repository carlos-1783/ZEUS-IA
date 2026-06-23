"""AFRODITA RRHH v1 — dominio operativo (fichajes, empleados, turnos)."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from services.afrodita_control_layer_v1 import log_execution_attempt, wrap_response
from services.afrodita_finalization_v1 import rrhh_status_payload
from services.afrodita_workspace_service_v1 import (
    create_company_employee,
    execute_qr_checkin,
    list_company_employees,
    list_employee_schedules,
)
from services.workspaces.afrodita_tools import create_rrhh_contract

router = APIRouter(prefix="/afrodita/rrhh/v1", tags=["afrodita-rrhh-v1"])


class QrCheckinRequest(BaseModel):
    qr_code: str = Field(..., min_length=1)


class ContractDraftRequest(BaseModel):
    employee_name: str = ""
    role: str = ""
    salary: float = 0
    contract_type: str = "indefinido"


class CreateEmployeeRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255)
    employee_code: str = Field(..., min_length=2, max_length=80)
    role_title: str = Field(default="", max_length=100)
    phone: str = Field(default="", max_length=32)
    hourly_rate: float = Field(default=0.0, ge=0)


@router.get("/status")
def afrodita_rrhh_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ = current_user
    return rrhh_status_payload(db)


@router.post("/checkin/qr")
def afrodita_rrhh_qr_checkin(
    request: QrCheckinRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    log_execution_attempt(
        module="qr_checkin",
        action="qr_check_in",
        allowed=True,
        actor_id=current_user.id,
    )
    result = execute_qr_checkin(db, current_user, request.qr_code.strip())
    dry_run = bool(result.get("dry_run"))
    real_exec = bool(result.get("checkin_id")) and not dry_run
    return wrap_response(
        {"success": True, "result": result, "text": result.get("message", "Fichaje QR procesado")},
        "qr_checkin",
        data_origin="backend",
        real_execution=real_exec,
        dry_run=dry_run,
    )


@router.post("/employees")
def afrodita_rrhh_create_employee(
    request: CreateEmployeeRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    log_execution_attempt(
        module="employee_manager",
        action="create_employee",
        allowed=True,
        actor_id=current_user.id,
    )
    body = create_company_employee(
        db,
        current_user,
        full_name=request.full_name,
        employee_code=request.employee_code,
        role_title=request.role_title or None,
        phone=request.phone or None,
        hourly_rate=request.hourly_rate,
    )
    db.commit()
    return wrap_response(
        {"success": True, **body},
        "employee_manager",
        data_origin="user_input",
        real_execution=True,
    )


@router.get("/employees")
def afrodita_rrhh_employees(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    body = list_company_employees(db, current_user)
    return wrap_response(
        {"success": True, **body},
        "employee_manager",
        data_origin="backend",
        real_execution=True,
    )


@router.get("/schedules")
def afrodita_rrhh_schedules(
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
    )


@router.post("/contract-draft")
def afrodita_rrhh_contract_draft(
    request: ContractDraftRequest,
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    result = create_rrhh_contract(request.model_dump())
    return wrap_response(
        {
            "success": True,
            "result": result,
            "text": "Borrador de contrato generado (sin validez legal).",
        },
        "contract",
        data_origin="user_input",
        real_execution=False,
        dry_run=True,
    )
