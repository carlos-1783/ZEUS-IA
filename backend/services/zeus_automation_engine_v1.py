"""ZEUS automation engine v1 — scheduled business jobs (policy expiration, etc.)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.legal_document import LegalDocument
from app.models.user import User
from services.zeus_event_bus_v1 import emit_event

logger = logging.getLogger(__name__)

POLICY_VALIDITY_DAYS = 365
EXPIRY_WINDOW_DAYS = 7


def _synthetic_expiry(created_at: datetime) -> datetime:
    base = created_at
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return base + timedelta(days=POLICY_VALIDITY_DAYS)


def run_policy_expiration_check(db: Session, *, actor: Optional[User] = None) -> Dict[str, Any]:
    """
    Scan policies/contracts nearing expiration (synthetic expiry from created_at + 365d).
    Emits policy_expiring for documents expiring within 7 days.
    """
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=EXPIRY_WINDOW_DAYS)
    emitted: List[Dict[str, Any]] = []

    rows = (
        db.query(LegalDocument)
        .filter(
            LegalDocument.doc_type.in_(("policy", "contract")),
            LegalDocument.status.in_(("draft", "approved")),
        )
        .order_by(LegalDocument.id.desc())
        .limit(500)
        .all()
    )

    for row in rows:
        if not row.created_at:
            continue
        expires = _synthetic_expiry(row.created_at)
        if now <= expires <= horizon:
            user = actor
            if user is None and row.user_id:
                user = db.query(User).filter(User.id == row.user_id).first()
            payload = {
                "document_id": row.public_id,
                "doc_type": row.doc_type,
                "expires_at": expires.isoformat(),
                "owner_agent": row.owner_agent,
            }
            emit_event(
                db,
                user,
                event_name="policy_expiring",
                source_module="ZEUS_AUTOMATION",
                payload=payload,
            )
            emitted.append(payload)

    logger.info("[ZEUS_AUTOMATION] policy_expiration_check emitted=%s scanned=%s", len(emitted), len(rows))
    return {
        "job": "policy_expiration_check",
        "scanned": len(rows),
        "emitted": len(emitted),
        "events": emitted,
        "real_execution": True,
    }


def run_automation_cycle(db: Session) -> Dict[str, Any]:
    """Single automation cycle — all cron jobs."""
    results = {
        "policy_expiration_check": run_policy_expiration_check(db),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return results
