"""
AFRODITA finalization v1 — separación de dominios RRHH / OPS / Workspace.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal

from fastapi import HTTPException, status

from services.afrodita_unified_control import current_flags, get_global_status

DomainId = Literal["rrhh", "ops", "workspace"]

DOMAIN_RULES: List[str] = [
    "workspace_no_executes_business",
    "rrhh_executes_real_operations",
    "ops_executes_real_operations",
]

DOMAIN_ROUTES: Dict[str, str] = {
    "rrhh": "/afrodita/rrhh",
    "ops": "/afrodita/ops",
    "workspace": "/workspaces",
}

RRHH_API_PREFIX = "/api/v1/afrodita/rrhh/v1"
OPS_API_PREFIX = "/api/v1/afrodita/ops/v1"

WORKSPACE_BLOCKED_MODULES = frozenset(
    {
        "facial_checkin",
        "qr_checkin",
        "employee_manager",
        "shift_generator",
        "contract",
    }
)


def finalization_payload() -> Dict[str, Any]:
    flags = current_flags()
    ws = {"enabled": flags.get("AFRODITA_WORKSPACE_ENABLED", True), "status": "CONNECTED"}
    rrhh_mode = "REAL" if flags.get("AFRODITA_USE_REAL_EMPLOYEES") else "PARTIAL"
    ops_mode = "REAL" if flags.get("AFRODITA_ENABLE_STOCK_SYNC") or flags.get("AFRODITA_OPS_ENABLED") else "PARTIAL"
    workspace_mode = "REAL" if ws["enabled"] else "ISOLATED"
    return {
        "system_id": "afrodita_finalization_v1",
        "mode": "safe_execution",
        "scope": "full_afrodita_stack",
        "domain_separation": {
            "rules": DOMAIN_RULES,
            "routes": {
                "/afrodita/rrhh": "AfroditaToolsPanel",
                "/afrodita/ops": "AfroditaOpsPanel",
                "/workspaces": "WorkspacePlaybooks",
            },
        },
        "rrhh_module": {
            "status": "ACTIVE",
            "api_prefix": RRHH_API_PREFIX,
            "checkin_service": "time_cost_engine_v1.register_checkin",
            "facial_checkin": "DISABLED",
        },
        "ops_module": {
            "status": "BOOTSTRAP_REAL",
            "api_prefix": OPS_API_PREFIX,
            "inventory": "REAL",
            "movements": "REAL",
            "warehouse": "NONE",
            "routes": "SIMULATED",
        },
        "workspace_module": {
            "status": workspace_mode,
            "rules": [
                "no_direct_business_execution",
                "playbooks_and_files_from_db",
            ],
            "files_api": "/api/v1/afrodita/workspace/files",
            "playbooks_api": "/api/v1/afrodita/workspace/playbooks",
        },
        "ui_tabs": [
            {"name": "RRHH", "component": "AfroditaToolsPanel", "status": rrhh_mode},
            {"name": "OPERACIONES", "component": "AfroditaOpsPanel", "status": ops_mode},
            {"name": "WORKSPACE", "component": "AfroditaWorkspacePanel", "status": workspace_mode},
        ],
        "anti_fake_rules": [
            "no_static_arrays",
            "no_workspace_json_as_source_of_truth",
            "no_fake_scores",
            "no_simulated_outputs_without_label",
        ],
        "phases_locked": {
            "phase_1": "COMPLETED",
            "phase_2": "COMPLETED",
            "phase_3": "READY",
        },
        "final_state": {
            "afrodita_rrhh": "REAL",
            "afrodita_ops": "REAL",
            "workspace": "ISOLATED",
            "system_integrity": "STABLE",
        },
        "flags": flags,
    }


def rrhh_status_payload(db=None) -> Dict[str, Any]:
    base = get_global_status(db)
    return {
        **base,
        "afrodita_finalization": finalization_payload(),
        "domain": "rrhh",
        "rrhh_api_prefix": RRHH_API_PREFIX,
    }


def assert_workspace_isolated(module: str) -> None:
    """Bloquea ejecución de negocio desde /workspaces/*."""
    if module not in WORKSPACE_BLOCKED_MODULES:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": "workspace_isolated",
            "system_id": "afrodita_finalization_v1",
            "module": module,
            "message": (
                "El workspace IA no ejecuta operaciones de negocio. "
                f"Use {RRHH_API_PREFIX} o {OPS_API_PREFIX}."
            ),
            "redirect_rrhh": RRHH_API_PREFIX,
            "redirect_ops": OPS_API_PREFIX,
        },
    )
