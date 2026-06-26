"""
ZEUS execution controller v1 — single source of truth for execution_mode and modules.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from services.afrodita_unified_control import get_global_status, writes_enabled
from services.zeus_data_pipeline_v1 import pipeline_definition

AGENT = "ZEUS_CORE"
VERSION = "v1_audit_deep"


def _module_mode(*, global_mode: str, can_read: bool, can_write: bool) -> str:
    if global_mode == "ERROR":
        return "ERROR"
    if can_write and can_read:
        return "REAL"
    if can_read:
        return "PARTIAL_REAL"
    return "SIMULATED"


def get_module_statuses(db: Optional[Session], global_status: Dict[str, Any]) -> Dict[str, Any]:
    flags = global_status.get("flags") or {}
    gmode = global_status.get("execution_mode", "SIMULATED")
    ws = global_status.get("workspace") or {}
    writes_on = bool(global_status.get("writes_enabled"))

    rrhh_read = bool(
        flags.get("AFRODITA_USE_REAL_EMPLOYEES")
        or flags.get("AFRODITA_USE_REAL_CHECKINS")
        or flags.get("AFRODITA_USE_REAL_SCHEDULES")
    )
    rrhh_write = writes_on and bool(
        flags.get("AFRODITA_USE_REAL_EMPLOYEES") or flags.get("AFRODITA_USE_REAL_CHECKINS")
    )

    ops_read = bool(flags.get("AFRODITA_USE_ERP") or flags.get("AFRODITA_USE_TPV"))
    ops_write = writes_on and ops_read

    ws_enabled = bool(ws.get("enabled"))
    ws_connected = bool(ws.get("connected"))
    ws_read = ws_enabled and ws_connected
    ws_write = ws_read and writes_on

    playbook_count = 0
    if db is not None and ws_read:
        try:
            from app.models.workspace_playbook import WorkspacePlaybook

            raw = (
                db.query(WorkspacePlaybook)
                .filter(WorkspacePlaybook.agent_name == "AFRODITA")
                .count()
            )
            playbook_count = int(raw) if isinstance(raw, int) else 0
        except Exception:
            playbook_count = 0

    if ws_read and playbook_count > 0:
        ws_status = "REAL_WITH_OUTPUT"
    elif ws_write:
        ws_status = "REAL"
    elif ws_read:
        ws_status = "EMPTY_REAL"
    elif ws_enabled:
        ws_status = "PARTIAL_REAL"
    else:
        ws_status = "SIMULATED"

    return {
        "rrhh": {
            "status": _module_mode(global_mode=gmode, can_read=rrhh_read, can_write=rrhh_write),
            "read": rrhh_read,
            "write": rrhh_write,
        },
        "ops": {
            "status": _module_mode(global_mode=gmode, can_read=ops_read, can_write=ops_write),
            "read": ops_read,
            "write": ops_write,
        },
        "workspace": {
            "status": ws_status,
            "read": ws_read,
            "write": ws_write,
            "playbook_count": playbook_count,
        },
    }


def get_execution_status(db: Optional[Session] = None) -> Dict[str, Any]:
    """Canonical ZEUS execution payload — all modules must derive from this."""
    global_status = get_global_status(db)
    modules = get_module_statuses(db, global_status)
    gmode = global_status["execution_mode"]
    simulation_layers = gmode != "REAL"

    connected_modules = [
        name
        for name, mod in modules.items()
        if mod.get("read") or mod.get("write")
    ]

    return {
        "agent": AGENT,
        "version": VERSION,
        "execution_mode": gmode,
        "writes_enabled": bool(global_status.get("writes_enabled")),
        "db_status": {
            "connected": bool(global_status.get("db_connected")),
            "flags_loaded": bool(global_status.get("flags_loaded")),
        },
        "connected_modules": connected_modules,
        "modules": modules,
        "simulation_layers_present": simulation_layers,
        "flag_consistency": "UNIFIED" if global_status.get("flags_loaded") else "DEGRADED",
        "pipeline": pipeline_definition(),
        "transaction_engine": "zeus_transaction_system_v1",
        "afrodita": global_status,
    }


def assert_execution_writes(db: Session) -> None:
    """Delegate write gate to unified control (single enforcement path)."""
    from services.afrodita_unified_control import assert_can_write

    assert_can_write(db)


def execution_writes_enabled() -> bool:
    return writes_enabled()
