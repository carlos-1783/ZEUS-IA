"""
AFRODITA control layer v1 — estado REAL / SIMULADO / PARCIAL en workspace RRHH.

Non-destructive overlay: flags + metadata; no modifica time_cost_engine.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional, Tuple

from app.core.config import settings
from services.execution_mode_v1 import normalize_execution_mode

logger = logging.getLogger(__name__)

ExecutionMode = Literal["SIMULATION", "READ_ONLY", "REAL_ACTIVE"]
DataOrigin = Literal["backend", "user_input", "mock", "mixed"]

MODULE_UI_BADGE: Dict[str, str] = {
    "facial_checkin": "NONE",
    "qr_checkin": "PARCIAL",
    "employee_manager": "REAL",
    "shift_generator": "PARTIAL",
    "contract": "SIMULADO",
    "status": "REAL",
}

DAY_NAMES = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")


@dataclass
class ControlMetadata:
    execution_mode: ExecutionMode
    data_origin: DataOrigin
    real_execution: bool
    module: str
    ui_badge: str
    flags: Dict[str, bool]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_mode": self.execution_mode,
            "data_origin": self.data_origin,
            "real_execution": self.real_execution,
            "module": self.module,
            "ui_badge": self.ui_badge,
            "flags": self.flags,
        }


def current_flags() -> Dict[str, bool]:
    return {
        "AFRODITA_EXECUTION_ENABLED": bool(getattr(settings, "AFRODITA_EXECUTION_ENABLED", False)),
        "AFRODITA_READ_ONLY_MODE": bool(getattr(settings, "AFRODITA_READ_ONLY_MODE", True)),
        "AFRODITA_USE_REAL_EMPLOYEES": bool(getattr(settings, "AFRODITA_USE_REAL_EMPLOYEES", True)),
        "AFRODITA_USE_REAL_CHECKINS": bool(getattr(settings, "AFRODITA_USE_REAL_CHECKINS", True)),
        "AFRODITA_USE_REAL_SCHEDULES": bool(getattr(settings, "AFRODITA_USE_REAL_SCHEDULES", False)),
    }


def resolve_execution_mode(module: str) -> ExecutionMode:
    flags = current_flags()
    if flags["AFRODITA_EXECUTION_ENABLED"] and not flags["AFRODITA_READ_ONLY_MODE"]:
        if module == "qr_checkin" and flags["AFRODITA_USE_REAL_CHECKINS"]:
            return "REAL_ACTIVE"
    if flags["AFRODITA_READ_ONLY_MODE"] or module in ("employee_manager", "shift_generator", "status"):
        return "READ_ONLY"
    return "SIMULATION"


def can_execute_checkin() -> bool:
    f = current_flags()
    return (
        f["AFRODITA_EXECUTION_ENABLED"]
        and f["AFRODITA_USE_REAL_CHECKINS"]
        and not f["AFRODITA_READ_ONLY_MODE"]
    )


def log_execution_attempt(
    *,
    module: str,
    action: Optional[str],
    allowed: bool,
    actor_id: Optional[int] = None,
) -> None:
    logger.info(
        "[AFRODITA_CONTROL] module=%s action=%s mode=%s allowed=%s actor=%s",
        module,
        action,
        resolve_execution_mode(module),
        allowed,
        actor_id,
    )


def build_metadata(
    module: str,
    *,
    data_origin: DataOrigin,
    real_execution: Optional[bool] = None,
    ui_badge: Optional[str] = None,
) -> ControlMetadata:
    mode = resolve_execution_mode(module)
    if real_execution is None:
        real_execution = mode == "REAL_ACTIVE" or (
            mode == "READ_ONLY" and module in ("employee_manager", "shift_generator", "status")
        )
    return ControlMetadata(
        execution_mode=mode,
        data_origin=data_origin,
        real_execution=real_execution,
        module=module,
        ui_badge=ui_badge or MODULE_UI_BADGE.get(module, "SIMULADO"),
        flags=current_flags(),
    )


def wrap_response(
    body: Dict[str, Any],
    module: str,
    *,
    data_origin: DataOrigin,
    real_execution: Optional[bool] = None,
    ui_badge: Optional[str] = None,
) -> Dict[str, Any]:
    meta = build_metadata(
        module,
        data_origin=data_origin,
        real_execution=real_execution,
        ui_badge=ui_badge,
    )
    return {
        **body,
        "execution_mode": meta.execution_mode,
        "standard_execution_mode": normalize_execution_mode(meta.execution_mode),
        "data_origin": meta.data_origin,
        "real_execution": meta.real_execution,
        "afrodita_control": meta.to_dict(),
    }


def global_status_payload() -> Dict[str, Any]:
    flags = current_flags()
    if flags["AFRODITA_EXECUTION_ENABLED"] and not flags["AFRODITA_READ_ONLY_MODE"]:
        default_mode: ExecutionMode = "REAL_ACTIVE"
    elif flags["AFRODITA_READ_ONLY_MODE"]:
        default_mode = "READ_ONLY"
    else:
        default_mode = "SIMULATION"

    return wrap_response(
        {
            "system_default_mode": default_mode,
            **flags,
            "module_badges": MODULE_UI_BADGE,
            "checkin_entry_point": "register_checkin",
            "employees_source": "company_employees",
            "schedules_source": "employee_schedules",
            "facial_checkin": "DISABLED",
            "rrhh_api_prefix": "/api/v1/afrodita/rrhh/v1",
            "legacy_preserved": True,
        },
        "status",
        data_origin="backend",
        real_execution=False,
    )


def parse_zeuscheck_code(code: str) -> Optional[Dict[str, Any]]:
    raw = (code or "").strip()
    if not raw.upper().startswith("ZEUSCHECK|"):
        return None
    parts = raw.split("|")
    return {
        "raw": raw,
        "employee_id": parts[1].strip() if len(parts) > 1 else None,
        "timestamp": parts[2].strip() if len(parts) > 2 else None,
    }


def _parse_timestamp(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    try:
        normalized = ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def validate_qr_freshness(code: str, max_minutes: int = 5) -> Tuple[bool, str]:
    """Valida frescura de timestamp en ZEUSCHECK (max 5 min por defecto)."""
    parsed = parse_zeuscheck_code(code)
    if not parsed:
        return True, "not_zeuscheck"
    ts_raw = parsed.get("timestamp")
    if not ts_raw:
        return False, "missing_timestamp"
    dt = _parse_timestamp(ts_raw)
    if not dt:
        return False, "invalid_timestamp"
    age = (datetime.now(timezone.utc) - dt).total_seconds() / 60.0
    if age > max_minutes:
        return False, f"timestamp_stale_{age:.1f}min"
    if age < -max_minutes:
        return False, "timestamp_future"
    return True, "ok"
