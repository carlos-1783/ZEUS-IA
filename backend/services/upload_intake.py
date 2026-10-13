"""Entrada comun de ficheros subidos por la API (Fase 2 / Step 1).

Todos los endpoints de subida usan `store_upload`: limite de tamano leido en streaming,
lista blanca de tipos, verificacion del contenido real (no solo la extension), empresa
resuelta en servidor y guardado en R2 via `services.object_storage`. Ningun endpoint
vuelve a escribir en STATIC_DIR.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any, Dict, Mapping, Optional

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.models.user import User
from services import object_storage

_CHUNK = 1024 * 1024

EXT_TO_TYPE: Mapping[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def resolve_content_type(upload: UploadFile) -> str:
    """Tipo declarado por el cliente; si es generico, por extension."""
    ct = (upload.content_type or "").split(";")[0].strip().lower()
    if ct and ct not in ("application/octet-stream", "binary/octet-stream"):
        return ct
    ext = PurePosixPath((upload.filename or "").replace("\\", "/")).suffix.lower()
    return EXT_TO_TYPE.get(ext, ct or "application/octet-stream")


async def read_limited(upload: UploadFile, max_bytes: int) -> bytes:
    """Lee como mucho `max_bytes`; si el fichero es mayor, 413 sin cargarlo entero."""
    buf = bytearray()
    while True:
        chunk = await upload.read(_CHUNK)
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Archivo demasiado grande (max. {max_bytes // (1024 * 1024)} MB).",
            )
    if not buf:
        raise HTTPException(status_code=400, detail="El archivo esta vacio.")
    return bytes(buf)


def resolve_company_for_upload(db: Session, user: User) -> int:
    import services.crm_office_service as crm_svc

    cid = crm_svc.primary_company_id(db, user)
    if not isinstance(cid, int):
        raise HTTPException(
            status_code=403, detail="Se requiere una empresa asociada para subir ficheros."
        )
    return cid


def storage_http_error(exc: Exception) -> HTTPException:
    """Traduce errores del almacenamiento a HTTP sin filtrar detalles internos."""
    if isinstance(exc, object_storage.StorageNotConfigured):
        return HTTPException(
            status_code=503,
            detail="El almacenamiento de ficheros no está configurado todavía. "
            "No se ha guardado nada; contacta con el administrador.",
        )
    if isinstance(exc, object_storage.ContentMismatch):
        return HTTPException(status_code=415, detail=str(exc))
    return HTTPException(
        status_code=502,
        detail="No se pudo acceder al almacenamiento de ficheros. Reintenta en unos minutos.",
    )


async def store_upload(
    db: Session,
    user: User,
    upload: UploadFile,
    *,
    category: str,
    allowed_types: frozenset,
    max_bytes: int,
    company_id: Optional[int] = None,
) -> Dict[str, Any]:
    content_type = resolve_content_type(upload)
    if content_type not in allowed_types:
        raise HTTPException(status_code=415, detail=f"Tipo de archivo no permitido: {content_type}.")
    data = await read_limited(upload, max_bytes)
    cid = company_id if isinstance(company_id, int) else resolve_company_for_upload(db, user)
    try:
        object_storage.verify_content(data, content_type)
        row = object_storage.store_file(
            db,
            company_id=cid,
            user_id=user.id,
            category=category,
            filename=upload.filename or "fichero",
            content_type=content_type,
            data=data,
        )
    except (
        object_storage.StorageNotConfigured,
        object_storage.StorageError,
        object_storage.ContentMismatch,
    ) as exc:
        raise storage_http_error(exc) from exc
    url = object_storage.file_url(row)
    return {
        "success": True,
        "file_id": row.id,
        "filename": row.original_filename,
        "content_type": row.content_type,
        "size_bytes": row.size_bytes,
        "url": url,
        "path_url": url,
        "company_id": row.company_id,
        "category": row.category,
    }
