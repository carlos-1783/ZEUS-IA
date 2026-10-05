"""
Handlers reales ZEUS CORE — ejecutan zeus_orchestrator_handlers (CRM, campañas, analytics).
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.db.session import SessionLocal
from app.models.agent_activity import AgentActivity
from app.models.user import User
from app.schemas.zeus_action import ZeusAction
from services import zeus_orchestrator_handlers as orch

logger = logging.getLogger(__name__)


def _user_from_activity(session, activity: AgentActivity) -> User | None:
    """Usuario de la actividad resuelto por el SERVIDOR.

    J3b: `/activities/log` fija siempre `user_email` desde el usuario autenticado, asi que ese
    es el dato fiable. `details.user_id` lo puede escribir el cliente: si hay email, un
    user_id que no coincida con el usuario del email se ignora (nunca se actua con el tenant
    de otro usuario). Solo se acepta `details.user_id` cuando la actividad no trae email
    (origen interno del servidor)."""
    details = activity.details if isinstance(activity.details, dict) else {}
    email = (activity.user_email or "").strip()
    if email:
        user = session.query(User).filter(User.email == email).first()
        uid = details.get("user_id")
        if user is not None and uid not in (None, "") and str(uid) != str(user.id):
            logger.warning(
                "activity %s: details.user_id=%s ignorado (el usuario de la actividad es %s)",
                getattr(activity, "id", None), uid, user.id,
            )
        return user
    uid = details.get("user_id")
    if uid:
        try:
            user = session.query(User).filter(User.id == int(uid)).first()
        except (TypeError, ValueError):
            user = None
        if user:
            return user
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
    """J3b: una actividad encolada NUNCA envia la campana por si misma.

    El envio a terceros solo ocurre via zeus_pending_approvals (preview -> confirmacion del
    mismo usuario -> execute_approval). Este handler no recibe esa prueba de aprobacion de
    forma verificable (details lo escribe el cliente), asi que bloquea sin enviar ni duplicar
    el envio: la ejecucion legitima ya ocurre en execute_approval."""
    logger.warning(
        "campaign_sent activity=%s bloqueada: requiere aprobacion en zeus_pending_approvals",
        getattr(activity, "id", None),
    )
    return {
        "status": "blocked_requires_approval",
        "details_update": {
            "executed": False,
            "blocked_requires_approval": True,
            "message": "El envio de campanas requiere vista previa y confirmacion (zeus_pending_approvals).",
        },
        "notes": "Bloqueada: el envio de campanas solo se ejecuta tras una aprobacion del propio usuario.",
        "executed_handler": "ORCH_CAMPAIGN_SENT_BLOCKED",
    }
