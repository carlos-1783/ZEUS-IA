"""
🧠 TeamFlow API
Endpoints para exponer workflows multiagente y ejecuciones.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Any, Dict, Optional

from app.core.auth import get_current_active_user
from app.models.user import User
from services.teamflow_engine import teamflow_engine


router = APIRouter(prefix="/teamflow", tags=["teamflow"])


class TeamFlowRunRequest(BaseModel):
    workflow_payload: Optional[Dict[str, Any]] = None
    requested_by: Optional[str] = None


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

