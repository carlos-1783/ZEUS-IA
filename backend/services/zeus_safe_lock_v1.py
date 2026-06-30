"""
ZEUS safe lock v1 — progressive_safe execution truth checks (warn-only).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.core.config import settings
from config.afrodita_flags_v1 import get_afrodita_safety_flags
from core.afrodita_env_debug import scan_misconfigured_railway_env

logger = logging.getLogger(__name__)

LOCK_ID = "zeus_safe_lock_v1"
MODE = "progressive_safe"

REQUIRED_ENV = {
    "AFRODITA_EXECUTION_ENABLED": "true",
    "AFRODITA_READ_ONLY_MODE": "false",
    "ZEUS_AGENT_ENABLED": "true",
}
OPTIONAL_ENV = {
    "TEAMFLOW_ENABLED": "true",
    "AFRODITA_OPS_ENABLED": "true",
    "AFRODITA_OPS_READ_ONLY": "false",
}
TEAMFLOW_ENDPOINTS = (
    "/api/v1/teamflow/list",
    "/api/v1/teamflow/create",
    "/api/v1/teamflow/update",
    "/api/v1/teamflow/audit",
)


def _env_raw(name: str) -> Optional[str]:
    return os.environ.get(name)


def _env_matches(name: str, expected: str) -> bool:
    raw = _env_raw(name)
    if raw is None:
        return False
    return raw.strip().lower() == expected.lower()


def _warn(warnings: List[Dict[str, Any]], code: str, message: str, *, module: str = "ZEUS_CORE") -> None:
    entry = {"code": code, "message": message, "module": module, "severity": "warning"}
    warnings.append(entry)
    logger.warning("[ZEUS_SAFE_LOCK] %s — %s", code, message)


def _check_env(warnings: List[Dict[str, Any]]) -> Dict[str, Any]:
    results: Dict[str, Any] = {"required": {}, "optional": {}}
    for name, expected in REQUIRED_ENV.items():
        raw = _env_raw(name)
        ok = _env_matches(name, expected)
        results["required"][name] = {"expected": expected, "actual": raw, "ok": ok}
        if raw is None:
            _warn(warnings, f"env_missing_{name}", f"{name} not set (expected {expected})")
        elif not ok:
            _warn(warnings, f"env_mismatch_{name}", f"{name}={raw!r} expected {expected!r}")
    for name, expected in OPTIONAL_ENV.items():
        raw = _env_raw(name)
        ok = raw is None or _env_matches(name, expected)
        results["optional"][name] = {"expected": expected, "actual": raw, "ok": ok}
        if raw is not None and not ok:
            _warn(warnings, f"env_optional_{name}", f"{name}={raw!r} expected {expected!r}", module="OPS")
    return results


def _check_teamflow(db: Optional[Session], warnings: List[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "migration": "0041",
        "tables_present": False,
        "endpoints": list(TEAMFLOW_ENDPOINTS),
        "teamflow_enabled": bool(getattr(settings, "TEAMFLOW_ENABLED", True)),
    }
    if db is not None:
        try:
            tables = inspect(db.get_bind()).get_table_names()
            out["tables_present"] = "teamflow_items" in tables and "teamflow_events" in tables
        except Exception as exc:
            out["inspect_error"] = str(exc)
    if not out["tables_present"]:
        _warn(warnings, "teamflow_migration_0041", "teamflow_items/teamflow_events tables missing", module="TEAMFLOW")
    if not out["teamflow_enabled"]:
        _warn(warnings, "teamflow_disabled", "TEAMFLOW_ENABLED is not true", module="TEAMFLOW")
    return out


def _check_execution_soft(warnings: List[Dict[str, Any]], execution: Dict[str, Any]) -> None:
    flags = get_afrodita_safety_flags()
    if not flags.get("AFRODITA_EXECUTION_ENABLED"):
        _warn(warnings, "execution_disabled", "AFRODITA_EXECUTION_ENABLED != true")
    if flags.get("AFRODITA_READ_ONLY_MODE"):
        _warn(warnings, "read_only_active", "AFRODITA_READ_ONLY_MODE == true")
    if not getattr(settings, "ZEUS_AGENT_ENABLED", True):
        _warn(warnings, "zeus_agent_disabled", "ZEUS_AGENT_ENABLED != true")

    mode = execution.get("execution_mode")
    writes = execution.get("writes_enabled")
    if mode != "REAL":
        _warn(warnings, "execution_mode_not_real", f"execution_mode={mode!r} (expected REAL)")
    if not writes:
        _warn(warnings, "writes_disabled", "writes_enabled is not true")

    misconfig = scan_misconfigured_railway_env()
    if misconfig.get("count"):
        _warn(
            warnings,
            "env_injection_error",
            f"env vars may be concatenated: {misconfig.get('hits', [])}",
        )


def run_safe_lock(
    db: Optional[Session] = None,
    *,
    execution_status: Optional[Dict[str, Any]] = None,
    log_warnings: bool = True,
) -> Dict[str, Any]:
    """Run progressive_safe checks. Never blocks — warnings only."""
    warnings: List[Dict[str, Any]] = []

    env_report = _check_env(warnings)
    teamflow_report = _check_teamflow(db, warnings)

    execution = execution_status or {}
    if execution:
        _check_execution_soft(warnings, execution)
    else:
        _check_execution_soft(warnings, {"execution_mode": "UNKNOWN", "writes_enabled": False})

    verified_real = (
        execution.get("execution_mode") == "REAL" and bool(execution.get("writes_enabled")) is True
    )

    report = {
        "lock_id": LOCK_ID,
        "mode": MODE,
        "block_on_inconsistency": False,
        "log_inconsistencies": log_warnings,
        "ui_show_real_only_if_verified": True,
        "verified_real": verified_real,
        "warnings": warnings,
        "warning_count": len(warnings),
        "env_validation": env_report,
        "teamflow": teamflow_report,
        "execution_source_of_truth": {
            "endpoint": "/api/v1/zeus/status",
            "required_fields": ["execution_mode", "writes_enabled", "modules"],
            "present": bool(execution),
        },
        "safe_transition": {
            "next_step": "zeus_partial_lock_v1",
            "ready": len(warnings) == 0,
        },
    }
    return report


def log_startup_safe_lock() -> Dict[str, Any]:
    """Startup hook — soft enforcement via warning logs."""
    flags = get_afrodita_safety_flags()
    execution = {
        "execution_mode": "REAL" if flags.get("writes_enabled") else "SIMULATED",
        "writes_enabled": bool(flags.get("writes_enabled")),
    }
    report = run_safe_lock(db=None, execution_status=execution, log_warnings=True)
    logger.info(
        "[ZEUS_SAFE_LOCK] startup verified_real=%s warnings=%s",
        report["verified_real"],
        report["warning_count"],
    )
    return report
