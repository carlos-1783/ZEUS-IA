"""
🧠 TeamFlow API — workflows multiagente con persistencia real en BD.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from services import chat_persistence_service as chat_db
from services.activity_logger import ActivityLogger
from services.teamflow_audit_service_v1 import run_full_audit
from services.teamflow_engine import teamflow_engine
from services.thalos_request_guard_v1 import thalos_request_guard
from services.teamflow_persistence_v1 import create_item, list_items, update_item_status

router = APIRouter(prefix="/teamflow", tags=["teamflow"])


class TeamFlowRunRequest(BaseModel):
    workflow_payload: Optional[Dict[str, Any]] = None
    requested_by: Optional[str] = None


class TeamFlowChatExecuteRequest(BaseModel):
    message: str
    thread_id: Optional[str] = "main"
    # J3: `force_execute` ya no existe; si un cliente lo envia, pydantic lo ignora.


class TeamFlowCreateRequest(BaseModel):
    owner_agent: str
    title: str
    item_type: str = "flow"
    status: str = "draft"
    source_agent: Optional[str] = None
    target_agent: Optional[str] = None
    workflow_id: Optional[str] = None
    content: Optional[Dict[str, Any]] = None


class TeamFlowUpdateRequest(BaseModel):
    status: str
    owner_agent: Optional[str] = None


@router.get("/list")
async def teamflow_list(
    owner_agent: Optional[str] = None,
    agent: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    items = list_items(
        db,
        current_user,
        owner_agent=owner_agent,
        agent=agent,
        status=status,
        limit=limit,
    )
    return {"success": True, "items": items, "count": len(items), "data_origin": "database"}


@router.post("/create")
async def teamflow_create(
    body: TeamFlowCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    company_id = chat_db.resolve_company_id(db, current_user)
    item = create_item(
        db,
        current_user,
        owner_agent=body.owner_agent,
        title=body.title,
        item_type=body.item_type,
        status=body.status,
        source_agent=body.source_agent,
        target_agent=body.target_agent,
        workflow_id=body.workflow_id,
        content=body.content,
        company_id=company_id,
    )
    db.commit()
    return {"success": True, "item": item, "real_execution": True}


@router.patch("/update/{item_id}")
async def teamflow_update(
    item_id: str,
    body: TeamFlowUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    item = update_item_status(
        db,
        current_user,
        item_id,
        status=body.status,
        owner_agent=body.owner_agent,
    )
    db.commit()
    return {"success": True, "item": item, "real_execution": True}


@router.get("/audit")
async def teamflow_audit(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    report = run_full_audit(db, current_user)
    if report.get("fail_on_inconsistency") and not report.get("passed"):
        raise HTTPException(status_code=409, detail=report)
    return {"success": True, **report}


@router.get("/workflows")
async def list_workflows(_: User = Depends(get_current_active_user)):
    return {"success": True, "workflows": teamflow_engine.list_workflows()}


@router.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str, _: User = Depends(get_current_active_user)):
    try:
        workflow = teamflow_engine.get_workflow(workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return {
        "success": True,
        "workflow": {
            "id": workflow.workflow_id,
            "title": workflow.title,
            "summary": workflow.summary,
            "category": workflow.category,
            "success_criteria": workflow.success_criteria,
            "agents": workflow.agents,
            "entry_conditions": workflow.entry_conditions,
            "steps": [
                {
                    "id": step.id,
                    "name": step.name,
                    "agent": step.agent,
                    "depends_on": step.depends_on,
                    "handoff_to": step.handoff_to,
                    "expected_output": step.expected_output,
                }
                for step in workflow.steps
            ],
        },
        "connections": teamflow_engine.connect_agents(workflow_id),
    }


@router.post("/workflows/{workflow_id}/run")
async def run_workflow(
    workflow_id: str,
    request: TeamFlowRunRequest,
    current_user: User = Depends(thalos_request_guard),
    db: Session = Depends(get_db),
):
    try:
        company_id = chat_db.resolve_company_id(db, current_user)
        result = teamflow_engine.run_workflow(
            workflow_id=workflow_id,
            payload=request.workflow_payload,
            actor=request.requested_by or current_user.email,
            db=db,
            user=current_user,
            company_id=company_id,
        )
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {"success": True, **result}


@router.get("/integrations")
async def validate_integrations(_: User = Depends(get_current_active_user)):
    return {"success": True, **teamflow_engine.validate_integrations()}


@router.post("/execute-from-chat")
async def execute_from_chat(
    request: TeamFlowChatExecuteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(thalos_request_guard),
):
    from app.api.v1.endpoints.chat import build_server_context
    from services.zeus_orchestrator_service import try_handle_zeus_chat

    thread_id = request.thread_id or "main"
    company_id = chat_db.resolve_company_id(db, current_user)
    chat_db.save_message(
        db,
        user=current_user,
        agent_name="ZEUS CORE",
        thread_id=thread_id,
        role="user",
        message=request.message,
        company_id=company_id,
    )

    bridge = await try_handle_zeus_chat(
        db,
        current_user,
        request.message,
        build_server_context(db, current_user, {}, thread_id),
    )
    out_msg = (bridge or {}).get("message") or "No se detectó una acción ejecutable en el mensaje."
    chat_db.save_message(
        db,
        user=current_user,
        agent_name="ZEUS CORE",
        thread_id=thread_id,
        role="assistant",
        message=str(out_msg),
        company_id=company_id,
    )
    ActivityLogger.log_activity(
        agent_name="ZEUS CORE",
        action_type="teamflow_execute_from_chat",
        action_description="Ejecución operativa desde TeamFlow/chat",
        details={
            "thread_id": thread_id,
            "handled": bool((bridge or {}).get("handled")),
            "executed": bool((bridge or {}).get("executed")),
            "company_id": company_id,
            "needs_confirmation": bool((bridge or {}).get("needs_confirmation")),
            "success": bool((bridge or {}).get("success")),
        },
        user_email=current_user.email,
        status="failed" if ((bridge or {}).get("handled") and not bridge.get("success")) else "completed",
        priority="normal",
        visible_to_client=True,
    )
    if not bridge or not bridge.get("handled"):
        return {"success": True, "handled": False, "message": out_msg}
    return {"success": bridge.get("success", False), **bridge}
