"""
Entregables de workspace: estructura fija, persistencia en document_approvals, visibles en /documents/pending.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.company import UserCompany
from app.models.document_approval import DocumentApproval
from app.models.user import User

logger = logging.getLogger(__name__)

WORKSPACE_DOCUMENT_TYPES: List[str] = [
    "marketing_campaign",
    "social_media_post",
    "fiscal_document",
    "legal_document",
    "hr_document",
]

AGENT_WORKSPACE_CATEGORY: Dict[str, str] = {
    "PERSEO": "marketing_campaign",
    "RAFAEL": "fiscal_document",
    "JUSTICIA": "legal_document",
    "AFRODITA": "hr_document",
}

DEFAULT_CONTENT_TYPE: Dict[str, str] = {
    "PERSEO": "social_media_post",
    "RAFAEL": "fiscal_document",
    "JUSTICIA": "legal_document",
    "AFRODITA": "hr_document",
}


def primary_company_id_for_user(db: Session, user: User) -> Optional[int]:
    row = (
        db.query(UserCompany)
        .filter(UserCompany.user_id == user.id)
        .order_by(UserCompany.id.asc())
        .first()
    )
    return int(row.company_id) if row else None


def build_structured_payload(
    *,
    title: str,
    content_type: str,
    content: Any,
    status: str = "draft",
    visible_in_workspace: bool = True,
) -> Dict[str, Any]:
    body: Dict[str, Any]
    if isinstance(content, dict):
        body = content
    else:
        body = {"body": content}
    return {
        "title": title,
        "type": content_type,
        "content": body,
        "status": status,
        "visible_in_workspace": visible_in_workspace,
    }


def persist_workspace_deliverable(
    db: Session,
    *,
    user_id: int,
    company_id: Optional[int],
    agent_name: str,
    workspace_category: str,
    title: str,
    content_type: str,
    content: Any,
    status: str = "draft",
    visible_in_workspace: bool = True,
) -> DocumentApproval:
    agent_name = agent_name.upper().strip()
    payload = build_structured_payload(
        title=title,
        content_type=content_type,
        content=content,
        status=status,
        visible_in_workspace=visible_in_workspace,
    )
    doc = DocumentApproval(
        user_id=user_id,
        company_id=company_id,
        agent_name=agent_name,
        document_type=workspace_category,
        document_payload=payload,
        status=status,
        visible_in_workspace=visible_in_workspace,
        audit_log=[
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": "workspace_deliverable_created",
                "agent": agent_name,
                "workspace_category": workspace_category,
            }
        ],
    )
    try:
        db.add(doc)
        db.commit()
        db.refresh(doc)
    except Exception:
        db.rollback()
        raise
    logger.info(
        "Workspace deliverable persisted id=%s user=%s company=%s agent=%s type=%s",
        doc.id,
        user_id,
        company_id,
        agent_name,
        workspace_category,
    )
    return doc


def persist_agent_chat_deliverable(
    db: Session, user: User, agent_name: str, message: str
) -> Optional[DocumentApproval]:
    if not message or not str(message).strip():
        return None
    agent_key = agent_name.upper().strip()
    if agent_key not in AGENT_WORKSPACE_CATEGORY:
        return None
    workspace_cat = AGENT_WORKSPACE_CATEGORY[agent_key]
    ctype = DEFAULT_CONTENT_TYPE[agent_key]
    raw = str(message).strip()
    title = raw.split("\n")[0][:200].strip() or f"Entregable {agent_key}"
    cid = primary_company_id_for_user(db, user)
    return persist_workspace_deliverable(
        db,
        user_id=user.id,
        company_id=cid,
        agent_name=agent_key,
        workspace_category=workspace_cat,
        title=title,
        content_type=ctype,
        content={"body": raw, "format": "markdown_or_plain"},
        status="draft",
        visible_in_workspace=True,
    )
