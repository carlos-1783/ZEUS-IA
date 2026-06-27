"""THALOS API — real DB-backed status, events, alerts, audit."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.core.config import settings
from app.db.session import get_db
from app.models.thalos_alert import ThalosAlert
from app.models.thalos_event import ThalosEvent
from app.models.user import User
from services.thalos_alert_service import list_alerts, resolve_alert
from services.thalos_control_layer_v1 import wrap_response
from services.thalos_monitor_service import audit_from_db, ingest_log_lines, run_monitor_cycle
from workers.thalos_worker import worker_status

router = APIRouter(prefix="/thalos", tags=["thalos"])


class LogIngestBody(BaseModel):
    logs: list[str] = Field(default_factory=list)


@router.get("/status")
def thalos_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ = current_user
    if not getattr(settings, "THALOS_ENABLED", True):
        raise HTTPException(status_code=503, detail="THALOS_ENABLED=false")

    audit = audit_from_db(db)
    ws = worker_status()
    body = {
        "thalos_enabled": True,
        "worker": ws,
        "database": audit,
        "flags": {
            "THALOS_EXECUTION_ENABLED": settings.THALOS_EXECUTION_ENABLED,
            "THALOS_REAL_MONITORING": settings.THALOS_REAL_MONITORING,
            "THALOS_REAL_LOGS_ENABLED": settings.THALOS_REAL_LOGS_ENABLED,
            "THALOS_BACKUP_ENABLED": settings.THALOS_BACKUP_ENABLED,
        },
        "system_default_mode": "REAL_ACTIVE" if settings.THALOS_EXECUTION_ENABLED else "REAL_SAFE",
    }
    if audit["event_count"] == 0 and not ws["running"]:
        body["warning"] = "No events in DB and worker not running — enable THALOS_REAL_MONITORING"
    return wrap_response(body, "status", data_origin="backend", real_execution=True)


@router.get("/events")
def thalos_events(
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ = current_user
    rows = db.query(ThalosEvent).order_by(ThalosEvent.id.desc()).limit(min(limit, 200)).all()
    if not rows and getattr(settings, "THALOS_ENABLED", True):
        raise HTTPException(status_code=404, detail="No events in database yet — run monitor or worker")
    events = []
    for r in rows:
        meta = {}
        if r.metadata_json:
            try:
                meta = json.loads(r.metadata_json)
            except json.JSONDecodeError:
                meta = {}
        events.append(
            {
                "id": r.id,
                "type": r.event_type,
                "severity": r.severity,
                "message": r.message,
                "source": r.source,
                "metadata": meta,
                "timestamp": r.created_at.isoformat() if r.created_at else None,
            }
        )
    return wrap_response({"events": events, "count": len(events)}, "events", data_origin="backend", real_execution=True)


@router.get("/alerts")
def thalos_alerts(
    limit: int = 50,
    unresolved_only: bool = False,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ = current_user
    rows = list_alerts(db, limit=limit, unresolved_only=unresolved_only)
    alerts = [
        {
            "id": r.id,
            "event_id": r.event_id,
            "level": r.level,
            "title": r.title,
            "message": r.message,
            "rule_id": r.rule_id,
            "resolved": r.resolved,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return wrap_response({"alerts": alerts, "count": len(alerts)}, "events", data_origin="backend", real_execution=True)


@router.post("/alerts/{alert_id}/resolve")
def thalos_resolve_alert(
    alert_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ = current_user
    row = resolve_alert(db, alert_id)
    if not row:
        raise HTTPException(status_code=404, detail="Alert not found")
    db.commit()
    return wrap_response({"id": row.id, "resolved": True}, "events", data_origin="backend", real_execution=True)


@router.get("/audit")
def thalos_audit(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ = current_user
    report = audit_from_db(db)
    report["worker"] = worker_status()
    report["strict_mode"] = True
    report["simulation_allowed"] = False
    return wrap_response(report, "auditoria_real", data_origin="backend", real_execution=True)


@router.post("/monitor")
def thalos_monitor_now(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    result = run_monitor_cycle(db, user_id=current_user.id)
    db.commit()
    return wrap_response(result, "auditoria_real", data_origin="backend", real_execution=True)


@router.post("/logs/ingest")
def thalos_ingest_logs(
    body: LogIngestBody,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ = current_user
    if not body.logs:
        raise HTTPException(status_code=422, detail="logs required")
    result = ingest_log_lines(db, body.logs, source="api_ingest")
    db.commit()
    return wrap_response(result, "log_monitor", data_origin="backend", real_execution=True)
