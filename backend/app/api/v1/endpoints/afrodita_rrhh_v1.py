"""AFRODITA RRHH v1 — dominio operativo (fichajes, empleados, turnos)."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from services.afrodita_finalization_v1 import rrhh_status_payload
from services.afrodita_unified_control import (
    assert_can_write,
    get_global_status,
    log_execution_attempt,
    wrap_response,
)
from services.afrodita_workspace_service_v1 import (
    create_company_employee,
    execute_qr_checkin,
    list_company_employees,
    list_employee_schedules,
)

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
    return {**get_global_status(db), "afrodita_finalization": rrhh_status_payload(db).get("afrodita_finalization"), "domain": "rrhh"}


@router.post("/checkin/qr")
def afrodita_rrhh_qr_checkin(
    request: QrCheckinRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    assert_can_write(db)
    log_execution_attempt(
        domain="qr_checkin",
        action="qr_check_in",
        allowed=True,
        actor_id=current_user.id,
    )
    result = execute_qr_checkin(db, current_user, request.qr_code.strip())
    checkin_id = result.get("checkin_id")
    if not checkin_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "write_failed",
                "execution_mode": "ERROR",
                "message": "Fichaje no persistido — falta checkin_id",
            },
        )
    from services.workspace_playbook_writer_v1 import write_rrhh_playbook

    write_rrhh_playbook(
        db,
        current_user,
        action="qr_check_in",
        title=f"Fichaje QR #{checkin_id}",
        payload={"checkin_id": checkin_id, "result": result},
    )
    db.commit()
    return wrap_response(
        {
            "success": True,
            "result": result,
            "checkin_id": int(checkin_id),
            "text": result.get("message", "Fichaje QR procesado"),
        },
        db=db,
        data_origin="backend",
        persisted=True,
    )


@router.post("/employees")
def afrodita_rrhh_create_employee(
    request: CreateEmployeeRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    assert_can_write(db)
    log_execution_attempt(
        domain="employee_manager",
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
    from services.workspace_playbook_writer_v1 import write_rrhh_playbook

    emp = body["employee"]
    write_rrhh_playbook(
        db,
        current_user,
        action="create_employee",
        title=f"Alta empleado {emp['full_name']}",
        payload=body,
    )
    db.commit()
    return wrap_response(
        {
            "success": True,
            **body,
            "employee_id": emp["id"],
        },
        db=db,
        data_origin="user_input",
        persisted=True,
    )


@router.get("/employees")
def afrodita_rrhh_employees(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    body = list_company_employees(db, current_user)
    return wrap_response(
        {"success": True, **body},
        db=db,
        data_origin="backend",
        read_only=True,
    )


@router.get("/schedules")
def afrodita_rrhh_schedules(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    body = list_employee_schedules(db, current_user)
    return wrap_response(
        {"success": True, **body},
        db=db,
        data_origin="backend",
        read_only=True,
    )


@router.post("/contract-draft")
def afrodita_rrhh_contract_draft(
    request: ContractDraftRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    assert_can_write(db)
    log_execution_attempt(
        domain="rrhh",
        action="contract_draft",
        allowed=True,
        actor_id=current_user.id,
    )
    from services.workspaces.afrodita_tools import create_rrhh_contract
    from services.contract_generator import generate_contract

    name = (request.employee_name or "").strip() or "Empleado"
    role = (request.role or "").strip() or "Puesto"
    contract = create_rrhh_contract(
        {
            "employee_name": name,
            "role": role,
            "salary": float(request.salary or 0),
            "contract_type": request.contract_type or "indefinido",
        }
    )
    legal = generate_contract(
        db,
        current_user,
        parties=[str(contract["clauses"][0]), str(contract["clauses"][1])],
        scope=f"Contrato laboral {request.contract_type or 'indefinido'}",
    )
    try:
        from services.zeus_cross_module_events_v1 import emit_cross_module_event

        emit_cross_module_event(
            db,
            current_user,
            "contract_rrhh_created",
            {"source": "contract_draft", "contract": contract, "legal": legal},
        )
    except Exception:
        pass

    from services.workspace_playbook_writer_v1 import write_rrhh_playbook

    write_rrhh_playbook(
        db,
        current_user,
        action="contract_draft",
        title=f"Contrato {name}",
        payload={"contract": contract, "legal_document": legal},
    )
    db.commit()
    return wrap_response(
        {
            "success": True,
            "contract": contract,
            "legal_document": legal,
            "text": f"Contrato laboral generado para {name} (doc {legal.get('document_id')})",
            "persisted": True,
        },
        db=db,
        data_origin="user_input",
        persisted=True,
    )
