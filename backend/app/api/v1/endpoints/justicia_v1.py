"""JUSTICIA v1 API — auditoría de sistema y control layer."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from services.justice_system_audit_v1 import run_system_audit
from services.justice_audit_service import run_real_audit, list_documents, list_pending_documents_grouped
from services.justicia_control_layer_v1 import global_status_payload, wrap_response

router = APIRouter(prefix="/justicia/v1", tags=["justicia-v1"])


@router.get("/status")
def justicia_v1_status(
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    return global_status_payload()


@router.get("/system-audit")
def justicia_system_audit(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    body = run_real_audit(db, current_user)
    db.commit()
    return wrap_response(
        body,
        "system_audit",
        data_origin="backend",
        real_execution=bool(body.get("real_execution")),
        ui_badge="REAL" if body.get("real_execution") else "SIMULADO",
        audit_trace=body.get("audit_trace"),
    )


@router.get("/documents")
def justicia_documents(
    status: str | None = None,
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    docs = list_documents(db, current_user, status=status, limit=limit)
    pending = list_pending_documents_grouped(db, current_user)
    return wrap_response(
        {"documents": docs, "pending": pending, "count": len(docs)},
        "workspace",
        data_origin="backend",
        real_execution=True,
        ui_badge="REAL",
    )
