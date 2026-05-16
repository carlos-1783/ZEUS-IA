"""Importación masiva de clientes CRM (CSV / XLSX)."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.crm_import import CrmImportColumnMapping, CrmImportPreviewOut, CrmImportResultOut
import services.crm_import_service as import_svc

router = APIRouter()


def _read_upload(file: UploadFile) -> tuple[bytes, str]:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nombre de archivo requerido.")
    content = file.file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo está vacío.")
    return content, file.filename


@router.post("/preview", response_model=CrmImportPreviewOut)
async def crm_import_preview(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
):
    """Parsea el archivo y devuelve columnas, mapeo sugerido y vista previa."""
    del current_user
    content, filename = _read_upload(file)
    columns, suggested, preview, total = import_svc.build_preview(content, filename)
    preview_clean = [{k: v for k, v in row.items() if k != "_raw"} for row in preview]
    return CrmImportPreviewOut(
        columns=columns,
        suggested_mapping=suggested,
        preview_rows=preview_clean,
        total_rows=total,
        filename=filename,
    )


@router.post("/clients", response_model=CrmImportResultOut)
async def crm_import_clients(
    file: UploadFile = File(...),
    mapping: str = Form(..., description="JSON con mapeo de columnas"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Importa clientes según el mapeo confirmado (sin sobrescribir existentes)."""
    content, filename = _read_upload(file)
    try:
        mapping_data = json.loads(mapping)
        column_mapping = CrmImportColumnMapping.model_validate(mapping_data)
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mapeo de columnas inválido.",
        ) from exc

    result = import_svc.import_customers(
        db,
        current_user,
        content=content,
        filename=filename,
        mapping=column_mapping,
    )
    return CrmImportResultOut(**result)
