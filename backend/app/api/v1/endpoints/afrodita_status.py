"""AFRODITA truth status — single source for execution_mode (REAL | SIMULATED | ERROR)."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from core.afrodita_env_debug import scan_misconfigured_railway_env
from services.afrodita_unified_control import get_global_status
from services.zeus_execution_controller_v1 import get_execution_status

router = APIRouter(prefix="/afrodita", tags=["afrodita"])


@router.get("/status")
def afrodita_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ = current_user
    payload = get_global_status(db)
    zeus = get_execution_status(db)
    env_debug = payload.get("env_debug") or {}
    payload["env_debug"] = env_debug
    payload["railway_env_audit"] = scan_misconfigured_railway_env()
    payload["zeus_modules"] = zeus["modules"]
    payload["zeus_execution_mode"] = zeus["execution_mode"]
    return payload
