"""AFRODITA runtime env diagnostics — raw vs parsed flag values."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional


def parse_bool(value: Optional[str]) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in ("true", "1", "yes")


def get_env_debug() -> Dict[str, Any]:
    raw_execution = os.getenv("AFRODITA_EXECUTION_ENABLED")
    raw_readonly = os.getenv("AFRODITA_READ_ONLY_MODE")

    execution_enabled = parse_bool(raw_execution)
    read_only = parse_bool(raw_readonly)
    writes_enabled = execution_enabled and not read_only

    return {
        "raw": {
            "AFRODITA_EXECUTION_ENABLED": raw_execution,
            "AFRODITA_READ_ONLY_MODE": raw_readonly,
        },
        "parsed": {
            "execution_enabled": execution_enabled,
            "read_only": read_only,
            "writes_enabled": writes_enabled,
        },
    }
