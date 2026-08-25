"""THALOS v1 API — monitorización, ejecución y workspace + control layer."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.core.config import settings
from app.db.session import get_db
from app.models.thalos_security_event import ThalosSecurityEvent
from app.models.thalos_event import ThalosEvent
from app.models.thalos_workspace_item import ThalosWorkspaceItem
from app.models.user import User
from services.thalos_control_layer_v1 import (
    can_run_active_execution,
    global_status_payload,
    log_execution_attempt,
    wrap_response,
)
from services.thalos_alert_service import list_alerts
from services.thalos_executor import execute_action
from services.thalos_monitor_service import audit_from_db
from services.thalos_monitoring_service import run_monitoring_cycle
from services.workspace_deliverables import (
    primary_company_id_for_user,
    user_has_company_access,
)

router = APIRouter(prefix="/thalos/v1", tags=["thalos-v1"])


class ThalosExecuteRequest(BaseModel):
    action: str = Field(
        ...,
        description="detect_suspicious_activity|block_user|trigger_backup|alert_admin|audit_cashflow_anomaly",
    )
    company_id: Optional[int] = None
    user_email: Optional[str] = None
    hours: int = 24
    payload: Optional[Dict[str, Any]] = None


class ThalosMonitorRequest(BaseModel):
    company_id: Optional[int] = None
    auto_execute: bool = False


@router.get("/status")
def thalos_v1_status(
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    return global_status_payload()


@router.post("/monitor")
def thalos_v1_monitor(
    body: ThalosMonitorRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    # Mitigación interina (AUDIT_FIX_THALOS_SHIELD.md, sección 10.2/10.3): con
    # la configuración por defecto (THALOS_REAL_MONITORING/THALOS_EXECUTION_ENABLED/
    # THALOS_REAL_LOGS_ENABLED=false) `run_monitor_cycle` no llega a invocar
    # `scan_logs` (security_scan queda `{}`), así que hoy esta ruta no es
    # explotable sin cambiar flags de entorno — a diferencia de
    # workspaces.py::workspace_thalos_logs y GET /thalos/v1/audit, que sí lo
    # son sin ninguna condición. Aun así, en cuanto se active la
    # monitorización real (el objetivo final del sistema) esta ruta hereda
    # exactamente la misma fuga cross-tenant de `scan_logs`, así que se aplica
    # el mismo gate por consistencia y para no dejar una fuga latente sin
    # cerrar de antemano.
    if not getattr(current_user, "is_superuser", False):
        raise HTTPException(
            status_code=403,
            detail=(
                "POST /thalos/v1/monitor requiere privilegios de superusuario "
                "(mitigación interina: el motor subyacente audita actividad "
                "global sin filtrar por empresa en cuanto se activa la "
                "monitorización real)."
            ),
        )

    log_execution_attempt(
        module="auditoria_real",
        action="security_monitor",
        allowed=True,
        actor_id=current_user.id,
    )
    if body.company_id is not None:
        if not user_has_company_access(db, current_user, body.company_id):
            raise HTTPException(
                status_code=403,
                detail="El company_id indicado no pertenece al usuario autenticado.",
            )
        cid = body.company_id
    else:
        cid = primary_company_id_for_user(db, current_user)
    result = run_monitoring_cycle(
        db,
        company_id=cid,
        user_id=current_user.id,
        auto_execute=body.auto_execute and can_run_active_execution("auditoria_real", "block_user"),
        force_scan=True,
    )
    db.commit()
    return wrap_response(
        result,
        "auditoria_real",
        data_origin="backend",
        real_execution=True,
    )


@router.post("/execute")
def thalos_v1_execute(
    body: ThalosExecuteRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    # Mitigación interina (AUDIT_FIX_THALOS_SHIELD.md, sección 7.3/8.3):
    # `detect_suspicious_activity` (el equivalente REST de `THALOS.SCAN`)
    # delega en `thalos_security_engine.scan_logs`, que audita
    # `agent_activities`/`thalos_login_attempts` de forma GLOBAL (esas tablas
    # no tienen `company_id`, ver investigación en 7.3) — fuga cross-tenant
    # confirmada en vivo por el revisor. La corrección de raíz (migración de
    # esquema) excede este fix; se restringe a superusuarios mientras tanto.
    if body.action == "detect_suspicious_activity" and not getattr(current_user, "is_superuser", False):
        raise HTTPException(
            status_code=403,
            detail=(
                "detect_suspicious_activity (THALOS.SCAN) requiere privilegios de "
                "superusuario (mitigación interina: el motor subyacente audita "
                "actividad global sin filtrar por empresa hasta que se migre el "
                "esquema)."
            ),
        )

    module = "backup_system" if body.action == "trigger_backup" else "auditoria_real"
    if body.action in ("block_user", "alert_admin"):
        module = "auditoria_real"

    allowed = can_run_active_execution(module, body.action)
    log_execution_attempt(
        module=module,
        action=body.action,
        allowed=allowed,
        actor_id=current_user.id,
    )

    if not allowed or not settings.THALOS_EXECUTION_ENABLED:
        return wrap_response(
            {
                "status": "blocked",
                "action": body.action,
                "executed": False,
                "reason": "REAL_ACTIVE required (THALOS_EXECUTION_ENABLED + module flags)",
            },
            module,
            data_origin="backend",
            real_execution=False,
        )

    if body.action == "trigger_backup" and not settings.THALOS_BACKUP_ENABLED:
        return wrap_response(
            {
                "status": "blocked",
                "action": body.action,
                "executed": False,
                "reason": "THALOS_BACKUP_ENABLED=false",
            },
            "backup_system",
            data_origin="backend",
            real_execution=False,
        )

    # Aislamiento multi-tenant: `body.company_id` lo controla el cliente. Antes
    # se usaba tal cual ("cid = body.company_id or primary_company_id_for_user(...)"),
    # lo que permitía a un tenant autenticado hacerse pasar por otro enviando
    # el company_id real de la víctima en el body — bypass confirmado en vivo
    # contra `block_user` (ver AUDIT_FIX_THALOS_SHIELD.md, sección 8.2) y
    # aplicable igual a las otras 3 acciones de este endpoint
    # (audit_cashflow_anomaly, detect_suspicious_activity, alert_admin). Ahora
    # se valida siempre contra las empresas reales del usuario autenticado
    # (o se permite si es superusuario) antes de usarlo para cualquier acción.
    if body.company_id is not None:
        if not user_has_company_access(db, current_user, body.company_id):
            raise HTTPException(
                status_code=403,
                detail="El company_id indicado no pertenece al usuario autenticado.",
            )
        cid = body.company_id
    else:
        cid = primary_company_id_for_user(db, current_user)
    result = execute_action(
        db,
        body.action,
        company_id=cid,
        user_id=current_user.id,
        user_email=body.user_email,
        hours=body.hours,
        payload=body.payload,
    )
    db.commit()

    # Aislamiento multi-tenant: services.thalos_executor.block_user devuelve
    # status="forbidden" (ya registrado en el log de seguridad, commiteado
    # arriba) cuando el user_email objetivo no pertenece al tenant del
    # solicitante. Aquí, en la vía REST oficial, eso se traduce en un 403
    # real (mismo estilo que services/tpv_service.py:1068), en vez de un 200
    # con el rechazo solo embebido en el cuerpo.
    if result.get("status") == "forbidden":
        raise HTTPException(
            status_code=403,
            detail=result.get("reason") or "El usuario objetivo no pertenece a su empresa.",
        )

    origin = "backend"
    real = bool(result.get("executed"))
    return wrap_response(result, module, data_origin=origin, real_execution=real)


@router.get("/events")
def thalos_v1_events(
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    sec_rows = (
        db.query(ThalosSecurityEvent)
        .order_by(ThalosSecurityEvent.id.desc())
        .limit(min(limit, 200))
        .all()
    )
    parsed_rows = (
        db.query(ThalosEvent)
        .order_by(ThalosEvent.id.desc())
        .limit(min(limit, 200))
        .all()
    )
    events = [
        {
            "id": f"sec-{r.id}",
            "event_type": r.event_type,
            "severity": r.severity,
            "source": r.source,
            "user_email": r.user_email,
            "message": (r.details_json or "")[:200],
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in sec_rows
    ]
    events.extend(
        {
            "id": f"evt-{r.id}",
            "event_type": r.event_type,
            "severity": r.severity,
            "source": r.source,
            "message": r.message,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in parsed_rows
    )
    if not events and getattr(settings, "THALOS_ENABLED", True):
        raise HTTPException(status_code=404, detail="No events in database — run /monitor or enable worker")
    body = {"events": events[:limit], "count": len(events[:limit])}
    return wrap_response(body, "events", data_origin="backend", real_execution=True)


@router.get("/alerts")
def thalos_v1_alerts(
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


@router.get("/audit")
def thalos_v1_audit(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    # Mitigación interina (AUDIT_FIX_THALOS_SHIELD.md, sección 10.2/10.3):
    # audit_from_db() cuenta/lista ThalosEvent/ThalosAlert/ThalosSecurityEvent
    # de forma GLOBAL, sin ningún filtro por company_id (esas tablas no lo
    # tienen) — confirmado en vivo que un tenant nuevo sin actividad propia
    # obtiene event_count/security_event_count y eventos recientes de otras
    # empresas con solo autenticarse, sin flags ni condición alguna. Mismo
    # gate ya aplicado a THALOS.SCAN/detect_suspicious_activity y a
    # workspaces.py::workspace_thalos_logs.
    if not getattr(current_user, "is_superuser", False):
        raise HTTPException(
            status_code=403,
            detail=(
                "GET /thalos/v1/audit requiere privilegios de superusuario "
                "(mitigación interina: el motor subyacente audita actividad "
                "global sin filtrar por empresa hasta que se migre el esquema)."
            ),
        )

    from workers.thalos_worker import worker_status

    report = audit_from_db(db)
    report["worker"] = worker_status()
    report["strict_real_mode"] = True
    return wrap_response(report, "auditoria_real", data_origin="backend", real_execution=True)


@router.get("/workspace/items")
def thalos_v1_workspace_items(
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    rows = (
        db.query(ThalosWorkspaceItem)
        .filter(ThalosWorkspaceItem.user_id == current_user.id)
        .order_by(ThalosWorkspaceItem.id.desc())
        .limit(min(limit, 200))
        .all()
    )
    items = []
    for r in rows:
        payload: Dict[str, Any] = {}
        if r.payload_json:
            try:
                payload = json.loads(r.payload_json)
            except json.JSONDecodeError:
                payload = {}
        items.append(
            {
                "id": r.public_id,
                "db_id": r.id,
                "type": r.item_type,
                "status": r.status,
                "title": r.title,
                "company_id": r.company_id,
                "workspace_document_id": r.workspace_document_id,
                "data_size_kb": r.data_size_kb,
                "source": r.source,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "payload": payload,
            }
        )
    return wrap_response(
        {"success": True, "items": items, "count": len(items)},
        "workspace",
        data_origin="backend",
        real_execution=True,
    )
