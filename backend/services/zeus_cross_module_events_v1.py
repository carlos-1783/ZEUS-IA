"""Cross-module event bus — async_non_blocking propagation (LOG_ONLY on failure)."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.user import User

logger = logging.getLogger(__name__)

EVENT_TARGETS: Dict[str, List[str]] = {
    "employee_created": ["ops", "workspace", "justicia"],
    "ops_route_created": ["workspace"],
    "document_signed": ["workspace", "perseo"],
    "contract_rrhh_created": ["workspace", "justicia"],
}


def emit_cross_module_event(
    db: Session,
    user: User,
    event_name: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Propagate event to modules without blocking caller transaction."""
    targets = EVENT_TARGETS.get(event_name, [])
    results: Dict[str, Any] = {"event": event_name, "targets": {}, "ok": True}
    if not targets:
        return results

    for target in targets:
        try:
            results["targets"][target] = _dispatch(db, user, target, event_name, payload)
        except Exception as exc:
            logger.warning(
                "[CROSS_MODULE] %s → %s failed: %s",
                event_name,
                target,
                exc,
                exc_info=True,
            )
            results["targets"][target] = {"ok": False, "error": str(exc)}
            results["ok"] = False
    return results


def _dispatch(
    db: Session,
    user: User,
    target: str,
    event_name: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    if target == "workspace":
        from services.workspace_playbook_service_v1 import persist_execution_playbook

        agent = "rrhh" if event_name in ("employee_created", "contract_rrhh_created") else "ops"
        if event_name == "document_signed":
            agent = "justicia"
        row = persist_execution_playbook(
            db,
            user,
            agent_source=agent,
            action=event_name,
            title=f"Evento {event_name}",
            payload=payload,
        )
        return {"ok": True, "playbook_id": row.id if row else None}

    if target == "justicia":
        from app.models.compliance_event import ComplianceEvent

        source = "AFRODITA" if event_name in ("employee_created", "contract_rrhh_created") else "JUSTICIA"
        db.add(
            ComplianceEvent(
                event_type=event_name,
                severity="info",
                source=source,
                details_json=json.dumps(payload, ensure_ascii=False, default=str),
            )
        )
        db.flush()
        return {"ok": True, "compliance_event": event_name}

    if target == "ops":
        from services.workspace_playbook_writer_v1 import write_ops_playbook

        write_ops_playbook(
            db,
            user,
            action=event_name,
            title=f"OPS sync: {event_name}",
            payload=payload,
        )
        return {"ok": True, "module": "ops"}

    if target == "perseo":
        from services.workspace_playbook_service_v1 import persist_execution_playbook

        row = persist_execution_playbook(
            db,
            user,
            agent_source="automation",
            action=event_name,
            title=f"PERSEO sync: {event_name}",
            payload=payload,
        )
        return {"ok": True, "playbook_id": row.id if row else None}

    return {"ok": False, "error": f"unknown target {target}"}
