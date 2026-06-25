"""
AFRODITA flag safety v1 — lectura explícita de env con defaults seguros (false).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from core.afrodita_env_debug import get_env_debug, parse_bool

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
    raw_execution = os.environ.get("AFRODITA_EXECUTION_ENABLED")
    raw_readonly = os.environ.get("AFRODITA_READ_ONLY_MODE")

    if raw_execution is None:
        _warn_missing("AFRODITA_EXECUTION_ENABLED")
    if raw_readonly is None:
        _warn_missing("AFRODITA_READ_ONLY_MODE")

    execution_enabled = parse_bool(raw_execution)
    read_only_mode = parse_bool(raw_readonly)
    writes_enabled = execution_enabled and not read_only_mode

    flags_loaded = raw_execution is not None and raw_readonly is not None

    return {
        "execution_enabled": execution_enabled,
        "read_only_mode": read_only_mode,
        "AFRODITA_EXECUTION_ENABLED": execution_enabled,
        "AFRODITA_READ_ONLY_MODE": read_only_mode,
        "flags_loaded": flags_loaded,
        "writes_enabled": writes_enabled,
        "flags_env_present": {
            "AFRODITA_EXECUTION_ENABLED": raw_execution is not None,
            "AFRODITA_READ_ONLY_MODE": raw_readonly is not None,
        },
        "env_debug": get_env_debug(),
    }
