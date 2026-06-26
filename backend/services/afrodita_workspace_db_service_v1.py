"""AFRODITA workspace DB — files y playbooks persistidos."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.models.workspace_file import WorkspaceFile
from app.models.workspace_playbook import WorkspacePlaybook
from services.workspace_deliverables import primary_company_id_for_user

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

logger = logging.getLogger(__name__)

AGENT_NAME = "AFRODITA"


def workspace_enabled() -> bool:
    return bool(getattr(settings, "AFRODITA_WORKSPACE_ENABLED", True))


def workspace_connection_status(db: Optional[Session]) -> Dict[str, Any]:
    db_ok = _probe_db_connected(db)
    enabled = workspace_enabled()
    connected = bool(enabled and db_ok)
    return {
        "enabled": enabled,
        "connected": connected,
        "db_connected": db_ok,
        "files_api": "/api/v1/afrodita/workspace/files",
        "playbooks_api": "/api/v1/afrodita/workspace/playbooks",
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
    _assert_workspace_available(db)
    rows = (
        db.query(WorkspacePlaybook)
        .filter(
            WorkspacePlaybook.user_id == user.id,
            WorkspacePlaybook.agent_name == AGENT_NAME,
        )
        .order_by(WorkspacePlaybook.id.desc())
        .limit(min(limit, 200))
        .all()
    )
    playbooks: List[Dict[str, Any]] = []
    for r in rows:
        payload: Dict[str, Any] = {}
        if r.content:
            try:
                payload = json.loads(r.content)
            except json.JSONDecodeError:
                payload = {"summary": r.content}
        playbooks.append(
            {
                "id": r.id,
                "title": r.title,
                "content": payload,
                "raw_content": r.content,
                "company_id": r.company_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
        )
    return {
        "playbooks": playbooks,
        "count": len(playbooks),
        "source": "workspace_playbooks",
        **workspace_connection_status(db),
    }


def persist_workspace_playbook(
    db: Session,
    user: User,
    *,
    title: str,
    content: Dict[str, Any],
    company_id: Optional[int] = None,
) -> WorkspacePlaybook:
    _assert_workspace_available(db)
    cid = company_id or primary_company_id_for_user(db, user)
    row = WorkspacePlaybook(
        user_id=user.id,
        company_id=cid,
        agent_name=AGENT_NAME,
        title=(title or "Playbook AFRODITA")[:255],
        content=json.dumps(content, ensure_ascii=False),
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    logger.info("[AFRODITA_WORKSPACE] playbook persisted id=%s user=%s", row.id, user.id)
    return row


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
