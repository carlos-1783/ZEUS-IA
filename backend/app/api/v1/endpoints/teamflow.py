"""
🧠 TeamFlow API
Endpoints para exponer workflows multiagente y ejecuciones.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Any, Dict, Optional

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from sqlalchemy.orm import Session
from services.teamflow_engine import teamflow_engine


router = APIRouter(prefix="/teamflow", tags=["teamflow"])


class TeamFlowRunRequest(BaseModel):
    workflow_payload: Optional[Dict[str, Any]] = None
    requested_by: Optional[str] = None


class TeamFlowChatExecuteRequest(BaseModel):
    message: str
    thread_id: Optional[str] = "main"
    force_execute: bool = False


@router.get("/workflows")
async def list_workflows(_: User = Depends(get_current_active_user)):
    return {
        "success": True,
        "workflows": teamflow_engine.list_workflows(),
    }


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
    current_user: User = Depends(get_current_active_user),
):
    try:
        result = teamflow_engine.run_workflow(
            workflow_id=workflow_id,
            payload=request.workflow_payload,
            actor=request.requested_by or current_user.email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {"success": True, **result}


@router.get("/integrations")
async def validate_integrations(_: User = Depends(get_current_active_user)):
    return {
        "success": True,
        **teamflow_engine.validate_integrations(),
    }


@router.post("/execute-from-chat")
async def execute_from_chat(
    request: TeamFlowChatExecuteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Ejecuta intent → task → acción (mismo puente que el chat de ZEUS Core)."""
    from services.teamflow_orchestrator import try_handle_zeus_chat

    bridge = await try_handle_zeus_chat(
        db,
        current_user,
        request.message,
        {"thread_id": request.thread_id or "main"},
        force_execute=request.force_execute,
    )
    if not bridge or not bridge.get("handled"):
        return {
            "success": True,
            "handled": False,
            "message": "No se detectó una acción ejecutable en el mensaje.",
        }
    return {"success": bridge.get("success", False), **bridge}

