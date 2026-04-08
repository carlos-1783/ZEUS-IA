"""
Workspace: crear entregables estructurados persistidos (document_approvals).
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from services.global_company_bootstrap import ensure_user_company_link_for_operations
from services.legal_fiscal_firewall import DocumentStatus
from services.workspace_deliverables import (
    WORKSPACE_DOCUMENT_TYPES,
    persist_workspace_deliverable,
    primary_company_id_for_user,
)

_ALLOWED_WORKSPACE_STATUS = {s.value for s in DocumentStatus}

router = APIRouter()


class WorkspaceCreateBody(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    type: str = Field(
        ...,
        description="Subtipo de contenido (ej. social_media_post)",
        min_length=1,
        max_length=100,
    )
    document_type: str = Field(
        ...,
        description="Categoría workspace (ej. marketing_campaign, fiscal_document)",
        min_length=1,
        max_length=100,
    )
    content: Dict[str, Any] = Field(default_factory=dict)
    agent_name: str = Field(..., min_length=2, max_length=50)
    status: str = Field(default="draft", max_length=50)
    visible_in_workspace: bool = True
    company_id: Optional[int] = None


@router.post("/create")
async def workspace_create(
    body: WorkspaceCreateBody,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Persiste un entregable estructurado vinculado a usuario y empresa (workspace).
    """
    cat = body.document_type.strip().lower()
    if cat not in WORKSPACE_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"document_type debe ser uno de: {WORKSPACE_DOCUMENT_TYPES}",
        )

    st = (body.status or "draft").strip().lower()
    if st not in _ALLOWED_WORKSPACE_STATUS:
        raise HTTPException(
            status_code=400,
            detail=f"status debe ser uno de: {sorted(_ALLOWED_WORKSPACE_STATUS)}",
        )

    ensure_user_company_link_for_operations(db, current_user)
    primary = primary_company_id_for_user(db, current_user)

    from app.models.company import UserCompany

    allowed = {
        r[0]
        for r in db.query(UserCompany.company_id)
        .filter(UserCompany.user_id == current_user.id)
        .all()
    }
    if body.company_id is not None:
        if body.company_id not in allowed:
            raise HTTPException(
                status_code=403,
                detail="company_id no pertenece a las empresas del usuario",
            )
        cid = body.company_id
    else:
        cid = primary

    doc = persist_workspace_deliverable(
        db,
        user_id=current_user.id,
        company_id=cid,
        agent_name=body.agent_name.strip(),
        workspace_category=cat,
        title=body.title.strip(),
        content_type=body.type.strip(),
        content=body.content,
        status=st,
        visible_in_workspace=body.visible_in_workspace,
    )
    d = doc.to_dict()
    return {
        "success": True,
        "workspace_document_id": doc.id,
        "document": d,
    }
