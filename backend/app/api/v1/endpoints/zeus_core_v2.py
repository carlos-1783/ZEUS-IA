"""ZEUS final closure v2 — scoring, agenda, approvals, agent execution, métricas."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi.responses import JSONResponse
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
import services.crm_office_service as crm_svc
from services.zeus_agent_executor_v1 import execute_agent_action
from services.zeus_agenda_optimizer_v1 import propose_meeting_slots, schedule_meeting
from services.zeus_core_metrics_v1 import get_core_metrics
from services.zeus_core_workspace_bootstrap_v1 import run_zeus_core_workspace_bootstrap
from services.zeus_external_intelligence_v1 import research_business
from services.thalos_request_guard_v1 import thalos_request_guard
from services.zeus_human_approval_v1 import execute_approval, list_pending, resolve_approval
from services.zeus_scoring_engine_v1 import convert_lead_to_customer, create_lead, score_lead

router = APIRouter()
logger = logging.getLogger(__name__)


class AgentExecuteRequest(BaseModel):
    agent: str = Field(..., description="ZEUS|RAFAEL|PERSEO")
    action: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    # force_execute ya NO existe en el schema: si un cliente lo envia se ignora
    # (pydantic descarta campos extra). Las acciones criticas solo se ejecutan
    # tras la aprobacion del mismo usuario (POST /approvals/{id}/resolve).


class LeadCreateRequest(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    sector: Optional[str] = None
    estimated_value: Optional[float] = None


class ScheduleMeetingRequest(BaseModel):
    start_iso: str


class ApprovalResolveRequest(BaseModel):
    approve: bool = True


class WorkspaceBootstrapRequest(BaseModel):
    analysis_only: bool = True
    persist_artifact: bool = True
    company_id: Optional[int] = None


@router.get("/metrics")
def core_metrics(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return {"success": True, **get_core_metrics(db, user=current_user, days=days)}


@router.post("/agent/execute")
async def agent_execute(
    body: AgentExecuteRequest,
    current_user: User = Depends(thalos_request_guard),
    db: Session = Depends(get_db),
):
    return await execute_agent_action(
        db,
        user=current_user,
        agent=body.agent,
        action=body.action,
        payload=body.payload,
    )


@router.get("/approvals/pending")
def approvals_pending(
    company_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    cid = company_id or crm_svc.primary_company_id(db, current_user)
    if not cid:
        raise HTTPException(status_code=400, detail="company_id requerido")
    return {"success": True, "pending": list_pending(db, user=current_user, company_id=cid)}


@router.post("/approvals/{approval_id}/resolve")
async def approvals_resolve(
    approval_id: int,
    body: ApprovalResolveRequest,
    current_user: User = Depends(thalos_request_guard),
    db: Session = Depends(get_db),
):
    """approve=true: el solicitante confirma y el SERVIDOR ejecuta la accion
    almacenada (una sola vez). approve=false: rechaza sin ejecutar."""
    import json

    row = resolve_approval(db, approval_id=approval_id, user=current_user, approve=body.approve)
    if not body.approve:
        return {"success": True, "status": row.status}
    row = await execute_approval(db, row=row, user=current_user)
    outcome = json.loads(row.result_json or "{}")
    base = {
        "approval_id": row.id,
        "status": row.status,
        "agent": row.agent_name,
        "action": row.action_type,
    }
    if row.status == "executed":
        return {"success": True, **base, "result": outcome.get("result")}
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"success": False, **base, "error": outcome.get("error"), "result": outcome.get("result")},
    )


@router.post("/leads")
def leads_create(
    body: LeadCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    lead = create_lead(
        db,
        user=current_user,
        name=body.name,
        email=body.email,
        phone=body.phone,
        sector=body.sector,
        estimated_value=body.estimated_value,
    )
    return {
        "success": True,
        "lead_id": lead.id,
        "lead_score": lead.lead_score,
        "customer_priority": lead.customer_priority,
        "next_best_action": lead.next_best_action,
    }


@router.post("/leads/{lead_id}/score")
def leads_score(
    lead_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return {"success": True, **score_lead(db, user=current_user, lead_id=lead_id)}


@router.get("/leads/{lead_id}/agenda/slots")
def agenda_slots(
    lead_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return {"success": True, **propose_meeting_slots(db, user=current_user, lead_id=lead_id)}


@router.post("/leads/{lead_id}/agenda/schedule")
def agenda_schedule(
    lead_id: int,
    body: ScheduleMeetingRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return {"success": True, **schedule_meeting(db, user=current_user, lead_id=lead_id, start_iso=body.start_iso)}


@router.post("/leads/{lead_id}/convert")
def leads_convert(
    lead_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return {"success": True, **convert_lead_to_customer(db, user=current_user, lead_id=lead_id)}


@router.post("/intelligence/research")
def external_research(
    query: str = Query(...),
    lead_id: Optional[int] = Query(None),
    customer_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return research_business(
        db, user=current_user, query=query, lead_id=lead_id, customer_id=customer_id
    )


@router.post("/workspace-bootstrap")
def workspace_bootstrap(
    body: WorkspaceBootstrapRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return run_zeus_core_workspace_bootstrap(
        db,
        user=current_user,
        analysis_only=body.analysis_only,
        persist_artifact=body.persist_artifact,
        company_id=body.company_id,
    )


# ----------------------------------------------------------------------------
# Endpoints de estado/auditoría, migrados desde el antiguo
# app/api/v1/endpoints/zeus_core.py (Bloque 3, limpieza de simulación). Ese
# archivo mezclaba estos endpoints reales (llaman a servicios reales:
# zeus_execution_controller_v1, zeus_safe_lock_v1, zeus_controlled_repair_v1,
# zeus_full_completion_v1, zeus_document_pipeline_v1) con /activate, /execute,
# /agents y /commands, que solo devolvían dicts fijos de
# app/core/zeus_agents.py (ZeusAgent en memoria, sin persistencia real,
# "status": "success" hardcodeado siempre). Esos cuatro se eliminaron junto
# con zeus_agents.py; estos cuatro se migraron aquí, al orquestador real,
# quitando la única referencia que tenían al zeus_manager legacy (el campo
# "timestamp"/"data.legacy" de /status, que ningún consumidor real leía —
# ver frontend/src/api/zeus_status_api.ts).
# ----------------------------------------------------------------------------


@router.get("/status")
async def get_zeus_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Estado real de ejecución del núcleo ZEUS: execution_mode, writes_enabled,
    módulos conectados y safe_lock (zeus_execution_controller_v1 /
    zeus_safe_lock_v1) — no simulado."""
    from datetime import datetime

    from services.zeus_data_pipeline_v1 import get_pipeline_status
    from services.zeus_execution_controller_v1 import get_execution_status
    from services.zeus_safe_lock_v1 import run_safe_lock

    try:
        execution = get_execution_status(db)
        pipeline_user = get_pipeline_status(db, current_user.id)
        safe_lock = run_safe_lock(db, execution_status=execution, log_warnings=True)

        return {
            "status": "success",
            "message": "Estado del Núcleo ZEUS obtenido correctamente",
            "timestamp": datetime.utcnow().isoformat(),
            "execution_mode": execution["execution_mode"],
            "writes_enabled": execution["writes_enabled"],
            "db_status": execution["db_status"],
            "connected_modules": execution["connected_modules"],
            "modules": execution["modules"],
            "simulation_layers_present": execution["simulation_layers_present"],
            "flag_consistency": execution["flag_consistency"],
            "verified_real": safe_lock["verified_real"],
            "safe_lock": safe_lock,
            "pipeline": {**execution["pipeline"], "user": pipeline_user},
        }
    except Exception as e:
        logger.error(f"Error obteniendo estado ZEUS: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo estado: {str(e)}",
        )


@router.get("/repair/status")
async def get_zeus_repair_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Auditoría secuencial de fases controlled_repair (sin mutaciones)."""
    from services.zeus_controlled_repair_v1 import run_controlled_repair

    return run_controlled_repair(db, current_user, stop_on_error=False)


@router.get("/completion/status")
async def get_zeus_completion_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Valida las fases de zeus_full_completion_v1 para ejecución 100% real."""
    from services.zeus_full_completion_v1 import run_full_completion

    return run_full_completion(db, current_user, stop_on_error=False)


@router.get("/document-pipeline/status")
async def get_zeus_document_pipeline_status(
    current_user: User = Depends(get_current_active_user),
):
    """Estado del pipeline de documentos cross-agent."""
    from services.zeus_document_pipeline_v1 import pipeline_status

    return {"success": True, **pipeline_status()}
