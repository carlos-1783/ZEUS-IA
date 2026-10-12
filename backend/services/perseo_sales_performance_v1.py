"""PERSEO: «¿cómo van las ventas?» con datos reales de la empresa (no los de la maqueta).

Ventas = tickets del TPV + facturas emitidas que NO vienen del TPV (las que tienen `tpv_sale_id`
ya estan contadas como ticket). Periodo actual (ultimos N dias, 30 por defecto) frente al periodo
anterior de la misma longitud, y productos mas vendidos del TPV. Todo filtrado por `company_id`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

MAX_DAYS = 365


def _window(db: Session, company_id: int, start: datetime, end: datetime) -> Dict[str, Any]:
    from app.models.erp import Invoice, InvoiceStatus, InvoiceType
    from app.models.fiscal import TPVSale

    tpv_n, tpv_total = (
        db.query(func.count(TPVSale.id), func.coalesce(func.sum(TPVSale.total), 0))
        .filter(TPVSale.company_id == company_id, TPVSale.sale_date >= start, TPVSale.sale_date < end)
        .one()
    )
    # Invoice.issue_date es naive UTC
    s_naive, e_naive = start.replace(tzinfo=None), end.replace(tzinfo=None)
    inv_n, inv_total = (
        db.query(func.count(Invoice.id), func.coalesce(func.sum(Invoice.total), 0))
        .filter(
            Invoice.company_id == company_id,
            Invoice.tpv_sale_id.is_(None),
            Invoice.status.notin_((InvoiceStatus.DRAFT, InvoiceStatus.VOID)),
            (Invoice.invoice_type == InvoiceType.INVOICE) | (Invoice.invoice_type.is_(None)),
            Invoice.issue_date >= s_naive,
            Invoice.issue_date < e_naive,
        )
        .one()
    )
    tpv_total, inv_total = float(tpv_total or 0), float(inv_total or 0)
    return {
        "tpv_count": int(tpv_n or 0),
        "tpv_total": round(tpv_total, 2),
        "invoice_count": int(inv_n or 0),
        "invoice_total": round(inv_total, 2),
        "total": round(tpv_total + inv_total, 2),
    }


def sales_performance(
    db: Session, company_id: int, *, days: int = 30, now: Optional[datetime] = None, top: int = 3
) -> Dict[str, Any]:
    from app.models.fiscal import TPVSale, TPVSaleItem

    if not 1 <= int(days) <= MAX_DAYS:
        raise ValueError("days fuera de rango")
    end = now or datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    prev_start = start - timedelta(days=days)
    current = _window(db, company_id, start, end)
    previous = _window(db, company_id, prev_start, start)
    change = None
    if previous["total"] > 0:
        change = round((current["total"] - previous["total"]) / previous["total"] * 100, 1)
    rows = (
        db.query(
            TPVSaleItem.product_name,
            func.coalesce(func.sum(TPVSaleItem.quantity), 0),
            func.coalesce(func.sum(TPVSaleItem.base_amount + TPVSaleItem.tax_amount), 0),
        )
        .join(TPVSale, TPVSale.id == TPVSaleItem.tpv_sale_id)
        .filter(TPVSale.company_id == company_id, TPVSale.sale_date >= start, TPVSale.sale_date < end)
        .group_by(TPVSaleItem.product_name)
        .order_by(func.sum(TPVSaleItem.base_amount + TPVSaleItem.tax_amount).desc())
        .limit(top)
        .all()
    )
    return {
        "window_days": int(days),
        "current": current,
        "previous": previous,
        "change_pct": change,
        "top_products": [
            {"name": n, "quantity": float(q or 0), "revenue": round(float(r or 0), 2)} for n, q, r in rows
        ],
        "source": "tpv_sales+invoices",
    }
