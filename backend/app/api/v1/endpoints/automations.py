"""Automation audit — read-only observability."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from services.zeus_automation_audit_v1 import get_automation_audit

router = APIRouter()


@router.get("/audit")
async def automation_audit(
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Últimas ejecuciones de automatizaciones + resumen por nombre (solo lectura)."""
    return get_automation_audit(db, current_user, limit=limit)
