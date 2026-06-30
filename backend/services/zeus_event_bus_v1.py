"""Minimal DB-backed event bus for cross-module propagation."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.compliance_event import ComplianceEvent
from app.models.user import User
from app.models.zeus_domain_event import ZeusDomainEvent

logger = logging.getLogger(__name__)

EVENT_TARGETS: Dict[str, List[str]] = {
    "employee_created": ["ops", "workspace", "justicia"],
    "ops_route_created": ["workspace"],
    "document_signed": ["workspace", "perseo"],
}


def emit_event(
    db: Session,
    user: Optional[User],
    *,
    event_name: str,
    source_module: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Persist event and propagate to registered modules (best-effort)."""
    row = ZeusDomainEvent(
        user_id=user.id if user else None,
        event_name=event_name,
        source_module=source_module.upper(),
        payload_json=json.dumps(payload or {}, ensure_ascii=False, default=str),
    )
    db.add(row)
    db.flush()

    propagated = _propagate(db, user, event_name, payload or {})
    row.propagated_to = json.dumps(propagated, ensure_ascii=False)
    db.add(row)
    db.flush()

    logger.info("[EVENT_BUS] %s from %s → %s", event_name, source_module, propagated)
    return {
        "event_id": row.public_id,
        "event_name": event_name,
        "propagated_to": propagated,
        "active": True,
    }


def _propagate(db: Session, user: Optional[User], event_name: str, payload: Dict[str, Any]) -> List[str]:
    done: List[str] = []
    targets = EVENT_TARGETS.get(event_name, [])

    if "workspace" in targets and user:
        try:
            from services.afrodita_workspace_db_service_v1 import persist_workspace_playbook, workspace_enabled

            if workspace_enabled():
                persist_workspace_playbook(
                    db,
                    user,
                    title=f"Event:{event_name}",
                    content={"event": event_name, **payload},
                    agent_source=payload.get("owner_agent") or "ZEUS_CORE",
                )
                done.append("workspace")
        except Exception as exc:
            logger.warning("[EVENT_BUS] workspace propagation failed: %s", exc)

    if "justicia" in targets:
        try:
            db.add(
                ComplianceEvent(
                    event_type=event_name,
                    severity="low",
                    source=payload.get("source_agent") or "AFRODITA",
                    details_json=json.dumps(payload, ensure_ascii=False, default=str),
                )
            )
            db.flush()
            done.append("justicia")
        except Exception as exc:
            logger.warning("[EVENT_BUS] justicia propagation failed: %s", exc)

    if "ops" in targets:
        done.append("ops")

    if "perseo" in targets:
        try:
            db.add(
                ComplianceEvent(
                    event_type=event_name,
                    severity="info",
                    source="PERSEO",
                    details_json=json.dumps(payload, ensure_ascii=False, default=str),
                )
            )
            db.flush()
            done.append("perseo")
        except Exception as exc:
            logger.warning("[EVENT_BUS] perseo propagation failed: %s", exc)

    return done


def event_bus_status(db: Session) -> Dict[str, Any]:
    try:
        count = db.query(ZeusDomainEvent).count()
        return {"active": True, "events_total": count, "registered_events": list(EVENT_TARGETS.keys())}
    except Exception as exc:
        return {"active": False, "error": str(exc)}
