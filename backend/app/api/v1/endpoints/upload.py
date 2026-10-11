"""
Subida unificada: imagenes, video, PDF.

Fase 2 / Step 1: el binario va a Cloudflare R2 (empresa/{id}/...) y se registra en
`stored_files`. La URL devuelta es estable (/api/v1/files/{id}) y el acceso exige usuario
de la misma empresa; nada se escribe en STATIC_DIR ni se publica por /static.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from services import object_storage
from services.upload_intake import storage_http_error, store_upload

router = APIRouter()

# Categorias antiguas de /static/uploads/<categoria>/ que pueden seguir referenciadas en BD.
_SERVE_UPLOAD_CATEGORIES = frozenset({"images", "videos", "documents", "media"})
_LEGACY_FILENAME = re.compile(r"^[a-zA-Z0-9._-]{1,255}$")

MAX_BYTES = 100 * 1024 * 1024  # 100 MB

ALLOWED_CONTENT_TYPES = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
        "video/mp4",
        "video/webm",
        "video/quicktime",
        "application/pdf",
    }
)


def _category_for(content_type: str) -> str:
    if content_type.startswith("image/"):
        return "images"
    if content_type.startswith("video/"):
        return "videos"
    if content_type == "application/pdf":
        return "documents"
    return "media"


@router.post("")
async def upload_media(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """POST /api/v1/upload — multipart campo ``file``. Guarda en R2 bajo la empresa del usuario."""
    from services.upload_intake import resolve_content_type

    category = _category_for(resolve_content_type(file))
    return await store_upload(
        db,
        current_user,
        file,
        category=category,
        allowed_types=ALLOWED_CONTENT_TYPES,
        max_bytes=MAX_BYTES,
    )


@router.options("/file/{category}/{filename}", include_in_schema=False)
async def upload_file_options(category: str, filename: str) -> Response:
    return Response(status_code=204)


@router.get("/file/{category}/{filename}")
def serve_legacy_upload(
    category: str,
    filename: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Compatibilidad con URLs antiguas /static/uploads/<categoria>/<fichero> guardadas en BD
    (el frontend las reescribe a esta ruta con ?token=). Ya no se lee del disco: se busca el
    fichero migrado a R2 por su ruta antigua, SOLO entre las empresas del usuario, y se
    redirige a una URL firmada corta.
    """
    import services.crm_office_service as crm_svc

    if category not in _SERVE_UPLOAD_CATEGORIES or not _LEGACY_FILENAME.match(filename):
        raise HTTPException(status_code=404, detail="Not Found")
    company_ids = crm_svc.company_ids_for_user(db, current_user)
    row = object_storage.get_legacy_for_companies(
        db, f"uploads/{category}/{filename}", company_ids
    )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Archivo no encontrado. Si se subio antes de la migracion a R2 y no se "
            "migro, hay que volver a subirlo.",
        )
    try:
        url = object_storage.signed_url(row)
    except (object_storage.StorageNotConfigured, object_storage.StorageError) as exc:
        raise storage_http_error(exc) from exc
    return RedirectResponse(url, status_code=302, headers={"Cache-Control": "no-store"})
