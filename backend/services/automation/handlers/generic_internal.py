"""
GENERIC_INTERNAL_HANDLER
Fallback handler for internal action types: persists full payload to activity, marks executed_internal.
No simulation: real write, auditable.
"""

from __future__ import annotations

from typing import Any, Dict

from app.models.agent_activity import AgentActivity

GENERIC_INTERNAL_HANDLER_NAME = "GENERIC_INTERNAL_HANDLER"


def handle_generic_internal(activity: AgentActivity) -> Dict[str, Any]:
    """
    Write full payload to agent_activities (details), mark status executed_internal.
    Emits audit trail; UI can show activity movement.
    """
    payload = activity.details if isinstance(activity.details, dict) else {}
    if not payload:
        payload = {"action_type": activity.action_type, "agent": activity.agent_name}

    return {
        "status": "executed_internal",
        "details_update": {
            **payload,
            "executed_handler": GENERIC_INTERNAL_HANDLER_NAME,
        },
        "metrics_update": {"executed_handler": GENERIC_INTERNAL_HANDLER_NAME},
        "notes": f"Internal action {activity.action_type} persisted (GENERIC_INTERNAL_HANDLER).",
        "executed_handler": GENERIC_INTERNAL_HANDLER_NAME,
    }
