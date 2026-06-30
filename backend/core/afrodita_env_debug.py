"""AFRODITA runtime env diagnostics — raw vs parsed flag values with Railway salvage."""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

EXECUTION_ENV_KEYS = (
    "AFRODITA_EXECUTION_ENABLED",
    "AFRODITA_RH_AGENT_ENABLED",  # legacy name in ZEUS_IA_ENV_VARIABLES_COMPLETE.md
)

READ_ONLY_ENV_KEYS = ("AFRODITA_READ_ONLY_MODE",)

_EMBEDDED_ENV_RE = re.compile(
    r"(AFRODITA_[A-Z0-9_]+)=(true|false|1|0|yes|no)",
    re.IGNORECASE,
)


def parse_bool(value: Optional[str]) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in ("true", "1", "yes", "t")


def salvage_embedded_env(env_var_name: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Recover KEY=value accidentally pasted into another Railway env var
    (e.g. STATIC_DIR=/data/static\"AFRODITA_EXECUTION_ENABLED=true).
    """
    direct = os.environ.get(env_var_name)
    if direct is not None:
        return direct, None

    needle = f"{env_var_name}="
    for source_name, val in os.environ.items():
        if not val or needle not in val:
            continue
        idx = val.find(needle)
        rest = val[idx + len(needle) :]
        for delim in ('"', "'", "\n", "\r", " ", "\t"):
            if delim in rest:
                rest = rest.split(delim, 1)[0]
        rest = rest.strip().rstrip(",;")
        if rest:
            logger.warning(
                "[AFRODITA_FLAGS] salvaged %s=%s from env var %s — fix Railway config",
                env_var_name,
                rest,
                source_name,
            )
            return rest, source_name
    return None, None


def _resolve_raw(keys: tuple[str, ...], canonical: str) -> Tuple[Optional[str], str]:
    for key in keys:
        raw = os.environ.get(key)
        if raw is not None:
            return raw, f"env:{key}"

    salvaged, source = salvage_embedded_env(canonical)
    if salvaged is not None:
        return salvaged, f"salvaged:{source}"

    return None, "missing"


def resolve_afrodita_env() -> Dict[str, Any]:
    raw_execution, execution_source = _resolve_raw(EXECUTION_ENV_KEYS, "AFRODITA_EXECUTION_ENABLED")
    raw_readonly, readonly_source = _resolve_raw(READ_ONLY_ENV_KEYS, "AFRODITA_READ_ONLY_MODE")

    execution_enabled = parse_bool(raw_execution)
    read_only = parse_bool(raw_readonly)
    writes_enabled = execution_enabled and not read_only

    flags_loaded = execution_source != "missing" and readonly_source != "missing"

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
        "resolution": {
            "AFRODITA_EXECUTION_ENABLED": execution_source,
            "AFRODITA_READ_ONLY_MODE": readonly_source,
        },
        "flags_loaded": flags_loaded,
        "salvaged_from_misconfigured_env": execution_source.startswith("salvaged:")
        or readonly_source.startswith("salvaged:"),
    }


def get_env_debug() -> Dict[str, Any]:
    return resolve_afrodita_env()


def scan_misconfigured_railway_env() -> Dict[str, Any]:
    """Surface env vars that contain embedded AFRODITA_* assignments (Railway typo)."""
    issues: list[Dict[str, str]] = []
    for name, val in os.environ.items():
        if not val or name in EXECUTION_ENV_KEYS or name in READ_ONLY_ENV_KEYS:
            continue
        for match in _EMBEDDED_ENV_RE.finditer(val):
            issues.append(
                {
                    "host_var": name,
                    "embedded": f"{match.group(1)}={match.group(2)}",
                    "hint": f"Move {match.group(1)} to its own Railway variable",
                }
            )
    return {"misconfigured_env_vars": issues, "count": len(issues)}
