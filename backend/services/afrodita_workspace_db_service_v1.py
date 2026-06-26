"""AFRODITA workspace DB — files y playbooks persistidos."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.models.workspace_file import WorkspaceFile
from app.models.workspace_playbook import WorkspacePlaybook
from services.workspace_deliverables import primary_company_id_for_user
from services.workspace_playbook_service_v1 import (
    create_playbook,
    list_playbooks,
    workspace_enabled as _workspace_enabled,
)

logger = logging.getLogger(__name__)

AGENT_NAME = "AFRODITA"


def _probe_db_connected(db: Optional[Session]) -> bool:
    if db is None:
        return bool(getattr(settings, "DATABASE_URL", None))
    try:
        from sqlalchemy import text

        db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def workspace_enabled() -> bool:
    return _workspace_enabled()


def workspace_connection_status(db: Optional[Session]) -> Dict[str, Any]:
    db_ok = _probe_db_connected(db)
    enabled = workspace_enabled()
    connected = bool(enabled and db_ok)
    return {
        "enabled": enabled,
        "connected": connected,
        "db_connected": db_ok,
        "files_api": "/api/v1/afrodita/workspace/files",
        "playbooks_api": "/api/v1/workspace/playbooks",
        "playbooks_create_api": "/api/v1/workspace/playbooks/create",
        "status": "REAL" if connected else ("ERROR" if not db_ok else "SIMULATED"),
    }


def _assert_workspace_available(db: Session) -> None:
    if not workspace_enabled():
        raise HTTPException(
            status_code=503,
            detail="AFRODITA_WORKSPACE_ENABLED=false — workspace deshabilitado",
        )
    if not _probe_db_connected(db):
        raise HTTPException(status_code=500, detail="Base de datos no disponible")


def list_workspace_files(db: Session, user: User, *, limit: int = 100) -> Dict[str, Any]:
    _assert_workspace_available(db)
    rows = (
        db.query(WorkspaceFile)
        .filter(
            WorkspaceFile.user_id == user.id,
            WorkspaceFile.agent_name == AGENT_NAME,
        )
        .order_by(WorkspaceFile.updated_at.desc(), WorkspaceFile.id.desc())
        .limit(min(limit, 200))
        .all()
    )
    files = [
        {
            "id": r.id,
            "name": r.name,
            "content": r.content,
            "company_id": r.company_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]
    return {
        "files": files,
        "count": len(files),
        "source": "workspace_files",
        **workspace_connection_status(db),
    }


def list_workspace_playbooks(db: Session, user: User, *, limit: int = 100) -> Dict[str, Any]:
    body = list_playbooks(db, user, limit=limit)
    return {**body, **workspace_connection_status(db)}


def persist_workspace_playbook(
    db: Session,
    user: User,
    *,
    title: str,
    content: Dict[str, Any],
    company_id: Optional[int] = None,
    agent_source: str = "automation",
) -> WorkspacePlaybook:
    _ = company_id
    return create_playbook(
        db,
        user,
        title=title,
        content=content,
        agent_source=agent_source,
    )


def persist_workspace_file(
    db: Session,
    user: User,
    *,
    name: str,
    content: str,
    company_id: Optional[int] = None,
) -> WorkspaceFile:
    _assert_workspace_available(db)
    cid = company_id or primary_company_id_for_user(db, user)
    row = WorkspaceFile(
        user_id=user.id,
        company_id=cid,
        agent_name=AGENT_NAME,
        name=(name or "workspace-file")[:255],
        content=content,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    logger.info("[AFRODITA_WORKSPACE] file persisted id=%s user=%s", row.id, user.id)
    return row
