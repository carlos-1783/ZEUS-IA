"""THALOS alert service — persist alerts from threat engine."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.thalos_alert import ThalosAlert
from services.thalos_threat_engine import evaluate_events

logger = logging.getLogger(__name__)


def _dump(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def create_alert(
    db: Session,
    *,
    title: str,
    level: str = "medium",
    message: Optional[str] = None,
    event_id: Optional[int] = None,
    rule_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> ThalosAlert:
    row = ThalosAlert(
        event_id=event_id,
        level=level,
        title=title[:255],
        message=message,
        rule_id=rule_id,
        resolved=False,
        metadata_json=_dump(metadata or {}),
    )
    db.add(row)
    db.flush()
    _emit_ws(row)
    return row


def _emit_ws(alert: ThalosAlert) -> None:
    try:
        from services.thalos_events_v1 import emit_thalos_event

        emit_thalos_event(
            0,
            "thalos_alert_created",
            {
                "alert_id": alert.id,
                "level": alert.level,
                "title": alert.title,
                "rule_id": alert.rule_id,
            },
        )
    except Exception:
        pass


def generate_alerts_from_engine(db: Session, *, window_minutes: int = 60) -> List[Dict[str, Any]]:
    """Run threat engine and insert new alerts (dedupe by rule_id in window)."""
    candidates = evaluate_events(db, window_minutes=window_minutes)
    created: List[Dict[str, Any]] = []
    since = datetime.now(timezone.utc).replace(microsecond=0)

    for cand in candidates:
        rule_id = cand.get("rule_id")
        if rule_id:
            existing = (
                db.query(ThalosAlert)
                .filter(
                    ThalosAlert.rule_id == rule_id,
                    ThalosAlert.resolved.is_(False),
                    ThalosAlert.created_at >= since.replace(hour=0, minute=0, second=0),
                )
                .first()
            )
            if existing:
                continue
        row = create_alert(
            db,
            title=cand["title"],
            level=cand.get("level", "medium"),
            message=cand.get("message"),
            event_id=cand.get("event_id"),
            rule_id=rule_id,
            metadata=cand.get("metadata"),
        )
        created.append(
            {
                "id": row.id,
                "level": row.level,
                "title": row.title,
                "rule_id": row.rule_id,
                "event_id": row.event_id,
            }
        )
    db.flush()
    return created


def list_alerts(db: Session, *, limit: int = 50, unresolved_only: bool = False) -> List[ThalosAlert]:
    q = db.query(ThalosAlert).order_by(ThalosAlert.id.desc())
    if unresolved_only:
        q = q.filter(ThalosAlert.resolved.is_(False))
    return q.limit(min(limit, 200)).all()


def resolve_alert(db: Session, alert_id: int) -> Optional[ThalosAlert]:
    row = db.query(ThalosAlert).filter(ThalosAlert.id == alert_id).first()
    if not row:
        return None
    row.resolved = True
    row.resolved_at = datetime.now(timezone.utc)
    db.add(row)
    db.flush()
    return row
