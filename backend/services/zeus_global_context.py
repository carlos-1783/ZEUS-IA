"""Contexto operativo compartido por ZEUS Core y todos los handlers del orquestador."""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.employee_work_session import EmployeeWorkSession
from app.models.user import User
from services.company_module_config import get_company_config_for_user
import services.crm_office_service as crm_svc


def build_global_context(db: Session, user: User) -> Dict[str, Any]:
    company_id = crm_svc.primary_company_id(db, user)
    cfg = get_company_config_for_user(db, user)
    customers = crm_svc.list_customers(db, user)
    with_email = sum(1 for c in customers if c.email and str(c.email).strip())

    active_session: Optional[Dict[str, Any]] = None
    ws = (
        db.query(EmployeeWorkSession)
        .filter(
            EmployeeWorkSession.user_id == user.id,
            EmployeeWorkSession.status == "active",
        )
        .order_by(EmployeeWorkSession.id.desc())
        .first()
    )
    if ws:
        active_session = {
            "id": ws.id,
            "employee_code": ws.employee_code,
            "status": ws.status,
            "opened_at": ws.opened_at.isoformat() if ws.opened_at else None,
            "company_id": ws.company_id,
        }

    return {
        "company_id": company_id,
        "user_id": user.id,
        "active_customers": {
            "total": len(customers),
            "with_email": with_email,
        },
        "active_session": active_session,
        "permissions": cfg.get("modules") or {},
        "company_type": cfg.get("company_type"),
        "company_name": cfg.get("company_name"),
    }


def enrich_chat_context(
    db: Session,
    user: User,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    ctx = dict(context or {})
    gc = build_global_context(db, user)
    if ctx.get("company_id") is None and gc.get("company_id") is not None:
        ctx["company_id"] = gc["company_id"]
    ctx["user_id"] = user.id
    ctx["zeus_global_context"] = gc
    return ctx


def attach_context_to_action_payload(
    action_payload: Dict[str, Any],
    global_context: Dict[str, Any],
) -> Dict[str, Any]:
    out = dict(action_payload)
    out["_zeus_context"] = global_context
    return out
