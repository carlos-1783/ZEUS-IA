"""Analytics reales: ingresos, ventas, clientes (BD)."""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from services.analytics_service import build_analytics_summary

logger = logging.getLogger(__name__)
router = APIRouter()


def _analytics_safe_fallback(*, days: int = 30, error: str = "") -> Dict[str, Any]:
    return {
        "success": False,
        "status": "safe_fallback",
        "period_days": days,
        "error": error or None,
        "financial": {
            "total_revenue": 0,
            "sales_count": 0,
            "avg_ticket": 0,
            "cmr_payments_count": 0,
            "tpv_sales_count": 0,
        },
        "customers": {"active_total": 0},
        "sales_by_day": [],
        "activity_total": 0,
    }


@router.get("/summary")
async def analytics_summary(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Métricas financieras y operativas desde tpv_sales, CRM y activity_log."""
    try:
        return build_analytics_summary(db, current_user, days=days)
    except Exception as exc:
        logger.warning("analytics_summary failsafe: %s", exc, exc_info=True)
        return _analytics_safe_fallback(days=days, error=str(exc))
