"""RAFAEL: consultas reales para el chat/voz (cierre de ventas TPV de un dia, facturas pendientes,
ultima factura, facturas de un dia o de un periodo e IVA trimestral de las ventas TPV).

Todo sale de la BD filtrado por la empresa (`company_id`) que resuelve el ejecutor en servidor.

Cierre del dia: las ventas TPV registradas ese dia local (tickets, total, IVA, por forma de pago)
y, si se hizo, el arqueo real guardado por `POST /tpv/close-register` (`tpv_cash_closures`:
efectivo esperado, contado y descuadre). Sin arqueo ese dia se dice explicitamente; no se inventa
un efectivo contado.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from services.local_day_v1 import day_bounds_utc, local_tz

NO_CASH_COUNT_NOTE = (
    "Ese día no se hizo arqueo de caja en el TPV, así que el cierre son las ventas registradas."
)


def _cash_closures(db: Session, company_id: int, start: datetime, end: datetime) -> List[Dict[str, Any]]:
    from app.models.tpv_cash_closure import TPVCashClosure

    rows = (
        db.query(TPVCashClosure)
        .filter(TPVCashClosure.company_id == company_id,
                TPVCashClosure.period_end >= start, TPVCashClosure.period_end < end)
        .order_by(TPVCashClosure.period_end.asc())
        .all()
    )
    return [{
        "terminal": c.terminal_id,
        "expected_cash": round(float(c.expected_cash or 0), 2),
        "counted_cash": round(float(c.final_cash or 0), 2),
        "difference": round(float(c.difference or 0), 2),
        "status": c.status,
    } for c in rows]


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
    closures = _cash_closures(db, company_id, start, end)
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
        "cash_count_recorded": bool(closures),
        "cash_closures": closures,
        "note": None if closures else NO_CASH_COUNT_NOTE,
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


def _invoice_row(inv: Any) -> Dict[str, Any]:
    """Factura -> fila para el chat. `issue_date` en dia LOCAL (Invoice.issue_date es naive UTC)."""
    from datetime import timezone as _tz

    issued = None
    if inv.issue_date is not None:
        issued = inv.issue_date.replace(tzinfo=_tz.utc).astimezone(local_tz()[0]).date().isoformat()
    total = round(float(inv.total or 0), 2)
    return {
        "invoice_number": inv.invoice_number,
        "issue_date": issued,
        "customer": getattr(inv.customer, "name", None) if inv.customer_id else None,
        "amount_total": total,
        "tax_amount": round(float(inv.tax_amount or 0), 2),
        "amount_due": round(max(total - float(inv.amount_paid or 0), 0.0), 2),
        "status": inv.status.value if inv.status else None,
        "from_tpv": inv.tpv_sale_id is not None,
    }


def _invoices_base(db: Session, company_id: int):
    """Facturas (no presupuestos/proformas/rectificativas) de la empresa. Mismos enums que
    `pending_invoices_summary` (nunca literales de texto)."""
    from app.models.erp import Invoice, InvoiceType

    type_ok = (Invoice.invoice_type == InvoiceType.INVOICE) | (Invoice.invoice_type.is_(None))
    return db.query(Invoice).filter(Invoice.company_id == company_id, type_ok)


def last_invoice_summary(db: Session, company_id: int) -> Dict[str, Any]:
    """Ultima factura de la empresa (por fecha de emision; a igualdad, la de mayor id), sea cual sea
    su estado (el estado va en la respuesta: un borrador se dice que es borrador)."""
    from app.models.erp import Invoice

    base = _invoices_base(db, company_id)
    last = base.order_by(Invoice.issue_date.desc(), Invoice.id.desc()).first()
    out: Dict[str, Any] = {"found": last is not None, "invoices_count": base.count()}
    if last is not None:
        out["invoice"] = _invoice_row(last)
    out["source"] = "invoices"
    return out


def invoices_day_summary(db: Session, company_id: int, day: date, *, top: int = 10) -> Dict[str, Any]:
    """Facturas emitidas el dia LOCAL `day` (ver `_invoices_between`)."""
    return {"date": day.isoformat(), **_invoices_between(db, company_id, day, day, top=top)}


# Periodos de «facturas de ayer / de esta semana / de este mes / del mes pasado…» (chat de RAFAEL y ZEUS).
INVOICE_PERIOD_LABELS = {
    "yesterday": "ayer",
    "week": "esta semana",
    "last_week": "la semana pasada",
    "month": "este mes",
    "last_month": "el mes pasado",
}


def invoice_period_bounds(period: str, today: date) -> Tuple[date, date]:
    """(primer dia, ultimo dia) LOCALES del periodo, resueltos en servidor a partir de `today` (dia local,
    `local_day_v1.today_local`). La semana va de lunes a domingo; el periodo en curso acaba hoy (nunca un dia
    futuro). Periodo desconocido -> ValueError (nunca se adivina)."""
    if period == "yesterday":
        d = today - timedelta(days=1)
        return d, d
    if period == "week":
        return today - timedelta(days=today.weekday()), today
    if period == "last_week":
        monday = today - timedelta(days=today.weekday() + 7)
        return monday, monday + timedelta(days=6)
    if period == "month":
        return today.replace(day=1), today
    if period == "last_month":
        last = today.replace(day=1) - timedelta(days=1)
        return last.replace(day=1), last
    raise ValueError("periodo no valido")


def invoices_period_summary(db: Session, company_id: int, period: str, today: date, *,
                            top: int = 10) -> Dict[str, Any]:
    """Facturas emitidas en un periodo de `INVOICE_PERIOD_LABELS`, con el MISMO filtro por dia local que
    `invoices_day_summary` (`_invoices_between`). Periodo desconocido -> ValueError."""
    first, last = invoice_period_bounds(period, today)
    return {
        "period_label": INVOICE_PERIOD_LABELS[period],
        "date_from": first.isoformat(),
        "date_to": last.isoformat(),
        "period": period,
        **_invoices_between(db, company_id, first, last, top=top),
    }


def _invoices_between(db: Session, company_id: int, first_day: date, last_day: date, *,
                      top: int) -> Dict[str, Any]:
    """Facturas emitidas entre los dias LOCALES `first_day` y `last_day` (ambos incluidos). Las anuladas no
    suman al total (se cuentan aparte) y los borradores se cuentan aparte (aun no estan emitidas)."""
    from app.models.erp import Invoice, InvoiceStatus

    start, _ = day_bounds_utc(first_day)
    _, end = day_bounds_utc(last_day)
    # Invoice.issue_date es naive UTC: se comparan limites UTC sin zona.
    start_n, end_n = start.replace(tzinfo=None), end.replace(tzinfo=None)
    rows = (
        _invoices_base(db, company_id)
        .filter(Invoice.issue_date >= start_n, Invoice.issue_date < end_n)
        .order_by(Invoice.issue_date.desc(), Invoice.id.desc())
        .all()
    )
    issued = [i for i in rows if i.status not in (InvoiceStatus.VOID, InvoiceStatus.DRAFT)]
    by_status: Dict[str, int] = {}
    for i in rows:
        k = i.status.value if i.status else "desconocido"
        by_status[k] = by_status.get(k, 0) + 1
    return {
        "timezone": local_tz()[1],
        "count": len(issued),
        "amount_total": round(sum(float(i.total or 0) for i in issued), 2),
        "tax_total": round(sum(float(i.tax_amount or 0) for i in issued), 2),
        "drafts_count": sum(1 for i in rows if i.status == InvoiceStatus.DRAFT),
        "void_count": sum(1 for i in rows if i.status == InvoiceStatus.VOID),
        "by_status": by_status,
        "invoices": [_invoice_row(i) for i in rows[:top]],
        "source": "invoices",
    }


VAT_DRAFT_NOTE = ("Cálculo orientativo sobre las ventas TPV registradas; no se ha presentado ni enviado "
                  "nada a Hacienda.")


def vat_quarter_summary(db: Session, company_id: int, year: int, quarter: int) -> Dict[str, Any]:
    """IVA del trimestre de las ventas TPV de la EMPRESA: reutiliza el calculo de
    `GET /tpv/fiscal/quarterly-vat` (`tpv_quarterly_vat_v1.quarterly_vat_breakdown`) con ambito estricto
    a la empresa de la sesion (sin el fallback de ventas legado sin empresa del endpoint)."""
    from app.models.fiscal import TPVSale
    from services.tpv_quarterly_vat_v1 import quarterly_vat_breakdown

    body = quarterly_vat_breakdown(db, TPVSale.company_id == company_id, year, quarter,
                                   include_sales_count=True)
    vat_total = round(body["iva_4"] + body["iva_10"] + body["iva_21"], 2)
    base_total = round(body["base_4"] + body["base_10"] + body["base_21"], 2)
    # Orden pensado para la ventana del chat: periodo legible, importes principales, desglose por tipo,
    # nota. `year`/`quarter`/`period` quedan para consumidores de maquina (la ventana los oculta).
    return {
        "period_label": f"{quarter}T {year}",
        "vat_total": vat_total,
        "base_total": base_total,
        "grand_total": body["grand_total"],
        "sales_count": body["sales_count"],
        "by_rate": [{"rate": f"{r} %", "tax_base": body[f"base_{r}"], "vat_amount": body[f"iva_{r}"]}
                    for r in (4, 10, 21)],
        "recargo_total": body["recargo_total"],
        "note": VAT_DRAFT_NOTE,
        "submitted_to_aeat": False,
        "period": body["period"],
        "year": year,
        "quarter": quarter,
        "source": "tpv_sales",
    }
