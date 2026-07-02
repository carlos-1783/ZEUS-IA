"""CRM → ZEUS agent hooks (THALOS monitor, RAFAEL notify, JUSTICIA review)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.user import User

logger = logging.getLogger(__name__)

PAYMENT_RISK_DAYS = 7


def _customer_payload(customer: Customer) -> Dict[str, Any]:
    meta = customer.metadata_ if isinstance(customer.metadata_, dict) else {}
    return {
        "customer_id": customer.id,
        "name": customer.name,
        "email": customer.email,
        "phone": customer.phone,
        "company_id": customer.company_id,
        "next_payment_date": meta.get("next_payment_date") or meta.get("next_payment"),
        "metadata": meta,
    }


def _parse_iso_date(raw: Any) -> Optional[datetime]:
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    try:
        text = str(raw).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _resolve_next_payment_date(db: Session, customer: Customer) -> Optional[datetime]:
    meta = customer.metadata_ if isinstance(customer.metadata_, dict) else {}
    due = _parse_iso_date(meta.get("next_payment_date") or meta.get("next_payment"))
    if due:
        return due
    try:
        from app.models.crm_office import CustomerRecord

        open_rec = (
            db.query(CustomerRecord)
            .filter(
                CustomerRecord.customer_id == customer.id,
                CustomerRecord.status.in_(("open", "pending", "draft")),
            )
            .order_by(CustomerRecord.id.desc())
            .first()
        )
        if open_rec and open_rec.amount and float(open_rec.amount) > 0:
            base = open_rec.updated_at or open_rec.created_at or customer.updated_at
            if base:
                if base.tzinfo is None:
                    base = base.replace(tzinfo=timezone.utc)
                return base + timedelta(days=30)
    except Exception:
        pass
    return None


def check_payment_expiry_risk(
    db: Session,
    customer: Customer,
) -> Optional[Dict[str, Any]]:
    """THALOS-style monitor: payment due within PAYMENT_RISK_DAYS."""
    due = _resolve_next_payment_date(db, customer)
    if not due:
        return None
    now = datetime.now(timezone.utc)
    delta = due - now
    if delta < timedelta(days=PAYMENT_RISK_DAYS):
        return {
            **_customer_payload(customer),
            "next_payment_date": due.isoformat(),
            "days_until_due": max(delta.days, 0),
            "risk_level": "high" if delta.days <= 2 else "medium",
        }
    return None


def on_client_created(db: Session, user: User, customer: Customer) -> Dict[str, Any]:
    """Emit client.created → PERSEO/workspace via zeus_event_bus."""
    from services.zeus_event_bus_v1 import emit_event

    payload = _customer_payload(customer)
    out = emit_event(
        db,
        user,
        event_name="client_created",
        source_module="CRM",
        payload=payload,
    )
    try:
        from services.event_bus import emit_client_created as legacy_emit

        legacy_emit(
            user_id=user.id,
            user_email=getattr(user, "email", None),
            company_id=customer.company_id or 0,
            customer_id=customer.id,
            customer_name=customer.name,
            customer_email=customer.email,
            db=db,
        )
    except Exception as exc:
        logger.warning("[CRM_HOOK] legacy client_created failed: %s", exc)
    return out


def on_client_updated(db: Session, user: User, customer: Customer) -> Dict[str, Any]:
    """Emit client.updated; THALOS may raise payment.risk for agents."""
    from services.zeus_event_bus_v1 import emit_event

    payload = _customer_payload(customer)
    out = emit_event(
        db,
        user,
        event_name="client_updated",
        source_module="CRM",
        payload=payload,
    )
    risk = check_payment_expiry_risk(db, customer)
    if risk:
        risk_out = emit_event(
            db,
            user,
            event_name="payment_risk",
            source_module="THALOS",
            payload=risk,
        )
        out["payment_risk"] = risk_out
    return out
