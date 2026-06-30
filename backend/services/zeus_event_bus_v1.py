"""Minimal DB-backed event bus for cross-module propagation."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.zeus_domain_event import ZeusDomainEvent
from services.zeus_event_handlers_v1 import dispatch_event_handlers

logger = logging.getLogger(__name__)

EVENT_TARGETS: Dict[str, List[str]] = {
    "employee_created": ["ops", "workspace", "justicia"],
    "contract_rrhh_created": ["workspace", "justicia"],
    "ops_route_created": ["workspace"],
    "document_signed": ["workspace", "perseo"],
    "contract_signed": ["workspace", "perseo"],
    "invoice_generated": ["workspace"],
    "policy_expiring": ["workspace", "perseo"],
}


def emit_event(
    db: Session,
    user: Optional[User],
    *,
    event_name: str,
    source_module: str,
    payload: Optional[Dict[str, Any]] = None,
    async_mode: bool = True,
) -> Dict[str, Any]:
    """Persist event and propagate to registered modules (best-effort, non-blocking)."""
    body = payload or {}
    row = ZeusDomainEvent(
        user_id=user.id if user else None,
        event_name=event_name,
        source_module=source_module.upper(),
        payload_json=json.dumps(body, ensure_ascii=False, default=str),
    )
    db.add(row)
    db.flush()

    propagated: List[str] = []
    try:
        handlers = dispatch_event_handlers(db, user, event_name, body)
        propagated.extend(handlers)
    except Exception as exc:
        logger.warning("[EVENT_BUS] handler dispatch failed: %s", exc)

    for target in EVENT_TARGETS.get(event_name, EVENT_TARGETS.get("document_signed" if event_name == "contract_signed" else "", [])):
        if target not in propagated and target not in [p.split(".")[0] for p in propagated]:
            propagated.append(target)

    row.propagated_to = json.dumps(propagated, ensure_ascii=False)
    db.add(row)
    db.flush()

    logger.info("[EVENT_BUS] %s from %s → %s (async=%s)", event_name, source_module, propagated, async_mode)
    return {
        "event_id": row.public_id,
        "event_name": event_name,
        "propagated_to": propagated,
        "active": True,
    }


def event_bus_status(db: Session) -> Dict[str, Any]:
    try:
        count = db.query(ZeusDomainEvent).count()
        return {"active": True, "events_total": count, "registered_events": list(EVENT_TARGETS.keys())}
    except Exception as exc:
        return {"active": False, "error": str(exc)}
