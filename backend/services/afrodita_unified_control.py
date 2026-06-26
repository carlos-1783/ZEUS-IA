"""
AFRODITA unified control v1 — single global execution truth for all domains.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from config.afrodita_flags_v1 import get_afrodita_safety_flags
from services.afrodita_workspace_db_service_v1 import workspace_connection_status
from services.execution_mode_v1 import normalize_execution_mode

logger = logging.getLogger(__name__)

ExecutionMode = Literal["REAL", "SIMULATED", "ERROR"]
DataOrigin = Literal["backend", "user_input", "mock", "mixed"]

DAY_NAMES = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")


def probe_db_connected(db: Optional[Session]) -> bool:
    if db is None:
        return bool(getattr(settings, "DATABASE_URL", None))
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def writes_enabled() -> bool:
    safety = get_afrodita_safety_flags()
    return bool(safety["execution_enabled"] and not safety["read_only_mode"])


def current_flags() -> Dict[str, bool]:
    safety = get_afrodita_safety_flags()
    return {
        "AFRODITA_EXECUTION_ENABLED": bool(safety["AFRODITA_EXECUTION_ENABLED"]),
        "AFRODITA_READ_ONLY_MODE": bool(safety["AFRODITA_READ_ONLY_MODE"]),
        "execution_enabled": bool(safety["execution_enabled"]),
        "read_only_mode": bool(safety["read_only_mode"]),
        "AFRODITA_USE_REAL_EMPLOYEES": bool(getattr(settings, "AFRODITA_USE_REAL_EMPLOYEES", True)),
        "AFRODITA_USE_REAL_CHECKINS": bool(getattr(settings, "AFRODITA_USE_REAL_CHECKINS", True)),
        "AFRODITA_USE_REAL_SCHEDULES": bool(getattr(settings, "AFRODITA_USE_REAL_SCHEDULES", True)),
        "AFRODITA_WORKSPACE_ENABLED": bool(getattr(settings, "AFRODITA_WORKSPACE_ENABLED", True)),
        "AFRODITA_USE_ERP": bool(getattr(settings, "AFRODITA_USE_ERP", True)),
        "AFRODITA_USE_TPV": bool(getattr(settings, "AFRODITA_USE_TPV", True)),
        "AFRODITA_ENABLE_ROUTE_ENGINE": bool(getattr(settings, "AFRODITA_ENABLE_ROUTE_ENGINE", False)),
        "AFRODITA_ENABLE_STOCK_SYNC": bool(getattr(settings, "AFRODITA_ENABLE_STOCK_SYNC", False)),
    }


def resolve_execution_mode(*, db_connected: bool, writes_on: bool) -> ExecutionMode:
    if not db_connected:
        return "ERROR"
    if writes_on:
        return "REAL"
    return "SIMULATED"


def get_global_status(db: Optional[Session] = None) -> Dict[str, Any]:
    safety = get_afrodita_safety_flags()
    flags = current_flags()
    db_ok = probe_db_connected(db)
    execution_enabled = bool(safety["execution_enabled"])
    read_only_mode = bool(safety["read_only_mode"])
    enabled = execution_enabled and not read_only_mode

    if not db_ok:
        mode: ExecutionMode = "ERROR"
    elif enabled and db_ok:
        mode = "REAL"
    else:
        mode = "SIMULATED"

    return {
        "execution_mode": mode,
        "system_default_mode": mode,
        "writes_enabled": enabled,
        "db_connected": db_ok,
        "flags_loaded": bool(safety["flags_loaded"]),
        "execution_enabled": execution_enabled,
        "read_only_mode": read_only_mode,
        "AFRODITA_EXECUTION_ENABLED": execution_enabled,
        "AFRODITA_READ_ONLY_MODE": read_only_mode,
        "flags": flags,
        "flags_env_present": safety["flags_env_present"],
        "env_debug": safety.get("env_debug"),
        "resolution": safety.get("resolution"),
        "salvaged_from_misconfigured_env": safety.get("salvaged_from_misconfigured_env", False),
        "checkin_entry_point": "register_checkin",
        "employees_source": "company_employees",
        "schedules_source": "employee_schedules",
        "rrhh_api_prefix": "/api/v1/afrodita/rrhh/v1",
        "ops_api_prefix": "/api/v1/afrodita/ops/v1",
        "erp_api_path": "/api/v1/products",
        "tpv_api_path": "/api/v1/tpv/products",
        "inventory_precedence": "erp",
        "workspace": workspace_connection_status(db),
    }


def assert_can_write(db: Session) -> None:
    if not probe_db_connected(db):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "db_unavailable",
                "execution_mode": "ERROR",
                "message": "Base de datos no disponible",
            },
        )
    if not writes_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "writes_disabled",
                "execution_mode": "SIMULATED",
                "message": (
                    "Escritura deshabilitada. Configure AFRODITA_EXECUTION_ENABLED=true "
                    "y AFRODITA_READ_ONLY_MODE=false en el entorno."
                ),
            },
        )


def can_create_employee() -> bool:
    if not writes_enabled():
        return False
    return bool(current_flags()["AFRODITA_USE_REAL_EMPLOYEES"])


def can_execute_checkin() -> bool:
    if not writes_enabled():
        return False
    return bool(current_flags()["AFRODITA_USE_REAL_CHECKINS"])


def can_write_stock() -> bool:
    return writes_enabled()


def route_engine_available() -> bool:
    return writes_enabled()


def log_execution_attempt(
    *,
    domain: str,
    action: Optional[str],
    allowed: bool,
    actor_id: Optional[int] = None,
) -> None:
    g = get_global_status()
    logger.info(
        "[AFRODITA_UNIFIED] domain=%s action=%s mode=%s allowed=%s actor=%s",
        domain,
        action,
        g["execution_mode"],
        allowed,
        actor_id,
    )


def wrap_response(
    body: Dict[str, Any],
    *,
    db: Optional[Session],
    data_origin: DataOrigin,
    persisted: bool = False,
    dry_run: bool = False,
    read_only: bool = False,
) -> Dict[str, Any]:
    global_status = get_global_status(db)
    mode = global_status["execution_mode"]
    out = dict(body)

    if dry_run:
        out["success"] = False
        out["dry_run"] = True
        out["non_persistent"] = True
    elif persisted:
        out["success"] = bool(out.get("success", True))

    if read_only:
        real_execution = mode == "REAL"
    else:
        real_execution = mode == "REAL" and persisted and not dry_run

    return {
        **out,
        "execution_mode": mode,
        "standard_execution_mode": normalize_execution_mode(mode),
        "writes_enabled": global_status["writes_enabled"],
        "db_connected": global_status["db_connected"],
        "data_origin": data_origin,
        "real_execution": real_execution,
    }


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
