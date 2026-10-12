"""Wrapper para handlers legacy — audita rutas sin sustituir lógica."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict

from app.models.agent_activity import AgentActivity
from services.zeus_core_guard_v1 import closure_active, validate_critical_action

logger = logging.getLogger(__name__)

HandlerFn = Callable[[AgentActivity], Dict[str, Any]]


def handler_execution_mode(activity: AgentActivity) -> str:
    """Modo segun el handler que REALMENTE se va a ejecutar (Fase 2).

    Antes se usaba una lista fija SIMULATED_HANDLER_ACTIONS desfasada: marcaba como
    "simulated" handlers reales (invoice_sent, contract_generator...) y no detectaba los
    que no hacian nada. Ahora: "no_real_logic" si la accion cae en el handler explicito
    sin logica, "no_handler" si no hay handler real, "real" en otro caso.
    """
    from services.automation.handlers import resolve_handler
    from services.automation.handlers.no_real_logic import handle_no_real_logic
    from services.teamflow_real_handlers_v1 import handle_unmapped_no_fake

    handler = resolve_handler(activity.agent_name or "", activity.action_type or "")
    if handler is handle_no_real_logic:
        return "no_real_logic"
    if handler is handle_unmapped_no_fake:
        return "no_handler"
    return "real"


def audit_legacy_handler_path(activity: AgentActivity) -> None:
    if not closure_active():
        return
    action = (activity.action_type or "").strip().lower()
    mode = handler_execution_mode(activity)
    validate_critical_action(
        "agents",
        action or "unknown",
        actor_email=activity.user_email,
        layer="agent",
        payload={
            "agent_name": activity.agent_name,
            "activity_id": activity.id,
            "execution_mode": mode,
            "legacy_path": True,
        },
    )
    logger.info(
        "[LEGACY_GUARD] agent=%s action=%s mode=%s activity_id=%s",
        activity.agent_name,
        action,
        mode,
        activity.id,
    )


def wrap_legacy_handler(handler: HandlerFn) -> HandlerFn:
    """Decorador no destructivo: audita antes de ejecutar handler legacy."""

    def _wrapped(activity: AgentActivity) -> Dict[str, Any]:
        audit_legacy_handler_path(activity)
        result = handler(activity)
        mode = handler_execution_mode(activity)
        if closure_active() and mode != "real":
            result = dict(result)
            result.setdefault("details_update", {})
            if isinstance(result["details_update"], dict):
                result["details_update"]["execution_mode"] = mode
        return result

    return _wrapped
