"""Workspace playbooks — persistencia unificada (AFRODITA + dominios)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.models.workspace_playbook import WorkspacePlaybook
from services.workspace_deliverables import primary_company_id_for_user

logger = logging.getLogger(__name__)

AGENT_ROOT = "AFRODITA"
VALID_AGENT_SOURCES = frozenset({"rrhh", "ops", "logistics", "afrodita", "automation"})


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
    return bool(getattr(settings, "AFRODITA_WORKSPACE_ENABLED", True))


def _assert_workspace_available(db: Session) -> None:
    if not workspace_enabled():
        raise HTTPException(
            status_code=503,
            detail="AFRODITA_WORKSPACE_ENABLED=false — workspace deshabilitado",
        )
    if not _probe_db_connected(db):
        raise HTTPException(status_code=500, detail="Base de datos no disponible")


def _normalize_agent_source(agent_source: Optional[str]) -> str:
    src = (agent_source or "afrodita").strip().lower()
    if src not in VALID_AGENT_SOURCES:
        return "afrodita"
    return src


def _row_to_dict(row: WorkspacePlaybook) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    if row.content:
        try:
            payload = json.loads(row.content)
        except json.JSONDecodeError:
            payload = {"summary": row.content}
    return {
        "id": row.id,
        "title": row.title,
        "content": payload,
        "agent_source": row.agent_source or row.agent_name,
        "agent_name": row.agent_name,
        "company_id": row.company_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def list_playbooks(
    db: Session,
    user: User,
    *,
    limit: int = 100,
    agent_source: Optional[str] = None,
) -> Dict[str, Any]:
    _assert_workspace_available(db)
    q = db.query(WorkspacePlaybook).filter(
        WorkspacePlaybook.user_id == user.id,
        WorkspacePlaybook.agent_name == AGENT_ROOT,
    )
    if agent_source:
        q = q.filter(WorkspacePlaybook.agent_source == _normalize_agent_source(agent_source))
    rows = q.order_by(WorkspacePlaybook.id.desc()).limit(min(limit, 200)).all()
    playbooks = [_row_to_dict(r) for r in rows]
    return {
        "playbooks": playbooks,
        "count": len(playbooks),
        "source": "workspace_playbooks",
        "agent_filter": agent_source,
    }


def create_playbook(
    db: Session,
    user: User,
    *,
    title: str,
    content: Dict[str, Any],
    agent_source: str = "afrodita",
    company_id: Optional[int] = None,
) -> WorkspacePlaybook:
    _assert_workspace_available(db)
    src = _normalize_agent_source(agent_source)
    cid = company_id or primary_company_id_for_user(db, user)
    body = {
        **content,
        "agent_source": src,
        "persisted_at": datetime.now(timezone.utc).isoformat(),
    }
    row = WorkspacePlaybook(
        user_id=user.id,
        company_id=cid,
        agent_name=AGENT_ROOT,
        agent_source=src,
        title=(title or f"Playbook {src}")[:255],
        content=json.dumps(body, ensure_ascii=False),
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    logger.info(
        "[WORKSPACE_PLAYBOOK] id=%s user=%s source=%s title=%s",
        row.id,
        user.id,
        src,
        row.title,
    )
    return row


def persist_execution_playbook(
    db: Session,
    user: User,
    *,
    agent_source: str,
    action: str,
    title: str,
    payload: Dict[str, Any],
    summary: Optional[str] = None,
) -> Optional[WorkspacePlaybook]:
    """Auto-persist tras ejecución real de dominio AFRODITA."""
    from services.zeus_transaction_context_v1 import get_active_transaction_id, workspace_writes_allowed

    if get_active_transaction_id() and not workspace_writes_allowed():
        logger.info(
            "[WORKSPACE_PLAYBOOK] deferred until transaction commit tx=%s",
            get_active_transaction_id(),
        )
        return None
    if not workspace_enabled():
        return None
    try:
        content = {
            "action": action,
            "summary": summary or title,
            "result": payload,
            "execution": "REAL",
        }
        return create_playbook(
            db,
            user,
            title=title,
            content=content,
            agent_source=agent_source,
        )
    except Exception:
        logger.exception("[WORKSPACE_PLAYBOOK] auto-persist failed source=%s action=%s", agent_source, action)
        return None
