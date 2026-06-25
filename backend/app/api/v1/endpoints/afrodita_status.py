"""AFRODITA truth status — single source for execution_mode (REAL | SIMULATED | ERROR)."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from core.afrodita_env_debug import get_env_debug
from services.afrodita_unified_control import get_global_status

router = APIRouter(prefix="/afrodita", tags=["afrodita"])


@router.get("/status")
def afrodita_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ = current_user
    env_debug = get_env_debug()
    payload = get_global_status(db)

    # Runtime assert: env not loaded → SIMULATED
    if env_debug["raw"]["AFRODITA_EXECUTION_ENABLED"] is None:
        payload["execution_mode"] = "SIMULATED"
        payload["system_default_mode"] = "SIMULATED"
    elif payload["writes_enabled"] and payload["db_connected"]:
        payload["execution_mode"] = "REAL"
        payload["system_default_mode"] = "REAL"

    payload["env_debug"] = env_debug
    payload["writes_enabled"] = bool(env_debug["parsed"]["writes_enabled"])
    return payload
