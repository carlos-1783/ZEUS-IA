"""AFRODITA workspace API — files y playbooks desde BD."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from services.afrodita_unified_control import get_global_status, wrap_response
from services.afrodita_workspace_db_service_v1 import (
    list_workspace_files,
    list_workspace_playbooks,
    workspace_connection_status,
)

router = APIRouter(prefix="/afrodita/workspace", tags=["afrodita-workspace"])


@router.get("/status")
def afrodita_workspace_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ = current_user
    global_status = get_global_status(db)
    ws = workspace_connection_status(db)
    return {
        **global_status,
        "workspace": ws,
        "domain": "workspace",
    }


@router.get("/files")
def afrodita_workspace_files(
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    body = list_workspace_files(db, current_user, limit=limit)
    return wrap_response(
        {"success": True, **body},
        db=db,
        data_origin="backend",
        persisted=True,
        read_only=True,
    )


@router.get("/playbooks")
def afrodita_workspace_playbooks(
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    body = list_workspace_playbooks(db, current_user, limit=limit)
    return wrap_response(
        {"success": True, **body},
        db=db,
        data_origin="backend",
        persisted=True,
        read_only=True,
    )
