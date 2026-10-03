"""RAFAEL fiscal engine v2 — PDF facturas y Excel modelo 303."""

from __future__ import annotations

import logging
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
    FISCAL_FILENAME_RE,
    FISCAL_KINDS,
    assert_user_company_access,
    generate_invoice_pdf_flow,
    generate_model_303_flow,
    fiscal_private_root,
)
import services.crm_office_service as crm_svc

logger = logging.getLogger(__name__)

router = APIRouter()

_FISCAL_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


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


@router.get("/fiscal-files/{company_id}/{kind}/{filename}")
def rafael_download_fiscal_file(
    company_id: int,
    kind: str,
    filename: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Descarga autenticada de ficheros fiscales (facturas PDF / modelo 303 XLSX).

    Solo usuarios vinculados a la empresa del path (o superusuarios). Los ficheros viven
    fuera de STATIC_DIR (PRIVATE_FILES_DIR) y nunca se sirven por /static.
    """
    # 1) Control de acceso a la empresa ANTES de tocar el disco (no revela si el fichero existe).
    assert_user_company_access(db, current_user, company_id)

    # 2) Validación estricta de kind / filename.
    if kind not in FISCAL_KINDS:
        raise HTTPException(status_code=404, detail="Archivo fiscal no disponible.")
    if not FISCAL_FILENAME_RE.fullmatch(filename):
        raise HTTPException(status_code=404, detail="Archivo fiscal no disponible.")

    # 3) Anti path traversal: la ruta resuelta (siguiendo symlinks) debe quedar dentro del dir de la empresa.
    company_dir = (fiscal_private_root() / str(company_id)).resolve()
    target = (company_dir / kind / filename).resolve()
    if not target.is_relative_to(company_dir):
        logger.warning(
            "fiscal-files: intento de path traversal user=%s company=%s kind=%s",
            current_user.id, company_id, kind,
        )
        raise HTTPException(status_code=404, detail="Archivo fiscal no disponible.")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Archivo fiscal no disponible.")
    if target.stat().st_size <= 0:
        raise HTTPException(status_code=422, detail="Archivo fiscal vacío.")

    logger.info(
        "fiscal-files: descarga user=%s company=%s kind=%s file=%s",
        current_user.id, company_id, kind, target.name,
    )
    media = _FISCAL_MEDIA_TYPES.get(target.suffix.lower(), "application/octet-stream")
    return FileResponse(
        str(target),
        media_type=media,
        filename=target.name,
        headers={"Cache-Control": "private, no-store"},
    )
