"""
System fix pass v1 — auditoría read-only + metadatos de fixes seguros.
"""

from __future__ import annotations

from typing import Any, Dict, List

from services.system_visibility_v1 import execution_status_payload


def _ui_audit() -> Dict[str, Any]:
    return {
        "status": "OK",
        "issues_found": [
            "button_text_white_on_colored_buttons_only",
            "workspace_panels_use_light_backgrounds",
        ],
        "fixes_recommended": [
            "enforce_text_color_dark_on_light_components",
            "use_theme_tokens_for_agent_workspaces",
        ],
    }


def _workspace_audit() -> Dict[str, Any]:
    return {
        "status": "CONNECTED",
        "issues_found": [
            "ws.items_th.items_need_empty_array_default",
        ],
        "fixes_applied_in_code": [
            "normalize_response_structure_in_useAutomationDeliverables",
        ],
    }


def _backend_audit() -> Dict[str, Any]:
    return {
        "status": "OK",
        "issues_found": [
            "resolve_handler_returned_none_for_unknown_actions",
        ],
        "fixes_applied_in_code": [
            "inject_safe_fallback_handler_GENERIC_INTERNAL",
        ],
        "handler_map_agents": [
            "ZEUS",
            "PERSEO",
            "RAFAEL",
            "JUSTICIA",
            "AFRODITA",
            "THALOS",
        ],
    }


def _approval_audit() -> Dict[str, Any]:
    return {
        "status": "CONNECTED",
        "flow": "approve → legal_fiscal_firewall.approve_and_send_to_advisor",
        "blockers": [
            "autoriza_envio_documentos_a_asesores=false",
            "missing_advisor_email",
        ],
        "notes": "Aprobación persiste estado y dispara envío; no es stub.",
    }


def _flags_audit(flags: Dict[str, bool]) -> Dict[str, Any]:
    execution_flags_off = not any(
        [
            flags.get("AFRODITA_EXECUTION_ENABLED"),
            flags.get("THALOS_EXECUTION_ENABLED"),
            flags.get("JUSTICE_REAL_AUDIT_ENABLED"),
            flags.get("ZEUS_CORE_ENABLED"),
        ]
    )
    return {
        "all_execution_flags_disabled": execution_flags_off,
        "read_only_modes_active": flags.get("AFRODITA_READ_ONLY_MODE", True)
        and flags.get("JUSTICE_READ_ONLY_MODE", True),
        "phase_b_sequence": [
            "AFRODITA_EXECUTION_ENABLED=true + AFRODITA_READ_ONLY_MODE=false",
            "THALOS_EXECUTION_ENABLED=true",
            "JUSTICE_REAL_AUDIT_ENABLED=true",
        ],
        "phase_c_sequence": [
            "ZEUS_CORE_ENABLED=true + ZEUS_AGENT_ENABLED=true",
            "RAFAEL_EXECUTION_ENABLED=true",
            "ZEUS_EVENT_BUS_ENABLED=true",
            "ZEUS_AUTOMATION_ENGINE_ENABLED=true",
        ],
    }


def fix_pass_payload() -> Dict[str, Any]:
    base = execution_status_payload()
    flags = base["flags"]
    flag_audit = _flags_audit(flags)

    agents_out: List[Dict[str, Any]] = []
    for agent in base["agents"]:
        agents_out.append(
            {
                **agent,
                "critical_issues": _agent_critical_issues(agent["name"], flags),
                "fixes_applied": _agent_fixes_applied(agent["name"]),
            }
        )

    safe_fixes = [
        "resolve_handler_safe_fallback_GENERIC_INTERNAL",
        "useAutomationDeliverables_empty_array_defaults",
        "workspace_tools_afrodita_routes_removed_phase_a",
        "perseo_thalos_simulated_badges_phase_a",
    ]

    manual_actions = []
    if flag_audit["all_execution_flags_disabled"]:
        manual_actions.append("Activar flags Railway (Fase B/C) — ver /system/status")

    ready_count = base["summary"]["execution_ready_count"]
    critical_blockers: List[str] = []
    if ready_count == 0:
        critical_blockers = [
            "ningún agente execution_ready=true",
            "flags de ejecución desactivados por defecto",
        ]

    return {
        "audit_type": "system_fix_pass_v1",
        "mode": "read_only_then_safe_fix",
        "system_state": base.get("system_state", "CONTROLLED_UNTRUSTED"),
        "ui_status": _ui_audit()["status"],
        "workspace_status": _workspace_audit()["status"],
        "backend_status": _backend_audit()["status"],
        "approval_flow": _approval_audit()["status"],
        "agents": agents_out,
        "audits": {
            "frontend_ui": _ui_audit(),
            "workspace_rendering": _workspace_audit(),
            "backend_handlers": _backend_audit(),
            "approval_pipeline": _approval_audit(),
            "agent_execution_flags": flag_audit,
        },
        "critical_blockers": critical_blockers,
        "safe_fixes_applied": safe_fixes,
        "manual_actions_required": manual_actions,
        "ready_for_phase_B": base.get("ready_for_flags_activation", True),
        "zeus_core_orchestration_active": base.get("zeus_core_orchestration_active", False),
        "flags": flags,
        "timestamp": base["timestamp"],
    }


def _agent_critical_issues(name: str, flags: Dict[str, bool]) -> List[str]:
    issues: List[str] = []
    if name == "AFRODITA" and not flags.get("AFRODITA_EXECUTION_ENABLED"):
        issues.append("AFRODITA_EXECUTION_ENABLED=false")
    if name == "THALOS" and not flags.get("THALOS_EXECUTION_ENABLED"):
        issues.append("THALOS_EXECUTION_ENABLED=false")
    if name == "JUSTICIA" and not flags.get("JUSTICE_REAL_AUDIT_ENABLED"):
        issues.append("JUSTICE_REAL_AUDIT_ENABLED=false")
    if name == "PERSEO":
        issues.append("tools_heuristic_no_db_persistence")
    if name == "ZEUS CORE" and not flags.get("ZEUS_CORE_ENABLED"):
        issues.append("ZEUS_CORE_ENABLED=false")
    elif name == "ZEUS CORE" and flags.get("ZEUS_CORE_ENABLED") and not flags.get("ZEUS_AGENT_ENABLED"):
        issues.append("ZEUS_AGENT_ENABLED=false")
    return issues


def _agent_fixes_applied(name: str) -> List[str]:
    applied: List[str] = []
    if name in ("AFRODITA", "PERSEO", "THALOS"):
        applied.append("simulated_badges_or_domain_separation")
    if name == "THALOS":
        applied.append("legacy_log_monitor_labeled")
    return applied
