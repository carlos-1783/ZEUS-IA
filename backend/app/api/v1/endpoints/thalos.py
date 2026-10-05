"""THALOS API — real DB-backed status, events, alerts, audit."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from services.thalos_request_guard_v1 import thalos_request_guard
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.core.config import settings
from app.db.tenant_context import get_db_scoped
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


def _require_superuser_for_global_audit(current_user: User, *, endpoint: str) -> None:
    """Mitigación interina (AUDIT_FIX_THALOS_SHIELD.md, sección 12.2/13):
    este router legacy (`/api/v1/thalos/*`) es un gemelo no versionado de
    `/api/v1/thalos/v1/*` que consulta las mismas tablas GLOBALES
    (ThalosEvent/ThalosAlert/ThalosSecurityEvent/ThalosLoginAttempt, sin
    `company_id`) sin ningún filtro ni gate — no había sido detectado en las
    4 vueltas previas de esta rama porque el grep se centró en
    `workspaces.py`/`thalos_v1.py`. Mismo gate ya aplicado a esos dos
    archivos."""
    if not getattr(current_user, "is_superuser", False):
        raise HTTPException(
            status_code=403,
            detail=(
                f"{endpoint} requiere privilegios de superusuario (mitigación "
                "interina: el motor subyacente audita actividad global sin "
                "filtrar por empresa hasta que se migre el esquema)."
            ),
        )


@router.get("/status")
def thalos_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_scoped),
) -> Dict[str, Any]:
    _require_superuser_for_global_audit(current_user, endpoint="GET /thalos/status")
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
    db: Session = Depends(get_db_scoped),
) -> Dict[str, Any]:
    _require_superuser_for_global_audit(current_user, endpoint="GET /thalos/events")
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
    db: Session = Depends(get_db_scoped),
) -> Dict[str, Any]:
    _require_superuser_for_global_audit(current_user, endpoint="GET /thalos/alerts")
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


@router.post("/alerts/{alert_id}/resolve", dependencies=[Depends(thalos_request_guard)])
def thalos_resolve_alert(
    alert_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_scoped),
) -> Dict[str, Any]:
    # ThalosAlert no tiene `company_id`: sin este gate, cualquier usuario
    # autenticado podía marcar como resuelta (silenciar) una alerta de
    # seguridad de OTRA empresa con solo adivinar/enumerar su `alert_id`.
    _require_superuser_for_global_audit(current_user, endpoint="POST /thalos/alerts/{alert_id}/resolve")
    row = resolve_alert(db, alert_id)
    if not row:
        raise HTTPException(status_code=404, detail="Alert not found")
    db.commit()
    return wrap_response({"id": row.id, "resolved": True}, "events", data_origin="backend", real_execution=True)


@router.get("/audit")
def thalos_audit(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_scoped),
) -> Dict[str, Any]:
    _require_superuser_for_global_audit(current_user, endpoint="GET /thalos/audit")
    report = audit_from_db(db)
    report["worker"] = worker_status()
    report["strict_mode"] = True
    report["simulation_allowed"] = False
    return wrap_response(report, "auditoria_real", data_origin="backend", real_execution=True)


@router.post("/monitor")
def thalos_monitor_now(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_scoped),
) -> Dict[str, Any]:
    # `run_monitor_cycle` solo invoca `scan_logs` (global, sin filtro por
    # tenant) si THALOS_REAL_MONITORING/THALOS_EXECUTION_ENABLED/
    # THALOS_REAL_LOGS_ENABLED están activos (todos `false` por defecto en
    # este entorno, igual que en `thalos_v1.py::thalos_v1_monitor`); no
    # explotable hoy con la configuración por defecto, pero hereda la misma
    # fuga en cuanto se active la monitorización real. Se aplica el mismo
    # gate por consistencia con su gemelo ya protegido.
    _require_superuser_for_global_audit(current_user, endpoint="POST /thalos/monitor")
    result = run_monitor_cycle(db, user_id=current_user.id)
    db.commit()
    return wrap_response(result, "auditoria_real", data_origin="backend", real_execution=True)


@router.post("/logs/ingest")
def thalos_ingest_logs(
    body: LogIngestBody,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_scoped),
) -> Dict[str, Any]:
    # `ingest_log_lines` -> `generate_alerts_from_engine` evalúa
    # `ThalosEvent`/`ThalosLoginAttempt` GLOBALES (60 min) y devuelve en la
    # respuesta cualquier alerta nueva creada — incluidas las que
    # correspondan a actividad de OTRAS empresas si es la primera vez que se
    # dispara esa regla en el día (el dedupe de `generate_alerts_from_engine`
    # es por `rule_id` global, no por tenant). Cualquier usuario autenticado
    # podía ver así, como efecto colateral de subir sus propias líneas de
    # log, alertas de seguridad ajenas. Mismo gate interino aplicado al resto
    # del motor. NOTA para el usuario/auditor: esto restringe la función de
    # "ingesta de logs" del panel THALOS del frontend
    # (`ThalosToolsPanel.vue::runLogs` / `ingestThalosLogs`) a superusuarios
    # mientras no exista un filtrado real por tenant — ver sección 13 del
    # documento de auditoría para la decisión pendiente.
    _require_superuser_for_global_audit(current_user, endpoint="POST /thalos/logs/ingest")
    if not body.logs:
        raise HTTPException(status_code=422, detail="logs required")
    result = ingest_log_lines(db, body.logs, source="api_ingest")
    db.commit()
    return wrap_response(result, "log_monitor", data_origin="backend", real_execution=True)
