"""Importación masiva de clientes CRM (preview + confirm, archivos temporales)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.crm_import import (
    CrmImportConfirmIn,
    CrmImportPreviewOut,
    CrmImportResultOut,
)
import services.crm_import_service as import_svc

router = APIRouter()


def _read_upload(file: UploadFile) -> tuple[bytes, str]:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nombre de archivo requerido.")
    content = file.file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo está vacío.")
    return content, file.filename


@router.post("/clients/preview", response_model=CrmImportPreviewOut)
async def crm_import_clients_preview(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
):
    """Sube archivo, lo guarda en tmp_uploads/ y devuelve file_id, columnas y vista previa."""
    content, filename = _read_upload(file)
    file_id = import_svc.store_preview_from_upload(content, filename, current_user)
    fid, columns, suggested, preview, total, name = import_svc.build_preview(file_id, current_user.id)
    return CrmImportPreviewOut(
        file_id=fid,
        columns=columns,
        suggested_mapping=suggested,
        preview_rows=preview,
        total_rows=total,
        filename=name,
    )


@router.post("/clients/confirm", response_model=CrmImportResultOut)
async def crm_import_clients_confirm(
    body: CrmImportConfirmIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Confirma importación con file_id y mapeo (sin re-subir archivo)."""
    result = import_svc.confirm_import(
        db,
        current_user,
        file_id=body.file_id,
        mapping=body.mapping,
        source="admin_clients_import",
    )
    return CrmImportResultOut(**result)
