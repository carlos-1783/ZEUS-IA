"""RAFAEL: consultas reales para el chat/voz (cierre de ventas TPV de un dia y facturas pendientes).

Todo sale de la BD filtrado por la empresa (`company_id`) que resuelve el ejecutor en servidor.

Cierre del dia: el TPV NO guarda arqueo de caja (`POST /tpv/close-register` no persiste nada), asi
que el "cierre" son las ventas TPV registradas ese dia local (tickets, total, IVA, por forma de
pago). Se dice explicitamente en la salida; no se inventa un efectivo contado.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from services.local_day_v1 import day_bounds_utc, local_tz

NO_CASH_COUNT_NOTE = (
    "El TPV no guarda el arqueo de caja (efectivo contado), así que el cierre son las ventas "
    "registradas ese día."
)


def daily_close_summary(db: Session, company_id: int, day: date) -> Dict[str, Any]:
    from app.models.fiscal import TPVSale

    start, end = day_bounds_utc(day)
    rows = (
        db.query(
            TPVSale.payment_method,
            func.count(TPVSale.id),
            func.coalesce(func.sum(TPVSale.total), 0),
            func.coalesce(func.sum(TPVSale.tax_amount), 0),
            func.coalesce(func.sum(TPVSale.subtotal), 0),
        )
        .filter(TPVSale.company_id == company_id, TPVSale.sale_date >= start, TPVSale.sale_date < end)
        .group_by(TPVSale.payment_method)
        .all()
    )
    by_method: Dict[str, Dict[str, Any]] = {}
    tickets = 0
    total = tax = subtotal = 0.0
    for method, n, t, tx, sub in rows:
        by_method[str(method or "desconocido")] = {"count": int(n), "total": round(float(t or 0), 2)}
        tickets += int(n)
        total += float(t or 0)
        tax += float(tx or 0)
        subtotal += float(sub or 0)
    return {
        "date": day.isoformat(),
        "timezone": local_tz()[1],
        "tickets": tickets,
        "total": round(total, 2),
        "subtotal": round(subtotal, 2),
        "tax_total": round(tax, 2),
        "average_ticket": round(total / tickets, 2) if tickets else 0.0,
        "by_payment_method": by_method,
        "cash_count_recorded": False,
        "note": NO_CASH_COUNT_NOTE,
        "source": "tpv_sales",
    }


def pending_invoices_summary(db: Session, company_id: int, *, top: int = 5) -> Dict[str, Any]:
    """Facturas emitidas sin cobrar del todo (enviadas, parcialmente pagadas o vencidas) y borradores
    sin emitir. Vencida = estado overdue o fecha de vencimiento pasada."""
    from app.models.erp import Invoice, InvoiceStatus, InvoiceType

    open_statuses = (InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE)
    base = db.query(Invoice).filter(Invoice.company_id == company_id)
    type_ok = (Invoice.invoice_type == InvoiceType.INVOICE) | (Invoice.invoice_type.is_(None))
    rows = base.filter(Invoice.status.in_(open_statuses), type_ok).all()
    now = datetime.utcnow()  # Invoice.due_date es naive UTC
    items: List[Dict[str, Any]] = []
    for inv in rows:
        due = max(float(inv.total or 0) - float(inv.amount_paid or 0), 0.0)
        if due <= 0:
            continue
        overdue = inv.status == InvoiceStatus.OVERDUE or (inv.due_date is not None and inv.due_date < now)
        items.append({
            "invoice_number": inv.invoice_number,
            "amount_due": round(due, 2),
            "due_date": inv.due_date.date().isoformat() if inv.due_date else None,
            "overdue": bool(overdue),
            "status": inv.status.value if inv.status else None,
        })
    items.sort(key=lambda i: (not i["overdue"], i["due_date"] or "9999-12-31"))
    drafts = base.filter(Invoice.status == InvoiceStatus.DRAFT, type_ok).count()
    return {
        "pending_count": len(items),
        "pending_amount": round(sum(i["amount_due"] for i in items), 2),
        "overdue_count": sum(1 for i in items if i["overdue"]),
        "overdue_amount": round(sum(i["amount_due"] for i in items if i["overdue"]), 2),
        "drafts_count": int(drafts),
        "top": items[:top],
        "source": "invoices",
    }
