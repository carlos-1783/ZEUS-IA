"""
AFRODITA flag safety v1 — lectura explícita de env con defaults seguros (false).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)

_WARNED_MISSING: set[str] = set()
_BOOL_TRUE = frozenset({"true", "1", "yes", "t"})

CRITICAL_FLAG_NAMES = (
    "AFRODITA_EXECUTION_ENABLED",
    "AFRODITA_READ_ONLY_MODE",
)


def _read_bool_env(name: str) -> Tuple[bool, bool]:
    """Devuelve (valor, presente_en_entorno). Si falta → false + warning."""
    raw = os.environ.get(name)
    if raw is None:
        if name not in _WARNED_MISSING:
            _WARNED_MISSING.add(name)
            logger.warning(
                "[AFRODITA_FLAGS] env var %s missing — defaulting to false",
                name,
            )
        return False, False
    return raw.strip().lower() in _BOOL_TRUE, True


def reset_afrodita_flag_warnings() -> None:
    """Solo para tests — permite re-loggear warnings."""
    _WARNED_MISSING.clear()


def get_afrodita_safety_flags() -> Dict[str, Any]:
    exec_val, exec_loaded = _read_bool_env("AFRODITA_EXECUTION_ENABLED")
    ro_val, ro_loaded = _read_bool_env("AFRODITA_READ_ONLY_MODE")
    flags_loaded = exec_loaded and ro_loaded
    writes_enabled = bool(flags_loaded and exec_val and not ro_val)
    return {
        "execution_enabled": exec_val,
        "read_only_mode": ro_val,
        "AFRODITA_EXECUTION_ENABLED": exec_val,
        "AFRODITA_READ_ONLY_MODE": ro_val,
        "flags_loaded": flags_loaded,
        "writes_enabled": writes_enabled,
        "flags_env_present": {
            "AFRODITA_EXECUTION_ENABLED": exec_loaded,
            "AFRODITA_READ_ONLY_MODE": ro_loaded,
        },
    }
