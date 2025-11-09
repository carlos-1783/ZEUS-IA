"""
🤖 Automation Handlers
Selecciona el handler apropiado para cada agente y acción.
"""

from __future__ import annotations

from typing import Callable, Dict, Optional

from app.models.agent_activity import AgentActivity

from .perseo import handle_perseo_task
from .rafael import handle_rafael_task
from .justicia import handle_justicia_task
from .afrodita import handle_afrodita_task
from .zeus import handle_zeus_task
from .thalos import (
    handle_thalos_security_scan,
    handle_thalos_alerts,
    handle_thalos_backup,
)


HandlerType = Callable[[AgentActivity], Dict[str, object]]


HANDLER_MAP: Dict[str, Dict[str, HandlerType]] = {
    "PERSEO": {
        "task_assigned": handle_perseo_task,
    },
    "RAFAEL": {
        "task_assigned": handle_rafael_task,
    },
    "JUSTICIA": {
        "task_assigned": handle_justicia_task,
        "document_reviewed": handle_justicia_task,
        "compliance_check": handle_justicia_task,
    },
    "AFRODITA": {
        "task_assigned": handle_afrodita_task,
    },
    "ZEUS": {
        "coordination": handle_zeus_task,
        "task_delegated": handle_zeus_task,
    },
    "THALOS": {
        "security_scan": handle_thalos_security_scan,
        "task_assigned": handle_thalos_alerts,
        "backup_created": handle_thalos_backup,
    },
}


def resolve_handler(agent: str, action_type: str) -> Optional[HandlerType]:
    agent_handlers = HANDLER_MAP.get(agent.upper())
    if not agent_handlers:
        return None
    return agent_handlers.get(action_type)

