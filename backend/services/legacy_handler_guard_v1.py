"""Wrapper para handlers legacy — audita rutas sin sustituir lógica."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict

from app.models.agent_activity import AgentActivity
from services.zeus_core_guard_v1 import (
    SIMULATED_HANDLER_ACTIONS,
    closure_active,
    validate_critical_action,
)

logger = logging.getLogger(__name__)

HandlerFn = Callable[[AgentActivity], Dict[str, Any]]


def audit_legacy_handler_path(activity: AgentActivity) -> None:
    if not closure_active():
        return
    action = (activity.action_type or "").strip().lower()
    mode = "simulated" if action in SIMULATED_HANDLER_ACTIONS else "real"
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
        if closure_active() and (activity.action_type or "") in SIMULATED_HANDLER_ACTIONS:
            result = dict(result)
            result.setdefault("details_update", {})
            if isinstance(result["details_update"], dict):
                result["details_update"]["execution_mode"] = "simulated"
        return result

    return _wrapped
