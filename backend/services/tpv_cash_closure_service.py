"""Cierre de caja (arqueo) del TPV sobre datos reales de la BD.

- Periodo: desde el ultimo cierre de la EMPRESA (o, si no hay ninguno, desde el inicio del
  dia en Europe/Madrid) hasta ahora. `tpv_sales` no guarda terminal, por lo que el cierre
  cubre todas las ventas de la empresa en el periodo (lo que dice la respuesta).
- Efectivo esperado = efectivo inicial + ventas en efectivo del periodo.
- Todo filtrado por company_id; el cierre se persiste en `tpv_cash_closures`.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.fiscal import TPVSale
from app.models.tpv_cash_closure import TPVCashClosure

logger = logging.getLogger(__name__)

_MADRID = ZoneInfo("Europe/Madrid")
_CENT = Decimal("0.01")
CASH_METHODS = frozenset({"efectivo", "cash"})
CARD_METHODS = frozenset({"tarjeta", "card"})


def _money(v: Any) -> Decimal:
    return Decimal(str(v or 0)).quantize(_CENT, rounding=ROUND_HALF_UP)


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _start_of_today_utc(now: datetime) -> datetime:
    local = now.astimezone(_MADRID)
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


def _last_closure(db: Session, company_id: int) -> Optional[TPVCashClosure]:
    return (
        db.query(TPVCashClosure)
        .filter(TPVCashClosure.company_id == company_id)
        .order_by(TPVCashClosure.period_end.desc(), TPVCashClosure.id.desc())
        .first()
    )


def sales_summary(db: Session, *, company_id: int, start: datetime, end: datetime) -> Dict[str, Any]:
    rows = (
        db.query(TPVSale.payment_method, func.count(TPVSale.id), func.coalesce(func.sum(TPVSale.total), 0))
        .filter(
            TPVSale.company_id == company_id,
            TPVSale.sale_date >= start,
            TPVSale.sale_date < end,
        )
        .group_by(TPVSale.payment_method)
        .all()
    )
    cash = card = other = Decimal("0")
    count = 0
    by_method: Dict[str, Any] = {}
    for method, n, total in rows:
        m = (method or "").strip().lower()
        amount = _money(total)
        count += int(n or 0)
        by_method[m or "desconocido"] = {"count": int(n or 0), "total": float(amount)}
        if m in CASH_METHODS:
            cash += amount
        elif m in CARD_METHODS:
            card += amount
        else:
            other += amount
    return {
        "sales_count": count,
        "cash": cash,
        "card": card,
        "other": other,
        "total": cash + card + other,
        "by_method": by_method,
    }


def closure_to_dict(c: TPVCashClosure) -> Dict[str, Any]:
    return {
        "id": c.id,
        "company_id": c.company_id,
        "terminal_id": c.terminal_id,
        "employee_id": c.employee_code,
        "period_start": c.period_start.isoformat() if c.period_start else None,
        "period_end": c.period_end.isoformat() if c.period_end else None,
        "sales_count": c.sales_count,
        "cash_sales_total": float(c.cash_sales_total or 0),
        "card_sales_total": float(c.card_sales_total or 0),
        "other_sales_total": float(c.other_sales_total or 0),
        "sales_total": float(c.sales_total or 0),
        "initial_cash": float(c.initial_cash or 0),
        "final_cash": float(c.final_cash or 0),
        "expected_cash": float(c.expected_cash or 0),
        "difference": float(c.difference or 0),
        "status": c.status,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def close_register(
    db: Session,
    *,
    company_id: Optional[int],
    user_id: int,
    terminal_id: str,
    employee_code: Optional[str],
    initial_cash: float,
    final_cash: float,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    if not isinstance(company_id, int):
        raise HTTPException(status_code=400, detail="Se requiere una empresa para cerrar caja.")
    terminal = (terminal_id or "").strip()[:100]
    if not terminal:
        raise HTTPException(status_code=422, detail="terminal_id es obligatorio.")
    if initial_cash is None or final_cash is None or initial_cash < 0 or final_cash < 0:
        raise HTTPException(status_code=422, detail="El efectivo inicial y el contado no pueden ser negativos.")

    end = _as_utc(now or datetime.now(timezone.utc))
    last = _last_closure(db, company_id)
    start = _as_utc(last.period_end) if last is not None else _start_of_today_utc(end)
    if start >= end:
        raise HTTPException(status_code=409, detail="Ya existe un cierre de caja posterior para esta empresa.")

    summary = sales_summary(db, company_id=company_id, start=start, end=end)
    initial = _money(initial_cash)
    counted = _money(final_cash)
    expected = initial + summary["cash"]
    difference = counted - expected
    status = "ok" if abs(difference) < _CENT else "discrepancy"

    row = TPVCashClosure(
        company_id=company_id,
        user_id=user_id,
        terminal_id=terminal,
        employee_code=(employee_code or None),
        period_start=start,
        period_end=end,
        sales_count=summary["sales_count"],
        cash_sales_total=summary["cash"],
        card_sales_total=summary["card"],
        other_sales_total=summary["other"],
        sales_total=summary["total"],
        initial_cash=initial,
        final_cash=counted,
        expected_cash=expected,
        difference=difference,
        status=status,
    )
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        logger.exception("TPV cierre de caja: fallo al persistir company_id=%s user_id=%s", company_id, user_id)
        raise HTTPException(status_code=500, detail="No se pudo guardar el cierre de caja.")

    logger.info(
        "TPV cierre de caja id=%s company_id=%s user_id=%s terminal=%s ventas=%s efectivo_esperado=%s contado=%s diferencia=%s",
        row.id, company_id, user_id, terminal, summary["sales_count"], expected, counted, difference,
    )
    out = closure_to_dict(row)
    out["by_payment_method"] = summary["by_method"]
    out["scope"] = "empresa"  # tpv_sales no registra terminal: el cierre cubre todas las ventas de la empresa
    return {"success": True, "closure": out}


def list_closures(db: Session, *, company_id: Optional[int], limit: int = 20) -> List[Dict[str, Any]]:
    if not isinstance(company_id, int):
        return []
    rows = (
        db.query(TPVCashClosure)
        .filter(TPVCashClosure.company_id == company_id)
        .order_by(TPVCashClosure.period_end.desc(), TPVCashClosure.id.desc())
        .limit(max(1, min(int(limit), 100)))
        .all()
    )
    return [closure_to_dict(r) for r in rows]
