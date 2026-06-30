"""TeamFlow persistence — create, list, update with DB + events."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.teamflow_event import TeamFlowEvent
from app.models.teamflow_item import TeamFlowItem, VALID_STATUSES
from app.models.user import User
from services.teamflow_state_v1 import can_transition


def _dump(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def _item_dict(row: TeamFlowItem) -> Dict[str, Any]:
    content = {}
    if row.content_json:
        try:
            content = json.loads(row.content_json)
        except json.JSONDecodeError:
            content = {}
    return {
        "id": row.public_id,
        "db_id": row.id,
        "owner_agent": row.owner_agent,
        "source_agent": row.source_agent,
        "target_agent": row.target_agent,
        "workflow_id": row.workflow_id,
        "item_type": row.item_type,
        "title": row.title,
        "status": row.status,
        "content": content,
        "execution_id": row.execution_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _log_event(
    db: Session,
    item: TeamFlowItem,
    event_type: str,
    *,
    from_status: Optional[str] = None,
    to_status: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> TeamFlowEvent:
    ev = TeamFlowEvent(
        item_id=item.id,
        event_type=event_type,
        owner_agent=item.owner_agent,
        from_status=from_status,
        to_status=to_status,
        details_json=_dump(details or {}),
    )
    db.add(ev)
    db.flush()
    return ev


def create_item(
    db: Session,
    user: User,
    *,
    owner_agent: str,
    title: str,
    item_type: str = "flow",
    status: str = "draft",
    source_agent: Optional[str] = None,
    target_agent: Optional[str] = None,
    workflow_id: Optional[str] = None,
    execution_id: Optional[str] = None,
    content: Optional[Dict[str, Any]] = None,
    company_id: Optional[int] = None,
) -> Dict[str, Any]:
    if status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid status: {status}")
    row = TeamFlowItem(
        user_id=user.id,
        company_id=company_id,
        owner_agent=owner_agent.upper(),
        source_agent=source_agent.upper() if source_agent else None,
        target_agent=target_agent.upper() if target_agent else None,
        workflow_id=workflow_id,
        item_type=item_type,
        title=title[:255],
        status=status,
        execution_id=execution_id,
        content_json=_dump(content or {}),
    )
    db.add(row)
    db.flush()
    _log_event(db, row, "created", to_status=status, details={"title": title})
    return _item_dict(row)


def list_items(
    db: Session,
    user: User,
    *,
    owner_agent: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    q = db.query(TeamFlowItem).filter(TeamFlowItem.user_id == user.id)
    if owner_agent:
        q = q.filter(TeamFlowItem.owner_agent == owner_agent.upper())
    if status:
        q = q.filter(TeamFlowItem.status == status)
    rows = q.order_by(TeamFlowItem.id.desc()).limit(min(limit, 500)).all()
    return [_item_dict(r) for r in rows]


def update_item_status(
    db: Session,
    user: User,
    item_id: str,
    *,
    status: str,
    owner_agent: Optional[str] = None,
) -> Dict[str, Any]:
    row = (
        db.query(TeamFlowItem)
        .filter(TeamFlowItem.public_id == item_id, TeamFlowItem.user_id == user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="TeamFlow item not found")
    if status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid status: {status}")
    if not can_transition(row.status, status):
        raise HTTPException(
            status_code=409,
            detail=f"Invalid transition {row.status} → {status}",
        )
    old = row.status
    row.status = status
    if owner_agent:
        row.owner_agent = owner_agent.upper()
    db.add(row)
    _log_event(db, row, "status_change", from_status=old, to_status=status)
    db.flush()
    return _item_dict(row)


def persist_workflow_execution(
    db: Session,
    user: User,
    *,
    workflow_id: str,
    execution_id: str,
    steps: List[Dict[str, Any]],
    company_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Persist each workflow step as teamflow_item with cross-agent links."""
    legal_handoff_markers = ("legal", "gdpr", "contract", "stamp", "sign", "compliance", "rrhh")
    created = []
    prev_agent: Optional[str] = None
    for step in steps:
        agent = (step.get("agent") or "ZEUS CORE").upper()
        handoffs = step.get("handoff_to") or []
        handoff_text = " ".join(str(h).lower() for h in handoffs)
        targets_justicia = agent == "JUSTICIA" or any(m in handoff_text for m in legal_handoff_markers)

        source: Optional[str] = None
        target: Optional[str] = None
        if agent == "JUSTICIA" and prev_agent:
            source, target = prev_agent, "JUSTICIA"
        elif targets_justicia and agent != "JUSTICIA":
            source, target = agent, "JUSTICIA"

        item = create_item(
            db,
            user,
            owner_agent=agent,
            source_agent=source,
            target_agent=target,
            title=f"[{workflow_id}] {step.get('step_id', 'step')}",
            item_type="flow",
            status="pending" if step.get("depends_on") else "in_progress",
            workflow_id=workflow_id,
            execution_id=execution_id,
            content=step,
            company_id=company_id,
        )
        created.append(item)
        prev_agent = agent
    return created
