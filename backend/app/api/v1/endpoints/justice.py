"""JUSTICIA real API — audit, documents, sign, GDPR from database."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.core.config import settings
from app.db.session import get_db
from app.models.compliance_event import ComplianceEvent
from app.models.user import User
from services.gdpr_engine import run_gdpr_check
from services.contract_generator import generate_contract
from services.justice_audit_service import audit_status, get_document, list_documents, run_real_audit
from services.justicia_control_layer_v1 import wrap_response
from services.signature_service import apply_signature

router = APIRouter(prefix="/justice", tags=["justice"])


class SignBody(BaseModel):
    document_id: Optional[str] = None
    document_name: str = ""
    file_hash: str = ""
    signer: str = "JUSTICIA"


class ContractBody(BaseModel):
    parties: List[str] = Field(default_factory=list)
    scope: str = "servicios"
    media_buying: bool = False


class GdprBody(BaseModel):
    systems: List[str] = Field(default_factory=list)


@router.get("/status")
def justice_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    body = audit_status(db, current_user)
    body["justice_enabled"] = bool(getattr(settings, "JUSTICE_ENABLED", True))
    return wrap_response(body, "status", data_origin="backend", real_execution=True, ui_badge="REAL")


@router.get("/audit")
def justice_audit(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    result = run_real_audit(db, current_user)
    if not result.get("real_execution"):
        raise HTTPException(status_code=503, detail=result.get("error", "audit disabled"))
    db.commit()
    return wrap_response(result, "system_audit", data_origin="backend", real_execution=True, ui_badge="REAL")


@router.get("/documents")
def justice_documents(
    status: Optional[str] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    docs = list_documents(db, current_user, status=status, limit=limit)
    return wrap_response(
        {"documents": docs, "count": len(docs), "data_origin": "database"},
        "workspace",
        data_origin="backend",
        real_execution=True,
        ui_badge="REAL",
    )


@router.get("/documents/{document_id}")
def justice_document_detail(
    document_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    body = get_document(db, current_user, document_id)
    if not body:
        raise HTTPException(status_code=404, detail="document_not_found")
    return wrap_response(
        body,
        "workspace",
        data_origin="database",
        real_execution=True,
        ui_badge="REAL",
    )


@router.post("/sign")
def justice_sign(
    body: SignBody,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    result = apply_signature(
        db,
        current_user,
        document_id=body.document_id,
        document_name=body.document_name,
        file_hash=body.file_hash,
        signer_label=body.signer,
    )
    db.commit()
    return wrap_response(result, "pdf_signer", data_origin="backend", real_execution=True, ui_badge="REAL")


@router.post("/contracts/generate")
def justice_generate_contract(
    body: ContractBody,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    result = generate_contract(
        db,
        current_user,
        parties=body.parties,
        scope=body.scope,
        media_buying=body.media_buying,
    )
    db.commit()
    return wrap_response(result, "contract_generator", data_origin="backend", real_execution=True, ui_badge="REAL")


@router.post("/gdpr")
def justice_gdpr(
    body: GdprBody,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    result = run_gdpr_check(db, current_user, systems=body.systems)
    db.commit()
    return wrap_response(result, "gdpr_audit", data_origin="backend", real_execution=True, ui_badge="REAL")


@router.get("/compliance-events")
def justice_compliance_events(
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ = current_user
    rows = db.query(ComplianceEvent).order_by(ComplianceEvent.id.desc()).limit(min(limit, 200)).all()
    events = [
        {
            "id": r.public_id,
            "event_type": r.event_type,
            "severity": r.severity,
            "source": r.source,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return wrap_response({"events": events, "count": len(events)}, "gdpr_audit", data_origin="backend", real_execution=True)
