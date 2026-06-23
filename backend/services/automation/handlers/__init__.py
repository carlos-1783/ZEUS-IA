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
from .thalos_v1 import (
    handle_thalos_v1_alert,
    handle_thalos_v1_backup,
    handle_thalos_v1_block,
    handle_thalos_v1_cashflow,
    handle_thalos_v1_detect,
    handle_thalos_v1_monitor,
)
from .generic_internal import handle_generic_internal, GENERIC_INTERNAL_HANDLER_NAME
from .zeus_orchestrator import (
    handle_campaign_created,
    handle_campaign_sent,
    handle_crm_customers_summary,
)


def _normalize_agent_key(agent: str) -> str:
    key = (agent or "").strip().upper()
    if key == "ZEUS CORE":
        return "ZEUS"
    return key


HandlerType = Callable[[AgentActivity], Dict[str, object]]

# Action types that use GENERIC_INTERNAL_HANDLER
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
    "ZEUS": {
        "coordination": handle_zeus_task,
        "task_delegated": handle_zeus_task,
        "crm_customers_summary": handle_crm_customers_summary,
        "campaign_sent": handle_campaign_sent,
        "zeus_launch_started": handle_zeus_launch_started,
        "automation_readiness_evaluate": handle_automation_readiness_evaluate,
        "payroll_draft_generate": handle_payroll_draft_generate,
        "autonomo_paperwork_prepare": handle_generic_internal,
        "pricing_review": handle_generic_internal,
        "stripe_readiness_check": handle_generic_internal,
        "daily_internal_log": handle_generic_internal,
        "system_friction_detected": handle_generic_internal,
    },
    "ZEUS CORE": {
        "coordination": handle_zeus_task,
        "task_delegated": handle_zeus_task,
        "crm_customers_summary": handle_crm_customers_summary,
        "campaign_sent": handle_campaign_sent,
        "zeus_launch_started": handle_zeus_launch_started,
        "automation_readiness_evaluate": handle_automation_readiness_evaluate,
        "payroll_draft_generate": handle_payroll_draft_generate,
    },
    "PERSEO": {
        "task_assigned": handle_perseo_task,
        "campaign_created": handle_campaign_created,
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
    "THALOS": {
        "security_scan": handle_thalos_security_scan,
        "task_assigned": handle_thalos_alerts,
        "backup_created": handle_thalos_backup,
        # THALOS v1 — acciones reales (paralelas, no sustituyen legacy)
        "detect_suspicious_activity": handle_thalos_v1_detect,
        "scan_security_logs": handle_thalos_v1_detect,
        "audit_cashflow_anomaly": handle_thalos_v1_cashflow,
        "trigger_backup": handle_thalos_v1_backup,
        "block_user": handle_thalos_v1_block,
        "alert_admin": handle_thalos_v1_alert,
        "security_monitor": handle_thalos_v1_monitor,
    },
}


def resolve_handler(agent: str, action_type: str) -> HandlerType:
    normalized = _normalize_agent_key(agent)
    for key in (normalized, (agent or "").strip().upper()):
        agent_handlers = HANDLER_MAP.get(key)
        if agent_handlers and action_type in agent_handlers:
            return agent_handlers[action_type]
    if action_type in GENERIC_INTERNAL_ACTION_TYPES:
        return handle_generic_internal
    # Safe fallback — evita blocked_missing_handler (system_fix_pass_v1)
    import logging

    logging.getLogger(__name__).warning(
        "[HANDLER] safe fallback %s for agent=%s action=%s",
        GENERIC_INTERNAL_HANDLER_NAME,
        agent,
        action_type,
    )
    return handle_generic_internal

