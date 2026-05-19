"""Persistencia de mensajes de chat en base de datos."""

from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.chat_message import ChatMessage
from app.models.user import User
import services.crm_office_service as crm_svc

logger = logging.getLogger(__name__)

MAX_HISTORY = 500


def normalize_agent_name(agent_name: str) -> str:
    return (agent_name or "ZEUS CORE").upper().replace("-", " ").replace("_", " ").strip()


def resolve_company_id(db: Session, user: User) -> Optional[int]:
    try:
        return crm_svc.primary_company_id(db, user)
    except Exception:
        logger.debug("resolve_company_id: sin empresa para user_id=%s", user.id)
        return None


def save_message(
    db: Session,
    *,
    user: User,
    agent_name: str,
    thread_id: str,
    role: str,
    message: str,
    company_id: Optional[int] = None,
) -> Optional[ChatMessage]:
    text = (message or "").strip()
    if not text:
        return None
    role_norm = (role or "user").strip().lower()
    if role_norm not in ("user", "assistant", "system"):
        role_norm = "user"
    cid = company_id if company_id is not None else resolve_company_id(db, user)
    row = ChatMessage(
        company_id=cid,
        user_id=user.id,
        agent_name=normalize_agent_name(agent_name),
        thread_id=(thread_id or "main").strip() or "main",
        role=role_norm,
        message=text[:50000],
    )
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    except Exception:
        db.rollback()
        logger.exception("save_message failed user_id=%s agent=%s", user.id, agent_name)
        return None


def list_messages(
    db: Session,
    *,
    user: User,
    agent_name: str,
    thread_id: str = "main",
    limit: int = MAX_HISTORY,
) -> List[ChatMessage]:
    agent = normalize_agent_name(agent_name)
    tid = (thread_id or "main").strip() or "main"
    limit = max(1, min(limit, MAX_HISTORY))
    q = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.user_id == user.id,
            ChatMessage.agent_name == agent,
            ChatMessage.thread_id == tid,
        )
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
    )
    rows = q.limit(limit).all()
    if len(rows) >= limit:
        return rows
    return rows
