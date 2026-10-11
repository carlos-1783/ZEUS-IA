"""Acceso a ficheros guardados en R2 (Fase 2 / Step 1).

- GET  /files/{id}      -> 302 a una URL firmada corta (sirve en <img>/<video> con ?token=).
- GET  /files/{id}/url  -> la URL firmada en JSON (para el frontend con cabecera Authorization).
- DELETE /files/{id}    -> borra el objeto y marca la fila.

Siempre: usuario autenticado y fichero de una de SUS empresas. Un id de otra empresa
responde 404 (no se revela que existe) y queda registrado como evento THALOS.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.stored_file import StoredFile
from app.models.user import User
from services import object_storage
from services.upload_intake import storage_http_error

router = APIRouter()
logger = logging.getLogger(__name__)

_NOT_FOUND = "Fichero no encontrado."


def _resolve_for_user(db: Session, user: User, file_id: str, request: Request) -> StoredFile:
    import services.crm_office_service as crm_svc
    from services.thalos_request_guard_v1 import record_security_event

    company_ids = crm_svc.company_ids_for_user(db, user)
    row = object_storage.get_for_companies(db, file_id, company_ids)
    if row is not None:
        return row
    # Distinguir (solo en el registro, nunca en la respuesta) si el id existe en otra empresa.
    exists_elsewhere = (
        db.query(StoredFile.id).filter(StoredFile.id == file_id).first() is not None
        if isinstance(file_id, str) and len(file_id) == 32
        else False
    )
    record_security_event(
        db,
        event_type="file_access_denied",
        severity="critical" if exists_elsewhere else "warning",
        source="files_api",
        details={
            "file_id": (file_id or "")[:64],
            "reason": "other_company" if exists_elsewhere else "not_found",
            "path": request.url.path,
            "method": request.method,
        },
        user=user,
        company_id=company_ids[0] if company_ids else None,
        ip_address=request.client.host if request.client else None,
        action_taken="deny",
        decision_rule="file_company_scope",
    )
    raise HTTPException(status_code=404, detail=_NOT_FOUND)


@router.get("/{file_id}")
def open_file(
    file_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    row = _resolve_for_user(db, current_user, file_id, request)
    try:
        url = object_storage.signed_url(row)
    except (object_storage.StorageNotConfigured, object_storage.StorageError) as exc:
        raise storage_http_error(exc) from exc
    return RedirectResponse(url, status_code=302, headers={"Cache-Control": "no-store"})


@router.get("/{file_id}/url")
def file_signed_url(
    file_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    row = _resolve_for_user(db, current_user, file_id, request)
    try:
        url = object_storage.signed_url(row)
    except (object_storage.StorageNotConfigured, object_storage.StorageError) as exc:
        raise storage_http_error(exc) from exc
    from app.core.config import settings

    return {
        "file_id": row.id,
        "url": url,
        "expires_in": int(settings.R2_SIGNED_URL_TTL_SEC),
        "content_type": row.content_type,
        "filename": row.original_filename,
        "size_bytes": row.size_bytes,
    }


@router.delete("/{file_id}")
def delete_file(
    file_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    row = _resolve_for_user(db, current_user, file_id, request)
    try:
        object_storage.delete_file(db, row)
    except (object_storage.StorageNotConfigured, object_storage.StorageError) as exc:
        raise storage_http_error(exc) from exc
    logger.info("fichero borrado file_id=%s company_id=%s user_id=%s", row.id, row.company_id, current_user.id)
    return {"success": True, "file_id": row.id}
