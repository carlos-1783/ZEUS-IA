"""Métricas reales desde BD: ventas TPV/CMR, clientes, actividad."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.agent_activity import AgentActivity
from app.models.customer import Customer
from app.models.fiscal import TPVSale
from app.models.user import User
import services.crm_office_service as crm_svc


def _sales_query(db: Session, user: User, since: datetime):
    q = db.query(TPVSale).filter(TPVSale.sale_date >= since)
    is_superuser = bool(getattr(user, "is_superuser", False))
    company_id = crm_svc.primary_company_id(db, user)
    if company_id is not None and not is_superuser:
        q = q.filter(TPVSale.company_id == company_id)
    elif not is_superuser:
        q = q.filter(TPVSale.user_id == user.id)
    return q


def build_analytics_summary(
    db: Session,
    user: User,
    days: int = 30,
) -> Dict[str, Any]:
    """Resumen unificado para dashboard y orquestador."""
    since = datetime.utcnow() - timedelta(days=days)
    sales = _sales_query(db, user, since).order_by(TPVSale.sale_date.asc()).all()

    total_revenue = 0.0
    cmr_count = 0
    tpv_count = 0
    by_day: Dict[str, float] = {}

    for sale in sales:
        amount = float(sale.total or 0)
        total_revenue += amount
        day_key = sale.sale_date.strftime("%Y-%m-%d") if sale.sale_date else "unknown"
        by_day[day_key] = by_day.get(day_key, 0.0) + amount
        cd = sale.customer_data if isinstance(sale.customer_data, dict) else {}
        if cd.get("source") == "office_crm":
            cmr_count += 1
        else:
            tpv_count += 1

    sales_count = len(sales)
    avg_ticket = total_revenue / sales_count if sales_count else 0.0

    customers = crm_svc.list_customers(db, user)
    active_customers = len(customers)

    act_q = db.query(AgentActivity).filter(AgentActivity.created_at >= since)
    if not getattr(user, "is_superuser", False):
        act_q = act_q.filter(AgentActivity.user_email == user.email)
    activity_total = act_q.count()

    sales_by_day: List[Dict[str, Any]] = [
        {"date": d, "total": round(v, 2), "label": d[5:]}
        for d, v in sorted(by_day.items())
    ]

    return {
        "success": True,
        "period_days": days,
        "financial": {
            "total_revenue": round(total_revenue, 2),
            "sales_count": sales_count,
            "avg_ticket": round(avg_ticket, 2),
            "cmr_payments_count": cmr_count,
            "tpv_sales_count": tpv_count,
        },
        "customers": {
            "active_total": active_customers,
            "with_email": sum(1 for c in customers if c.email),
        },
        "activity": {
            "total_events": activity_total,
        },
        "sales_by_day": sales_by_day,
        "data_sources": ["tpv_sales", "cmr_payments", "customers", "activity_log"],
    }
