"""RRHH contract draft — real persistence via JUSTICIA contract_generator."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.company_employee import CompanyEmployee
from app.models.user import User
from services.afrodita_unified_control import assert_can_write
from services.contract_generator import generate_contract
from services.workspace_deliverables import primary_company_id_for_user
from services.zeus_event_bus_v1 import emit_event


def _find_employee(
    db: Session,
    user: User,
    *,
    employee_name: str,
    employee_code: Optional[str] = None,
    employee_id: Optional[int] = None,
) -> CompanyEmployee:
    company_id = primary_company_id_for_user(db, user)
    if not company_id:
        raise HTTPException(status_code=404, detail="Usuario sin empresa asociada")

    if employee_id:
        row = (
            db.query(CompanyEmployee)
            .filter(
                CompanyEmployee.id == employee_id,
                CompanyEmployee.company_id == company_id,
                CompanyEmployee.is_active.is_(True),
            )
            .first()
        )
        if row:
            return row

    code = (employee_code or "").strip()
    if code:
        row = (
            db.query(CompanyEmployee)
            .filter(
                CompanyEmployee.company_id == company_id,
                CompanyEmployee.employee_code == code,
                CompanyEmployee.is_active.is_(True),
            )
            .first()
        )
        if row:
            return row

    name = (employee_name or "").strip()
    if len(name) >= 2:
        row = (
            db.query(CompanyEmployee)
            .filter(
                CompanyEmployee.company_id == company_id,
                CompanyEmployee.full_name.ilike(name),
                CompanyEmployee.is_active.is_(True),
            )
            .first()
        )
        if row:
            return row
        row = (
            db.query(CompanyEmployee)
            .filter(
                CompanyEmployee.company_id == company_id,
                CompanyEmployee.full_name.ilike(f"%{name}%"),
                CompanyEmployee.is_active.is_(True),
            )
            .first()
        )
        if row:
            return row

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "error": "employee_not_found",
            "message": "Empleado no encontrado — cree el empleado antes del contrato",
            "employee_name": employee_name,
            "employee_code": employee_code,
        },
    )


def create_rrhh_contract_draft(
    db: Session,
    user: User,
    *,
    employee_name: str,
    role: str = "",
    salary: float = 0,
    contract_type: str = "indefinido",
    employee_code: Optional[str] = None,
    employee_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Validate employee, generate contract in legal_documents, emit cross-module events."""
    assert_can_write(db)
    emp = _find_employee(
        db,
        user,
        employee_name=employee_name,
        employee_code=employee_code,
        employee_id=employee_id,
    )
    company_id = emp.company_id
    role_title = (role or emp.role_title or "Puesto").strip()
    scope = f"Contrato laboral {contract_type} — {role_title}"
    if salary > 0:
        scope = f"{scope} — salario ref. {salary}"

    legal = generate_contract(
        db,
        user,
        parties=[emp.full_name, "Empresa"],
        scope=scope,
        media_buying=False,
        company_id=company_id,
    )

    emit_event(
        db,
        user,
        event_name="contract_rrhh_created",
        source_module="AFRODITA",
        payload={
            "employee_id": emp.id,
            "employee_code": str(emp.employee_code),
            "employee_name": emp.full_name,
            "contract_type": contract_type,
            "legal_document": legal,
            "owner_agent": "AFRODITA",
        },
    )

    from services.teamflow_persistence_v1 import create_item

    handoff_content = {
        "event": "contract_rrhh_created",
        "document_id": legal.get("document_id"),
        "employee_name": emp.full_name,
        "employee_code": str(emp.employee_code),
        "role": role_title,
        "salary": salary,
        "legal_document": legal,
    }
    create_item(
        db,
        user,
        owner_agent="AFRODITA",
        source_agent="AFRODITA",
        target_agent="JUSTICIA",
        title=f"Contrato RRHH — {emp.full_name}",
        item_type="contract_rrhh",
        status="pending",
        content=handoff_content,
        company_id=company_id,
    )
    create_item(
        db,
        user,
        owner_agent="JUSTICIA",
        source_agent="AFRODITA",
        target_agent="JUSTICIA",
        title=f"Revisión legal — {emp.full_name}",
        item_type="contract_rrhh",
        status="pending",
        content=handoff_content,
        company_id=company_id,
    )

    return {
        "success": True,
        "contract_id": legal.get("document_id"),
        "document_id": legal.get("document_id"),
        "db_id": legal.get("db_id"),
        "employee": {
            "id": emp.id,
            "full_name": emp.full_name,
            "employee_code": str(emp.employee_code),
        },
        "legal_document": legal,
        "message": f"Contrato laboral generado para {emp.full_name}",
        "persisted": True,
        "real_execution": True,
    }
