"""
ZEUS core metrics v1 — revenue, staff_cost, product_cost (datos reales BD).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.employee_work_session import EmployeeWorkSession
from app.models.erp import TPVProduct
from app.models.fiscal import TPVSale
from app.models.user import User
from services.analytics_service import build_analytics_summary
from services.cashflow_ledger_service import get_balance, get_summary
import services.crm_office_service as crm_svc


def get_core_metrics(
    db: Session,
    *,
    user: User,
    company_id: Optional[int] = None,
    days: int = 30,
) -> Dict[str, Any]:
    cid = company_id or crm_svc.primary_company_id(db, user)
    analytics = build_analytics_summary(db, user, days=days)
    revenue = float((analytics.get("financial") or {}).get("total_revenue") or 0)

    staff_cost = 0.0
    if cid:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        staff_cost = float(
            db.query(func.coalesce(func.sum(EmployeeWorkSession.total_cost), 0.0))
            .filter(
                EmployeeWorkSession.company_id == cid,
                EmployeeWorkSession.opened_at >= since,
            )
            .scalar()
            or 0
        )

    product_cost = 0.0
    if cid:
        products = db.query(TPVProduct).filter(TPVProduct.company_id == cid).all()
        for p in products:
            unit = float(getattr(p, "price", None) or 0)
            meta = p.metadata_ if isinstance(p.metadata_, dict) else {}
            cost = float(meta.get("cost") or meta.get("unit_cost") or unit * 0.5)
            qty = float(p.stock or 0)
            product_cost += cost * qty

    cashflow_balance = get_balance(db, company_id=cid) if cid else 0.0
    cashflow_summary = get_summary(db, company_id=cid, days=days) if cid else {}

    return {
        "company_id": cid,
        "period_days": days,
        "revenue": round(revenue, 2),
        "staff_cost": round(staff_cost, 2),
        "product_cost": round(product_cost, 2),
        "gross_margin_estimate": round(revenue - staff_cost - product_cost, 2),
        "cashflow_balance": cashflow_balance,
        "cashflow_period": cashflow_summary,
        "sales_count": (analytics.get("financial") or {}).get("sales_count", 0),
        "active_customers": (analytics.get("customers") or {}).get("active_total", 0),
    }
