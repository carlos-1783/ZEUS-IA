"""THALOS: estado de seguridad REAL de una empresa (Fase 2 / Step 3).

Lee `thalos_security_events` de la empresa indicada (nunca de otras): eventos por decision y
severidad en la ventana, y los ultimos rechazos. Sin datos -> lo dice (no rellena).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.thalos_security_event import ThalosSecurityEvent

_DENY = ("deny", "block", "blocked", "audit_fail")


def company_security_status(db: Session, company_id: int, *, days: int = 7) -> Dict[str, Any]:
    days = max(1, min(int(days or 7), 90))
    since = datetime.now(timezone.utc) - timedelta(days=days)
    base = db.query(ThalosSecurityEvent).filter(
        ThalosSecurityEvent.company_id == company_id, ThalosSecurityEvent.created_at >= since
    )
    by_action = dict(
        base.with_entities(ThalosSecurityEvent.action_taken, func.count(ThalosSecurityEvent.id))
        .group_by(ThalosSecurityEvent.action_taken).all()
    )
    by_severity = dict(
        base.with_entities(ThalosSecurityEvent.severity, func.count(ThalosSecurityEvent.id))
        .group_by(ThalosSecurityEvent.severity).all()
    )
    denials = (
        base.filter(ThalosSecurityEvent.action_taken.in_(_DENY))
        .order_by(ThalosSecurityEvent.id.desc()).limit(5).all()
    )
    total = sum(int(v) for v in by_action.values())
    return {
        "company_id": company_id,
        "window_days": days,
        "events_total": total,
        "by_action": {str(k or "?"): int(v) for k, v in by_action.items()},
        "by_severity": {str(k or "?"): int(v) for k, v in by_severity.items()},
        "denied_total": sum(int(v) for k, v in by_action.items() if k in _DENY),
        "critical_total": int(by_severity.get("critical", 0)),
        "recent_denials": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "severity": e.severity,
                "rule": e.decision_rule,
                "source": e.source,
                "at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in denials
        ],
        "source": "thalos_security_events",
    }
