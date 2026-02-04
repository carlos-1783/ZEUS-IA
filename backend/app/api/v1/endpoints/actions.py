"""
POST /actions/execute — Unified real action execution entrypoint.
Flow: permission_check → activity_write_pending → handler_execution_or_block → activity_write_final → ui_feedback.
No action completes without handler; missing handler → blocked_missing_handler.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.auth import get_current_active_user
from app.db.session import SessionLocal
from app.models.agent_activity import AgentActivity
from app.models.user import User
from services.activity_logger import ActivityLogger
from services.automation.handlers import resolve_handler
from services.automation.utils import merge_dict
from services.unified_agent_runtime import run_workspace_task


router = APIRouter(prefix="/actions", tags=["actions"])


class ActionsExecuteRequest(BaseModel):
    agent: str
    action_type: str
    payload: Optional[Dict[str, Any]] = None
    sync: bool = False


class ActionsExecuteResponse(BaseModel):
    activity_id: int
    status: str  # pending | in_progress | executed | executed_internal | blocked_missing_handler | failed
    executed_handler: Optional[str] = None


def _require_superuser(current_user: User) -> None:
    if not getattr(current_user, "is_superuser", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only SUPERUSER can call POST /actions/execute.",
        )


@router.post("/execute", response_model=ActionsExecuteResponse)
async def actions_execute(
    body: ActionsExecuteRequest,
    current_user: User = Depends(get_current_active_user),
):
    """
    Unified real action execution.
    Writes to agent_activities; no action completes without handler.
    Missing handler → status blocked_missing_handler.
    """
    _require_superuser(current_user)

    agent = (body.agent or "").strip().upper()
    action_type = (body.action_type or "").strip()
    payload = body.payload or {}
    sync = body.sync

    if not agent or not action_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="agent and action_type are required.",
        )

    # activity_write_pending
    activity = ActivityLogger.log_activity(
        agent_name=agent,
        action_type=action_type,
        action_description=payload.get("description") or f"{agent} / {action_type}",
        details=payload,
        user_email=current_user.email,
        status="pending",
        priority="normal",
        visible_to_client=True,
    )
    if not activity:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create activity.",
        )
    activity_id = activity.id

    if not sync:
        return ActionsExecuteResponse(
            activity_id=activity_id,
            status="pending",
            executed_handler=None,
        )

    # sync: handler_execution_or_block → activity_write_final
    session = SessionLocal()
    try:
        activity = session.query(AgentActivity).filter(AgentActivity.id == activity_id).first()
        if not activity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found.")

        handler = resolve_handler(activity.agent_name, activity.action_type or "")

        if handler is None:
            activity.status = "blocked_missing_handler"
            session.add(activity)
            session.commit()
            return ActionsExecuteResponse(
                activity_id=activity_id,
                status="blocked_missing_handler",
                executed_handler=None,
            )

        result = run_workspace_task(activity)
        status_val = result.get("status", "completed")

        activity.status = status_val
        if "details_update" in result:
            activity.details = merge_dict(activity.details, result["details_update"])
        if "metrics_update" in result:
            activity.metrics = merge_dict(activity.metrics, result["metrics_update"])
        if result.get("executed_handler") is not None:
            activity.metrics = merge_dict(activity.metrics or {}, {"executed_handler": result["executed_handler"]})
        if status_val in ("completed", "executed_internal", "failed"):
            activity.completed_at = datetime.utcnow()

        session.add(activity)
        session.commit()

        return ActionsExecuteResponse(
            activity_id=activity_id,
            status=status_val,
            executed_handler=result.get("executed_handler"),
        )
    finally:
        session.close()
