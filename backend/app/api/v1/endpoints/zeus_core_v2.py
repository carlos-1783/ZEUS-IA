"""ZEUS final closure v2 — scoring, agenda, approvals, agent execution, métricas."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
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
from services.zeus_human_approval_v1 import list_pending, resolve_approval
from services.zeus_scoring_engine_v1 import convert_lead_to_customer, create_lead, score_lead

router = APIRouter()


class AgentExecuteRequest(BaseModel):
    agent: str = Field(..., description="ZEUS|RAFAEL|PERSEO")
    action: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    force_execute: bool = False


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
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return await execute_agent_action(
        db,
        user=current_user,
        agent=body.agent,
        action=body.action,
        payload=body.payload,
        force_execute=body.force_execute,
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
def approvals_resolve(
    approval_id: int,
    body: ApprovalResolveRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    row = resolve_approval(db, approval_id=approval_id, user=current_user, approve=body.approve)
    if body.approve:
        import json

        payload = json.loads(row.payload_json or "{}")
        return {
            "success": True,
            "status": row.status,
            "hint": "Ejecuta POST /zeus-core/agent/execute con force_execute=true y el mismo payload.",
            "agent": row.agent_name,
            "action": row.action_type,
            "payload": payload,
        }
    return {"success": True, "status": row.status}


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
