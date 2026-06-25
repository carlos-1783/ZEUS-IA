"""
AFRODITA flag safety v1 — lectura explícita de env con defaults seguros (false).
Soporta alias legacy y recuperación si el valor se pegó en otra variable (Railway).
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from core.afrodita_env_debug import resolve_afrodita_env

logger = logging.getLogger(__name__)

_WARNED_MISSING: set[str] = set()

CRITICAL_FLAG_NAMES = (
    "AFRODITA_EXECUTION_ENABLED",
    "AFRODITA_READ_ONLY_MODE",
)


def _warn_missing(name: str) -> None:
    if name not in _WARNED_MISSING:
        _WARNED_MISSING.add(name)
        logger.warning(
            "[AFRODITA_FLAGS] env var %s missing — defaulting to false",
            name,
        )


def reset_afrodita_flag_warnings() -> None:
    """Solo para tests — permite re-loggear warnings."""
    _WARNED_MISSING.clear()


def get_afrodita_safety_flags() -> Dict[str, Any]:
    resolved = resolve_afrodita_env()
    raw_execution = resolved["raw"]["AFRODITA_EXECUTION_ENABLED"]
    raw_readonly = resolved["raw"]["AFRODITA_READ_ONLY_MODE"]
    execution_source = resolved["resolution"]["AFRODITA_EXECUTION_ENABLED"]
    readonly_source = resolved["resolution"]["AFRODITA_READ_ONLY_MODE"]

    if execution_source == "missing":
        _warn_missing("AFRODITA_EXECUTION_ENABLED")
    if readonly_source == "missing":
        _warn_missing("AFRODITA_READ_ONLY_MODE")

    execution_enabled = bool(resolved["parsed"]["execution_enabled"])
    read_only_mode = bool(resolved["parsed"]["read_only"])
    writes_enabled = bool(resolved["parsed"]["writes_enabled"])
    flags_loaded = bool(resolved["flags_loaded"])

    if resolved.get("salvaged_from_misconfigured_env"):
        logger.error(
            "[AFRODITA_FLAGS] Flags recovered from a misconfigured env var — "
            "set AFRODITA_EXECUTION_ENABLED and AFRODITA_READ_ONLY_MODE as separate Railway variables"
        )

    return {
        "execution_enabled": execution_enabled,
        "read_only_mode": read_only_mode,
        "AFRODITA_EXECUTION_ENABLED": execution_enabled,
        "AFRODITA_READ_ONLY_MODE": read_only_mode,
        "flags_loaded": flags_loaded,
        "writes_enabled": writes_enabled,
        "flags_env_present": {
            "AFRODITA_EXECUTION_ENABLED": execution_source != "missing",
            "AFRODITA_READ_ONLY_MODE": readonly_source != "missing",
        },
        "env_debug": resolved,
        "resolution": resolved["resolution"],
        "salvaged_from_misconfigured_env": resolved.get("salvaged_from_misconfigured_env", False),
    }
