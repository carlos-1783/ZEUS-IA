"""Workspace playbooks API — GET/POST genérico."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from services.afrodita_unified_control import assert_can_write, wrap_response
from services.workspace_playbook_service_v1 import create_playbook, list_playbooks

router = APIRouter(prefix="/workspace", tags=["workspace-playbooks"])


class PlaybookCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    content: Dict[str, Any] = Field(default_factory=dict)
    agent_source: str = Field(default="afrodita")


@router.get("/playbooks")
def workspace_playbooks_list(
    limit: int = 100,
    agent_source: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    body = list_playbooks(db, current_user, limit=limit, agent_source=agent_source)
    return wrap_response(
        {"success": True, **body},
        db=db,
        data_origin="backend",
        persisted=True,
        read_only=True,
    )


@router.post("/playbooks/create")
def workspace_playbook_create(
    body: PlaybookCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    assert_can_write(db)
    row = create_playbook(
        db,
        current_user,
        title=body.title,
        content=body.content,
        agent_source=body.agent_source,
    )
    db.commit()
    return wrap_response(
        {
            "success": True,
            "playbook_id": row.id,
            "title": row.title,
            "agent_source": row.agent_source,
            "message": "Playbook persistido en workspace_playbooks",
        },
        db=db,
        data_origin="user_input",
        persisted=True,
    )
