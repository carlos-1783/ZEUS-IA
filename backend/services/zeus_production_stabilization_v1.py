"""ZEUS production stabilization v1 — safe defaults and validation."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)

FIX_ID = "zeus_production_stabilization_v1"
MODE = "safe_apply_patch"

RAILWAY_ENV_KEYS = (
    "AFRODITA_EXECUTION_ENABLED",
    "AFRODITA_READ_ONLY_MODE",
    "ZEUS_AGENT_ENABLED",
    "TEAMFLOW_ENABLED",
    "AFRODITA_OPS_ENABLED",
    "AFRODITA_OPS_READ_ONLY",
)


def stabilization_enabled() -> bool:
    return os.getenv("ZEUS_PRODUCTION_STABILIZATION", "true").lower() in ("true", "1", "yes")


def is_deployed_environment() -> bool:
    return bool(
        os.getenv("RAILWAY_ENVIRONMENT")
        or os.getenv("RAILWAY_SERVICE_NAME")
        or os.getenv("ENVIRONMENT", "").lower() in ("production", "staging")
    )


def production_execution_defaults() -> bool:
    """When true, missing AFRODITA flags default to REAL on deployed env."""
    return stabilization_enabled() and is_deployed_environment()


def validate_phase_1_env() -> Dict[str, Any]:
    from config.afrodita_flags_v1 import get_afrodita_safety_flags
    from app.core.config import settings

    flags = get_afrodita_safety_flags()
    checks = {
        "AFRODITA_EXECUTION_ENABLED": bool(flags.get("AFRODITA_EXECUTION_ENABLED")),
        "AFRODITA_READ_ONLY_MODE": bool(flags.get("AFRODITA_READ_ONLY_MODE")),
        "ZEUS_AGENT_ENABLED": bool(getattr(settings, "ZEUS_AGENT_ENABLED", True)),
        "TEAMFLOW_ENABLED": bool(getattr(settings, "TEAMFLOW_ENABLED", True)),
        "AFRODITA_OPS_ENABLED": bool(getattr(settings, "AFRODITA_OPS_ENABLED", False)),
        "AFRODITA_OPS_READ_ONLY": bool(getattr(settings, "AFRODITA_OPS_READ_ONLY", True)),
    }
    writes_enabled = bool(flags.get("writes_enabled"))
    execution_mode = "REAL" if writes_enabled else "SIMULATED"
    passed = (
        checks["AFRODITA_EXECUTION_ENABLED"]
        and not checks["AFRODITA_READ_ONLY_MODE"]
        and writes_enabled
    )
    return {
        "fix_id": FIX_ID,
        "phase": "phase_1_env_fix",
        "checks": checks,
        "writes_enabled": writes_enabled,
        "execution_mode": execution_mode,
        "passed": passed,
        "production_defaults": production_execution_defaults(),
    }


def log_startup_stabilization() -> Dict[str, Any]:
    report = validate_phase_1_env()
    level = logging.INFO if report["passed"] else logging.WARNING
    logger.log(
        level,
        "[ZEUS_STABILIZATION] phase_1 passed=%s execution_mode=%s writes_enabled=%s",
        report["passed"],
        report["execution_mode"],
        report["writes_enabled"],
    )
    if not report["passed"] and report.get("production_defaults"):
        logger.warning(
            "[ZEUS_STABILIZATION] Set Railway vars: %s",
            ", ".join(f"{k}=..." for k in RAILWAY_ENV_KEYS),
        )
    return report
