"""
Persistencia real de cashflow — cada cobro/venta genera un movimiento en BD.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.cashflow_ledger import CashflowLedgerEntry

logger = logging.getLogger(__name__)


def record_movement(
    db: Session,
    *,
    company_id: int,
    amount: float,
    direction: str = "in",
    source: str,
    user_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    invoice_id: Optional[int] = None,
    tpv_sale_id: Optional[int] = None,
    ticket_id: Optional[str] = None,
    payment_method: Optional[str] = None,
    reference: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    auto_commit: bool = True,
) -> CashflowLedgerEntry:
    amt = abs(float(amount or 0))
    if amt <= 0:
        raise ValueError("amount debe ser > 0 para registrar cashflow")
    from services.financial_integrity_v1 import assert_financial_record_valid

    fin = assert_financial_record_valid(
        db,
        company_id=company_id,
        amount=amt,
        domain="cashflow",
        action="record_movement",
        actor_id=user_id,
    )
    if fin.get("blocked"):
        raise ValueError(
            fin.get("guard", {}).get("human_message") or "Registro cashflow bloqueado por guard"
        )
    direc = (direction or "in").strip().lower()
    if direc not in ("in", "out"):
        direc = "in"

    entry = CashflowLedgerEntry(
        company_id=int(company_id),
        user_id=user_id,
        customer_id=customer_id,
        invoice_id=invoice_id,
        tpv_sale_id=tpv_sale_id,
        ticket_id=(str(ticket_id)[:128] if ticket_id else None),
        amount=amt,
        direction=direc,
        source=str(source or "UNKNOWN")[:64],
        payment_method=(str(payment_method)[:64] if payment_method else None),
        reference=(str(reference)[:255] if reference else None),
        metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
    )
    from services.zeus_runtime_guard_v1 import clear_authorized_session, mark_authorized_session

    mark_authorized_session(db)
    try:
        db.add(entry)
        if auto_commit:
            db.commit()
            db.refresh(entry)
        else:
            db.flush()
    finally:
        clear_authorized_session(db)
    logger.info(
        "cashflow_ledger entry id=%s company=%s %s %.2f source=%s",
        entry.id,
        company_id,
        direc,
        amt,
        source,
    )
    return entry


def get_balance(db: Session, *, company_id: int) -> float:
    ins = (
        db.query(func.coalesce(func.sum(CashflowLedgerEntry.amount), 0.0))
        .filter(
            CashflowLedgerEntry.company_id == company_id,
            CashflowLedgerEntry.direction == "in",
        )
        .scalar()
    )
    outs = (
        db.query(func.coalesce(func.sum(CashflowLedgerEntry.amount), 0.0))
        .filter(
            CashflowLedgerEntry.company_id == company_id,
            CashflowLedgerEntry.direction == "out",
        )
        .scalar()
    )
    return round(float(ins or 0) - float(outs or 0), 2)


def get_summary(
    db: Session,
    *,
    company_id: int,
    days: int = 30,
) -> Dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(days=max(1, int(days)))
    rows: List[CashflowLedgerEntry] = (
        db.query(CashflowLedgerEntry)
        .filter(
            CashflowLedgerEntry.company_id == company_id,
            CashflowLedgerEntry.created_at >= since,
        )
        .order_by(CashflowLedgerEntry.created_at.desc())
        .all()
    )
    total_in = sum(r.amount for r in rows if r.direction == "in")
    total_out = sum(r.amount for r in rows if r.direction == "out")
    by_source: Dict[str, float] = {}
    for r in rows:
        if r.direction != "in":
            continue
        by_source[r.source] = by_source.get(r.source, 0.0) + float(r.amount or 0)

    return {
        "company_id": company_id,
        "balance": get_balance(db, company_id=company_id),
        "period_days": days,
        "total_in": round(total_in, 2),
        "total_out": round(total_out, 2),
        "net_period": round(total_in - total_out, 2),
        "by_source": {k: round(v, 2) for k, v in by_source.items()},
        "entries_count": len(rows),
        "recent": [
            {
                "id": r.id,
                "amount": r.amount,
                "direction": r.direction,
                "source": r.source,
                "ticket_id": r.ticket_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows[:20]
        ],
    }


def detect_anomaly(
    db: Session,
    *,
    company_id: int,
    threshold_multiplier: float = 3.0,
) -> Dict[str, Any]:
    """Wrapper THALOS v1 — delega en thalos_security_engine sin alterar get_summary."""
    from services.thalos_security_engine import detect_cashflow_anomaly

    return detect_cashflow_anomaly(
        db,
        company_id=company_id,
        threshold_multiplier=threshold_multiplier,
    )
