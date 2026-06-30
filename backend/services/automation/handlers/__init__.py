"""
🤖 Automation Handlers
Selecciona el handler apropiado para cada agente y acción.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Any

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
from services.teamflow_real_handlers_v1 import (
    TEAMFLOW_REAL_ACTION_TYPES,
    handle_ads_campaign_builder,
    handle_contract_creator_rrhh,
    handle_contract_generator,
    handle_document_signed,
    handle_image_analyzer,
    handle_invoice_sent,
    handle_unmapped_no_fake,
)


def _normalize_agent_key(agent: str) -> str:
    key = (agent or "").strip().upper()
    if key == "ZEUS CORE":
        return "ZEUS"
    return key


HandlerType = Callable[[AgentActivity], Dict[str, object]]

# ZEUS internal only — critical TeamFlow actions use real handlers
GENERIC_INTERNAL_ACTION_TYPES = frozenset({
    "autonomo_paperwork_prepare",
    "pricing_review",
    "stripe_readiness_check",
    "daily_internal_log",
    "system_friction_detected",
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
        "image_analyzer": handle_image_analyzer,
        "ads_campaign_builder": handle_ads_campaign_builder,
    },
    "RAFAEL": {
        "task_assigned": handle_rafael_task,
        "invoice_sent": handle_invoice_sent,
    },
    "JUSTICIA": {
        "task_assigned": handle_justicia_task,
        "document_reviewed": handle_justicia_task,
        "compliance_check": handle_justicia_task,
        "contract_generator": handle_contract_generator,
        "document_signed": handle_document_signed,
    },
    "AFRODITA": {
        "task_assigned": handle_afrodita_task,
        "contract_creator_rrhh": handle_contract_creator_rrhh,
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
    if action_type in TEAMFLOW_REAL_ACTION_TYPES:
        return handle_unmapped_no_fake
    import logging

    logging.getLogger(__name__).warning(
        "[HANDLER] no real handler for agent=%s action=%s — failing closed",
        agent,
        action_type,
    )
    return handle_unmapped_no_fake


def scan_handler_coverage() -> Dict[str, Any]:
    """Audit TeamFlow critical actions — generic handler count must be 0."""
    from .generic_internal import handle_generic_internal

    generic_on_critical: List[str] = []
    critical_real: List[str] = []
    for agent, actions in HANDLER_MAP.items():
        for action, handler in actions.items():
            if action not in TEAMFLOW_REAL_ACTION_TYPES:
                continue
            label = f"{agent}:{action}"
            if handler is handle_generic_internal:
                generic_on_critical.append(label)
            else:
                critical_real.append(label)

    workflow_generic = 0
    try:
        from services.teamflow_engine import teamflow_engine

        for wf in teamflow_engine.list_workflows():
            for step in wf.get("steps") or []:
                action = step.get("action") or ""
                if action not in TEAMFLOW_REAL_ACTION_TYPES:
                    continue
                agent = step.get("agent") or ""
                handler = resolve_handler(agent, action)
                if handler is handle_generic_internal:
                    workflow_generic += 1
    except Exception:
        pass

    return {
        "generic_handlers_count": len(generic_on_critical) + workflow_generic,
        "generic_on_critical": generic_on_critical,
        "critical_actions_all_real": len(generic_on_critical) == 0 and workflow_generic == 0,
        "critical_real_handlers": critical_real,
        "teamflow_real_percentage": (
            100.0
            if len(generic_on_critical) == 0 and workflow_generic == 0
            else round(
                100.0
                * len(critical_real)
                / max(len(critical_real) + len(generic_on_critical) + workflow_generic, 1),
                1,
            )
        ),
    }

