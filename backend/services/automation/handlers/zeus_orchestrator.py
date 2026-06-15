"""
Handlers reales ZEUS CORE — ejecutan zeus_orchestrator_handlers (CRM, campañas, analytics).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from app.db.session import SessionLocal
from app.models.agent_activity import AgentActivity
from app.models.user import User
from app.schemas.zeus_action import ZeusAction
from services import zeus_orchestrator_handlers as orch

logger = logging.getLogger(__name__)


def _user_from_activity(session, activity: AgentActivity) -> User | None:
    details = activity.details if isinstance(activity.details, dict) else {}
    uid = details.get("user_id")
    if uid:
        user = session.query(User).filter(User.id == int(uid)).first()
        if user:
            return user
    email = (activity.user_email or "").strip()
    if email:
        return session.query(User).filter(User.email == email).first()
    return session.query(User).filter(User.is_superuser.is_(True)).first()


def _action_from_activity(activity: AgentActivity, user: User) -> ZeusAction:
    details = activity.details if isinstance(activity.details, dict) else {}
    return ZeusAction(
        action_type=details.get("zeus_action_type") or "unknown",
        company_id=details.get("company_id"),
        user_id=user.id,
        payload=details.get("payload") or details,
        modules=list(details.get("modules") or []),
        requires_confirmation=bool(details.get("requires_confirmation", False)),
        confidence=float(details.get("confidence") or 0),
        raw_message=str(details.get("raw_message") or activity.action_description or ""),
    )


def _result_to_handler_dict(result: Any, *, handler_name: str) -> Dict[str, Any]:
    if hasattr(result, "model_dump"):
        data = result.model_dump()
    elif isinstance(result, dict):
        data = result
    else:
        data = {"message": str(result)}
    success = bool(data.get("success", True))
    return {
        "status": "completed" if success else "failed",
        "details_update": {
            "orchestrator": data,
            "executed": data.get("executed", True),
            "message": data.get("message"),
        },
        "metrics_update": data.get("metrics") or {},
        "notes": data.get("message") or "Acción orquestador ejecutada.",
        "executed_handler": handler_name,
    }


def handle_crm_customers_summary(activity: AgentActivity) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        user = _user_from_activity(session, activity)
        if not user:
            return {"status": "failed", "notes": "Usuario no encontrado.", "executed_handler": "ORCH_CRM_SUMMARY"}
        action = _action_from_activity(activity, user)
        action.action_type = "list_customers"
        result = orch.execute_list_customers(session, user, action)
        return _result_to_handler_dict(result, handler_name="ORCH_CRM_CUSTOMERS_SUMMARY")
    finally:
        session.close()


def handle_campaign_created(activity: AgentActivity) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        user = _user_from_activity(session, activity)
        if not user:
            return {"status": "failed", "notes": "Usuario no encontrado.", "executed_handler": "ORCH_CAMPAIGN_CREATE"}
        action = _action_from_activity(activity, user)
        preview = orch.preview_send_campaign(session, user, action)
        return {
            "status": "completed",
            "details_update": {"campaign_preview": preview},
            "metrics_update": {"customer_count": preview.get("customer_count", 0)},
            "notes": preview.get("message", "Campaña preparada."),
            "executed_handler": "ORCH_CAMPAIGN_CREATED",
        }
    finally:
        session.close()


def handle_campaign_sent(activity: AgentActivity) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        user = _user_from_activity(session, activity)
        if not user:
            return {"status": "failed", "notes": "Usuario no encontrado.", "executed_handler": "ORCH_CAMPAIGN_SENT"}
        action = _action_from_activity(activity, user)
        action.action_type = "send_campaign"
        result = asyncio.run(orch.execute_send_campaign(session, user, action))
        return _result_to_handler_dict(result, handler_name="ORCH_CAMPAIGN_SENT")
    finally:
        session.close()
