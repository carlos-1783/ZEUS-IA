"""RAFAEL fiscal engine v2 — PDF facturas y Excel modelo 303."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.document_approval import DocumentApproval
from app.models.user import User
from services.rafael_fiscal_engine_v2 import (
    assert_user_company_access,
    generate_invoice_pdf_flow,
    generate_model_303_flow,
)
import services.crm_office_service as crm_svc

router = APIRouter()


class Model303GenerateBody(BaseModel):
    company_id: Optional[int] = None
    year: int = Field(..., ge=2000, le=2100)
    quarter: int = Field(..., ge=1, le=4)


class InvoicePdfBody(BaseModel):
    company_id: Optional[int] = None


@router.post("/invoices/{invoice_id}/generate-pdf")
def rafael_generate_invoice_pdf(
    invoice_id: int,
    body: InvoicePdfBody = InvoicePdfBody(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    company_id = body.company_id or crm_svc.primary_company_id(db, current_user)
    return generate_invoice_pdf_flow(
        db,
        user=current_user,
        invoice_id=invoice_id,
        company_id=company_id,
    )


@router.post("/model-303/generate")
def rafael_generate_model_303(
    body: Model303GenerateBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    company_id = body.company_id or crm_svc.primary_company_id(db, current_user)
    return generate_model_303_flow(
        db,
        user=current_user,
        company_id=int(company_id),
        year=body.year,
        quarter=body.quarter,
    )


@router.get("/documents/{document_id}/download")
def rafael_download_fiscal_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    doc = (
        db.query(DocumentApproval)
        .filter(
            DocumentApproval.id == document_id,
            DocumentApproval.user_id == current_user.id,
            DocumentApproval.agent_name == "RAFAEL",
        )
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")

    file_path = getattr(doc, "file_path", None)
    if not file_path:
        payload = doc.document_payload or {}
        content = payload.get("content") if isinstance(payload.get("content"), dict) else payload
        file_path = (content or {}).get("file_path")

    if not file_path or not Path(file_path).is_file():
        raise HTTPException(status_code=404, detail="Archivo fiscal no disponible.")

    size = Path(file_path).stat().st_size
    if size <= 0:
        raise HTTPException(status_code=422, detail="Archivo fiscal vacío.")

    if doc.company_id:
        assert_user_company_access(db, current_user, doc.company_id)

    media = getattr(doc, "mime_type", None) or "application/octet-stream"
    filename = Path(file_path).name
    return FileResponse(file_path, media_type=media, filename=filename)
