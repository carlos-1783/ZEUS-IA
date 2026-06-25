"""AFRODITA truth status — single source for execution_mode (REAL | SIMULATED | ERROR)."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from services.afrodita_unified_control import get_global_status

router = APIRouter(prefix="/afrodita", tags=["afrodita"])


@router.get("/status")
def afrodita_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ = current_user
    return get_global_status(db)
