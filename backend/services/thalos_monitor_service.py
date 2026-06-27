"""THALOS monitor service — logs → parser → events DB → threat engine → alerts."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.thalos_event import ThalosEvent
from services.thalos_alert_service import generate_alerts_from_engine
from services.thalos_log_parser import parse_log_lines, serialize_metadata
from services.thalos_security_engine import scan_logs

logger = logging.getLogger(__name__)

_tail_offsets: Dict[str, int] = {}


def _log_paths() -> List[Path]:
    paths: List[Path] = []
    configured = getattr(settings, "THALOS_LOG_PATH", "") or os.getenv("THALOS_LOG_PATH", "")
    if configured:
        paths.append(Path(configured))
    paths.append(Path("logs/zeus.log"))
    paths.append(Path("/var/log/zeus.log"))
    return [p for p in paths if p.exists()]


def _read_new_lines(path: Path) -> List[str]:
    key = str(path.resolve())
    offset = _tail_offsets.get(key, 0)
    try:
        size = path.stat().st_size
        if size < offset:
            offset = 0
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            fh.seek(offset)
            chunk = fh.read()
            _tail_offsets[key] = fh.tell()
        return [ln for ln in chunk.splitlines() if ln.strip()]
    except OSError as exc:
        logger.warning("[THALOS_MONITOR] cannot read %s: %s", path, exc)
        return []


def persist_parsed_events(db: Session, parsed: List[Dict[str, Any]]) -> int:
    count = 0
    for item in parsed:
        row = ThalosEvent(
            event_type=item["event_type"],
            severity=item["severity"],
            message=item["message"],
            source=item.get("source"),
            metadata_json=serialize_metadata(item.get("metadata") or {}),
        )
        db.add(row)
        count += 1
    if count:
        db.flush()
    return count


def ingest_log_lines(db: Session, lines: List[str], *, source: str = "manual") -> Dict[str, Any]:
    """Parse user-provided or tailed log lines and persist to thalos_events."""
    parsed = parse_log_lines(lines, source=source)
    inserted = persist_parsed_events(db, parsed)
    alerts = generate_alerts_from_engine(db)
    return {"lines_in": len(lines), "events_inserted": inserted, "alerts_created": len(alerts), "alerts": alerts}


def run_monitor_cycle(
    db: Session,
    *,
    company_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Full pipeline: tail log files + security scan → events → threat engine → alerts.
    All data persisted in DB (strict real mode).
    """
    if not getattr(settings, "THALOS_ENABLED", True):
        return {"status": "disabled", "reason": "THALOS_ENABLED=false"}

    log_lines: List[str] = []
    sources: List[str] = []
    for path in _log_paths():
        new_lines = _read_new_lines(path)
        if new_lines:
            log_lines.extend(new_lines)
            sources.append(str(path))

    file_events = 0
    if log_lines:
        file_events = persist_parsed_events(
            db,
            parse_log_lines(log_lines, source=",".join(sources) or "log_file"),
        )

    security_scan: Dict[str, Any] = {}
    if settings.THALOS_REAL_MONITORING or settings.THALOS_EXECUTION_ENABLED or settings.THALOS_REAL_LOGS_ENABLED:
        security_scan = scan_logs(db, hours=24, company_id=company_id)
        for alert in security_scan.get("pattern_alerts") or []:
            db.add(
                ThalosEvent(
                    event_type="security_pattern",
                    severity=security_scan.get("risk_level", "warning"),
                    message=f"{alert.get('pattern')} @ {alert.get('agent')}",
                    source="thalos_security_engine",
                    metadata_json=serialize_metadata(alert),
                )
            )
        db.flush()

    alerts = generate_alerts_from_engine(db)

    from services.thalos_events_v1 import emit_thalos_event

    emit_thalos_event(
        user_id or 0,
        "thalos_monitor_cycle",
        {"events_inserted": file_events, "alerts_created": len(alerts)},
    )

    if user_id:
        from services.thalos_workspace_writer_v1 import write_from_action_result

        write_from_action_result(
            db,
            user_id=user_id,
            company_id=company_id,
            action="security_monitor",
            result={
                "status": "completed",
                "executed": True,
                "file_events": file_events,
                "security_scan": security_scan,
                "alerts": alerts,
            },
            source="thalos_monitor_service",
        )

    return {
        "status": "ok",
        "log_sources": sources,
        "file_events_inserted": file_events,
        "security_scan": security_scan,
        "alerts_created": len(alerts),
        "alerts": alerts,
        "pipeline": ["logs", "parser", "events", "threat_engine", "alerts"],
    }


def audit_from_db(db: Session) -> Dict[str, Any]:
    """Full system analysis from DB only."""
    from app.models.thalos_alert import ThalosAlert
    from app.models.thalos_security_event import ThalosSecurityEvent

    event_count = db.query(ThalosEvent).count()
    alert_count = db.query(ThalosAlert).count()
    open_alerts = db.query(ThalosAlert).filter(ThalosAlert.resolved.is_(False)).count()
    sec_count = db.query(ThalosSecurityEvent).count()

    recent_events = (
        db.query(ThalosEvent)
        .order_by(ThalosEvent.id.desc())
        .limit(10)
        .all()
    )
    recent_alerts = (
        db.query(ThalosAlert)
        .order_by(ThalosAlert.id.desc())
        .limit(10)
        .all()
    )

    severity_breakdown: Dict[str, int] = {}
    for ev in db.query(ThalosEvent).limit(1000).all():
        severity_breakdown[ev.severity] = severity_breakdown.get(ev.severity, 0) + 1

    return {
        "event_count": int(event_count),
        "alert_count": int(alert_count),
        "open_alerts": int(open_alerts),
        "security_event_count": int(sec_count),
        "severity_breakdown": severity_breakdown,
        "recent_events": [
            {"id": e.id, "type": e.event_type, "severity": e.severity, "message": e.message[:200]}
            for e in recent_events
        ],
        "recent_alerts": [
            {"id": a.id, "level": a.level, "title": a.title, "resolved": a.resolved}
            for a in recent_alerts
        ],
        "data_origin": "database",
        "simulation_detected": False,
    }
