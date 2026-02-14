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
from .zeus_launch import handle_zeus_launch_started
from .zeus_automation_readiness import handle_automation_readiness_evaluate
from .zeus_payroll_draft import handle_payroll_draft_generate
from .thalos import (
    handle_thalos_security_scan,
    handle_thalos_alerts,
    handle_thalos_backup,
)
from .generic_internal import handle_generic_internal, GENERIC_INTERNAL_HANDLER_NAME


HandlerType = Callable[[AgentActivity], Dict[str, object]]

# Action types that use GENERIC_INTERNAL_HANDLER (persist payload, no simulation)
# These are internal actions that need persistence but don't require external execution
GENERIC_INTERNAL_ACTION_TYPES = frozenset({
    # ZEUS internal
    "autonomo_paperwork_prepare",
    "pricing_review",
    "stripe_readiness_check",
    "daily_internal_log",
    "system_friction_detected",
    # RAFAEL critical (fiscal workflows)
    "invoice_sent",  # Invoice generation - requires real handler in future
    # JUSTICIA critical (legal workflows)
    "contract_generator",  # Contract generation - requires real handler in future
    "document_signed",  # Document signing - requires real handler in future
    # AFRODITA critical (HR workflows)
    "contract_creator_rrhh",  # HR contract creation - requires real handler in future
    # PERSEO critical (marketing workflows)
    "image_analyzer",  # Image analysis - requires real handler in future
    "ads_campaign_builder",  # Campaign builder - requires real handler in future
})

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
        "zeus_launch_started": handle_zeus_launch_started,
        "automation_readiness_evaluate": handle_automation_readiness_evaluate,
        "payroll_draft_generate": handle_payroll_draft_generate,
        "autonomo_paperwork_prepare": handle_generic_internal,
        "pricing_review": handle_generic_internal,
        "stripe_readiness_check": handle_generic_internal,
        "daily_internal_log": handle_generic_internal,
        "system_friction_detected": handle_generic_internal,
    },
    # Critical action types mapped to generic handler (will be blocked if not in GENERIC_INTERNAL_ACTION_TYPES)
    # These will use GENERIC_INTERNAL_HANDLER via resolve_handler fallback
    "THALOS": {
        "security_scan": handle_thalos_security_scan,
        "task_assigned": handle_thalos_alerts,
        "backup_created": handle_thalos_backup,
    },
}


def resolve_handler(agent: str, action_type: str) -> Optional[HandlerType]:
    agent_handlers = HANDLER_MAP.get(agent.upper())
    if agent_handlers and action_type in agent_handlers:
        return agent_handlers.get(action_type)
    if action_type in GENERIC_INTERNAL_ACTION_TYPES:
        return handle_generic_internal
    return None

