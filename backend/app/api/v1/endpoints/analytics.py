"""Analytics reales: ingresos, ventas, clientes (BD)."""

from typing import Any, Dict

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from services.analytics_service import build_analytics_summary

router = APIRouter()


@router.get("/summary")
async def analytics_summary(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Métricas financieras y operativas desde tpv_sales, CRM y activity_log."""
    return build_analytics_summary(db, current_user, days=days)
