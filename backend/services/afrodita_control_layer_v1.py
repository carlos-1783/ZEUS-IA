"""
AFRODITA control layer v1 — estado REAL | SIMULATED desde backend (sin capa simulada en UI).

Non-destructive overlay: flags + metadata; no modifica time_cost_engine.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from config.afrodita_flags_v1 import get_afrodita_safety_flags
from services.execution_mode_v1 import normalize_execution_mode

logger = logging.getLogger(__name__)

TruthExecutionMode = Literal["REAL", "SIMULATED"]
ExecutionMode = Literal["REAL", "SIMULATED"]
DataOrigin = Literal["backend", "user_input", "mock", "mixed"]

MODULE_UI_BADGE: Dict[str, str] = {
    "facial_checkin": "NONE",
    "qr_checkin": "REAL",
    "employee_manager": "REAL",
    "shift_generator": "REAL",
    "contract": "REAL",
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
    safety = get_afrodita_safety_flags()
    return {
        "AFRODITA_EXECUTION_ENABLED": bool(safety["AFRODITA_EXECUTION_ENABLED"]),
        "AFRODITA_READ_ONLY_MODE": bool(safety["AFRODITA_READ_ONLY_MODE"]),
        "AFRODITA_USE_REAL_EMPLOYEES": bool(getattr(settings, "AFRODITA_USE_REAL_EMPLOYEES", True)),
        "AFRODITA_USE_REAL_CHECKINS": bool(getattr(settings, "AFRODITA_USE_REAL_CHECKINS", True)),
        "AFRODITA_USE_REAL_SCHEDULES": bool(getattr(settings, "AFRODITA_USE_REAL_SCHEDULES", False)),
    }


def writes_enabled() -> bool:
    return bool(get_afrodita_safety_flags()["writes_enabled"])


def probe_db_connected(db: Session) -> bool:
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def resolve_truth_execution_mode(*, real_execution: bool = False, dry_run: bool = False) -> TruthExecutionMode:
    if dry_run or not real_execution:
        return "SIMULATED"
    return "REAL"


def resolve_execution_mode(module: str) -> ExecutionMode:
    flags = current_flags()
    if writes_enabled():
        if module == "qr_checkin" and flags["AFRODITA_USE_REAL_CHECKINS"]:
            return "REAL"
        if module == "employee_manager" and flags["AFRODITA_USE_REAL_EMPLOYEES"]:
            return "REAL"
        if module in ("shift_generator", "contract", "status"):
            return "REAL"
    return "SIMULATED"


def afrodita_truth_status_payload(db: Session) -> Dict[str, Any]:
    safety = get_afrodita_safety_flags()
    flags = current_flags()
    enabled = bool(safety["writes_enabled"])
    db_ok = probe_db_connected(db)
    mode: TruthExecutionMode = "REAL" if enabled and db_ok else "SIMULATED"
    return {
        "execution_mode": mode,
        "db_connected": db_ok,
        "writes_enabled": enabled,
        "flags_loaded": bool(safety["flags_loaded"]),
        "execution_enabled": bool(safety["execution_enabled"]),
        "read_only_mode": bool(safety["read_only_mode"]),
        "AFRODITA_EXECUTION_ENABLED": bool(safety["AFRODITA_EXECUTION_ENABLED"]),
        "AFRODITA_READ_ONLY_MODE": bool(safety["AFRODITA_READ_ONLY_MODE"]),
        "flags": flags,
        "flags_env_present": safety["flags_env_present"],
        "module_badges": {
            mod: ("REAL" if enabled else "SIMULATED")
            for mod in MODULE_UI_BADGE
            if mod != "facial_checkin"
        },
        "checkin_entry_point": "register_checkin",
        "employees_source": "company_employees",
        "schedules_source": "employee_schedules",
        "rrhh_api_prefix": "/api/v1/afrodita/rrhh/v1",
    }


def can_create_employee() -> bool:
    if not writes_enabled():
        return False
    f = current_flags()
    return bool(f["AFRODITA_USE_REAL_EMPLOYEES"])


def can_execute_checkin() -> bool:
    if not writes_enabled():
        return False
    f = current_flags()
    return bool(f["AFRODITA_USE_REAL_CHECKINS"])


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
    dry_run: bool = False,
) -> ControlMetadata:
    if real_execution is None:
        real_execution = resolve_execution_mode(module) == "REAL" and not dry_run
    mode = resolve_truth_execution_mode(real_execution=real_execution, dry_run=dry_run)
    badge = ui_badge or ("REAL" if mode == "REAL" else "SIMULATED")
    if module == "facial_checkin":
        badge = "NONE"
    return ControlMetadata(
        execution_mode=mode,
        data_origin=data_origin,
        real_execution=real_execution,
        module=module,
        ui_badge=badge,
        flags=current_flags(),
    )


def wrap_response(
    body: Dict[str, Any],
    module: str,
    *,
    data_origin: DataOrigin,
    real_execution: Optional[bool] = None,
    ui_badge: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    meta = build_metadata(
        module,
        data_origin=data_origin,
        real_execution=real_execution,
        ui_badge=ui_badge,
        dry_run=dry_run,
    )
    return {
        **body,
        "execution_mode": meta.execution_mode,
        "standard_execution_mode": normalize_execution_mode(meta.execution_mode),
        "data_origin": meta.data_origin,
        "real_execution": meta.real_execution,
        "afrodita_control": meta.to_dict(),
    }


def global_status_payload(db: Optional[Session] = None) -> Dict[str, Any]:
    safety = get_afrodita_safety_flags()
    flags = current_flags()
    enabled = bool(safety["writes_enabled"])
    db_ok = probe_db_connected(db) if db is not None else bool(settings.DATABASE_URL)
    default_mode: ExecutionMode = "REAL" if enabled and db_ok else "SIMULATED"

    return wrap_response(
        {
            "system_default_mode": default_mode,
            "db_connected": db_ok,
            "writes_enabled": enabled,
            "flags_loaded": bool(safety["flags_loaded"]),
            "execution_enabled": bool(safety["execution_enabled"]),
            "read_only_mode": bool(safety["read_only_mode"]),
            **flags,
            "module_badges": {
                mod: ("REAL" if enabled else "SIMULATED")
                for mod in MODULE_UI_BADGE
            },
            "checkin_entry_point": "register_checkin",
            "employees_source": "company_employees",
            "schedules_source": "employee_schedules",
            "facial_checkin": "DISABLED",
            "rrhh_api_prefix": "/api/v1/afrodita/rrhh/v1",
        },
        "status",
        data_origin="backend",
        real_execution=enabled and db_ok,
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
