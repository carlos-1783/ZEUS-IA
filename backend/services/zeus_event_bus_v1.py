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
    "contract_rrhh_created": ["workspace", "justicia", "perseo", "rafael", "thalos", "pipeline"],
    "client_created": ["perseo", "workspace"],
    "client_updated": ["thalos", "workspace"],
    "payment_due": ["zeus_core", "rafael", "crm_payment_risk"],
    "payment_risk": ["rafael", "justicia", "thalos"],
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
    try:
        row = ZeusDomainEvent(
            user_id=user.id if user else None,
            event_name=event_name,
            source_module=source_module.upper(),
            payload_json=json.dumps(body, ensure_ascii=False, default=str),
        )
        db.add(row)
        db.flush()
    except Exception as exc:
        logger.warning("[EVENT_BUS] persist failed (migration 0042?): %s", exc)
        return {
            "event_id": None,
            "event_name": event_name,
            "propagated_to": [],
            "active": False,
            "degraded": True,
            "error": str(exc),
        }

    propagated: List[str] = []
    pipeline_result: Optional[Dict[str, Any]] = None
    try:
        dispatch = dispatch_event_handlers(db, user, event_name, body)
        handlers = dispatch.get("handlers") or []
        propagated.extend(handlers)
        pipeline_result = dispatch.get("pipeline")
    except Exception as exc:
        logger.warning("[EVENT_BUS] handler dispatch failed: %s", exc)

    for target in EVENT_TARGETS.get(event_name, []):
        if target not in propagated:
            propagated.append(target)

    try:
        row.propagated_to = json.dumps(propagated, ensure_ascii=False)
        db.add(row)
        db.flush()
    except Exception:
        pass

    logger.info("[EVENT_BUS] %s from %s → %s (async=%s)", event_name, source_module, propagated, async_mode)

    try:
        from services.zeus_analytics_real_v1 import record_zeus_event

        record_zeus_event(
            db,
            event_type=event_name,
            agent=source_module,
            status="success",
            user_id=user.id if user else None,
        )
    except Exception as exc:
        logger.warning("[EVENT_BUS] analytics event record failed: %s", exc)

    try:
        from services.zeus_automation_audit_v1 import record_automation_audit

        audit_status = "success"
        if pipeline_result and isinstance(pipeline_result, dict) and pipeline_result.get("real_execution") is False:
            audit_status = "partial"
        record_automation_audit(
            db,
            automation_name=event_name,
            agent=source_module,
            trigger_type="event_bus",
            status=audit_status,
            input_data=body,
            output_data={
                "event_id": row.public_id,
                "propagated_to": propagated,
                "pipeline": pipeline_result,
            },
            user_id=user.id if user else None,
        )
    except Exception as exc:
        logger.warning("[EVENT_BUS] automation audit record failed: %s", exc)

    return {
        "event_id": row.public_id,
        "event_name": event_name,
        "propagated_to": propagated,
        "pipeline": pipeline_result,
        "active": True,
    }


def event_bus_status(db: Session) -> Dict[str, Any]:
    try:
        count = db.query(ZeusDomainEvent).count()
        return {"active": True, "events_total": count, "registered_events": list(EVENT_TARGETS.keys())}
    except Exception as exc:
        return {"active": False, "error": str(exc)}
