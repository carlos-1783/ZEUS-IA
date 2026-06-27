"""THALOS threat engine — rule-based detection on structured events."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models.thalos_event import ThalosEvent
from app.models.thalos_security_event import ThalosLoginAttempt


def _load_meta(row: ThalosEvent) -> Dict[str, Any]:
    if not row.metadata_json:
        return {}
    try:
        return json.loads(row.metadata_json)
    except json.JSONDecodeError:
        return {}


def evaluate_events(db: Session, *, window_minutes: int = 60) -> List[Dict[str, Any]]:
    """Evaluate recent ThalosEvent rows and login attempts; return alert candidates."""
    since = datetime.now(timezone.utc) - timedelta(minutes=max(1, window_minutes))
    events: List[ThalosEvent] = (
        db.query(ThalosEvent)
        .filter(ThalosEvent.created_at >= since)
        .order_by(ThalosEvent.id.desc())
        .limit(500)
        .all()
    )

    candidates: List[Dict[str, Any]] = []
    auth_failures = [e for e in events if e.event_type in ("auth_failure", "brute_force")]
    if len(auth_failures) >= 3:
        candidates.append(
            {
                "rule_id": "failed_login_burst",
                "level": "critical",
                "title": "Ráfaga de fallos de autenticación",
                "message": f"{len(auth_failures)} eventos de auth en {window_minutes}min",
                "event_id": auth_failures[0].id,
                "metadata": {"count": len(auth_failures), "window_minutes": window_minutes},
            }
        )

    sql_injection = [e for e in events if e.event_type == "sql_injection"]
    if sql_injection:
        candidates.append(
            {
                "rule_id": "sql_injection_attempt",
                "level": "critical",
                "title": "Intento de inyección SQL detectado",
                "message": sql_injection[0].message[:500],
                "event_id": sql_injection[0].id,
                "metadata": {"count": len(sql_injection)},
            }
        )

    by_source: Dict[str, int] = defaultdict(int)
    for e in events:
        if e.severity in ("error", "critical", "high"):
            by_source[e.source or "unknown"] += 1
    for src, cnt in by_source.items():
        if cnt >= 10:
            candidates.append(
                {
                    "rule_id": "anomaly_error_burst",
                    "level": "high",
                    "title": f"Anomalía de errores en {src}",
                    "message": f"{cnt} eventos severos en {window_minutes}min",
                    "event_id": events[0].id if events else None,
                    "metadata": {"source": src, "count": cnt},
                }
            )

    attempts = (
        db.query(ThalosLoginAttempt)
        .filter(ThalosLoginAttempt.created_at >= since, ThalosLoginAttempt.success == 0)
        .all()
    )
    by_email: Dict[str, int] = defaultdict(int)
    for att in attempts:
        by_email[att.email] += 1
    for email, cnt in by_email.items():
        if cnt >= 5:
            candidates.append(
                {
                    "rule_id": "brute_force_email",
                    "level": "critical",
                    "title": "Brute-force por email",
                    "message": f"{email}: {cnt} fallos en {window_minutes}min",
                    "event_id": None,
                    "metadata": {"email": email, "failed_count": cnt},
                }
            )

    critical_events = [e for e in events if e.severity == "critical"]
    for ev in critical_events[:3]:
        if any(c.get("event_id") == ev.id for c in candidates):
            continue
        candidates.append(
            {
                "rule_id": "critical_event",
                "level": "critical",
                "title": f"Evento crítico: {ev.event_type}",
                "message": ev.message[:500],
                "event_id": ev.id,
                "metadata": _load_meta(ev),
            }
        )

    return candidates
