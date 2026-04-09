"""
Subida unificada: imágenes, vídeo, PDF. Autenticada, tamaño acotado, URL pública bajo /static.
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Set

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse

from app.core.auth import get_current_active_user
from app.core.config import settings
from app.models.user import User

router = APIRouter()

# Debe coincidir con subcarpetas de POST "" (images, videos, documents, media)
_SERVE_UPLOAD_CATEGORIES = frozenset({"images", "videos", "documents", "media"})
_FILENAME_SAFE = re.compile(r"^u\d+_[a-zA-Z0-9._-]+$")

MAX_BYTES = 100 * 1024 * 1024  # 100 MB

ALLOWED_CONTENT_TYPES: Set[str] = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "application/pdf",
}

def _public_origin_for_upload(request: Request) -> Optional[str]:
    """
    Host público visto por el navegador (proxy / Railway). Evita guardar http://127.0.0.1 en la BD.
    """
    explicit = (getattr(settings, "PUBLIC_BASE_URL", None) or "").strip().rstrip("/")
    if explicit:
        return explicit
    rdom = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
    if rdom:
        return f"https://{rdom}".rstrip("/")
    fwd_host = (request.headers.get("x-forwarded-host") or "").split(",")[0].strip()
    if fwd_host:
        proto = (request.headers.get("x-forwarded-proto") or "https").split(",")[0].strip().lower()
        if proto not in ("http", "https"):
            proto = "https"
        return f"{proto}://{fwd_host}".rstrip("/")
    return None


EXT_FALLBACK = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
    ".pdf": "application/pdf",
}


def _safe_filename(name: str) -> str:
    base = Path(name or "upload").name
    base = re.sub(r"[^a-zA-Z0-9._-]", "_", base)[:180]
    return base or "upload.bin"


def _resolve_content_type(upload: UploadFile) -> str:
    ct = (upload.content_type or "").split(";")[0].strip().lower()
    if ct in ALLOWED_CONTENT_TYPES:
        return ct
    ext = Path(upload.filename or "").suffix.lower()
    return EXT_FALLBACK.get(ext, ct or "application/octet-stream")


@router.post("")
async def upload_media(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
):
    """
    POST /api/v1/upload — multipart campo ``file``.
    """
    content_type = _resolve_content_type(file)
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Tipo no permitido: {content_type}. Use imagen, vídeo o PDF.",
        )

    raw = await file.read()
    if len(raw) > MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Archivo demasiado grande (máx. {MAX_BYTES // (1024 * 1024)} MB).",
        )

    subdir = "media"
    if content_type.startswith("image/"):
        subdir = "images"
    elif content_type.startswith("video/"):
        subdir = "videos"
    elif content_type == "application/pdf":
        subdir = "documents"

    upload_root = Path(settings.STATIC_DIR) / "uploads" / subdir
    upload_root.mkdir(parents=True, exist_ok=True)

    safe = _safe_filename(file.filename or "file")
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    filename = f"u{current_user.id}_{stamp}_{safe}"
    destination = upload_root / filename
    destination.write_bytes(raw)

    path_url = f"{settings.STATIC_URL.rstrip('/')}/uploads/{subdir}/{filename}"
    if not path_url.startswith("/"):
        path_url = "/" + path_url.lstrip("/")

    public_origin = _public_origin_for_upload(request)
    if public_origin:
        absolute_url = f"{public_origin}{path_url}"
    else:
        host = request.url.hostname or "127.0.0.1"
        port = request.url.port
        scheme = request.url.scheme or "http"
        netloc = host
        if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
            netloc = f"{host}:{port}"
        absolute_url = f"{scheme}://{netloc}{path_url}"

    return {
        "success": True,
        "filename": filename,
        "content_type": content_type,
        "size_bytes": len(raw),
        "url": absolute_url,
        "path_url": path_url,
        "path": f"uploads/{subdir}/{filename}",
    }


def _media_type_upload(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return EXT_FALLBACK.get(ext, "application/octet-stream")


@router.options("/file/{category}/{filename}", include_in_schema=False)
async def upload_file_options(category: str, filename: str) -> Response:
    return Response(status_code=204)


@router.get("/file/{category}/{filename}")
async def serve_user_upload(
    category: str,
    filename: str,
    current_user: User = Depends(get_current_active_user),
):
    """
    Sirve un fichero subido vía POST /upload (mismo disco que STATIC_DIR).
    Autenticado; solo el propietario (prefijo u{user_id}_). Útil cuando /static da 404
    (disco efímero, otro réplica, etc.): el cliente usa ?token= en <video src>.
    """
    if category not in _SERVE_UPLOAD_CATEGORIES:
        raise HTTPException(status_code=404, detail="Not Found")
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=404, detail="Not Found")
    if not _FILENAME_SAFE.match(filename):
        raise HTTPException(status_code=404, detail="Not Found")
    prefix = f"u{current_user.id}_"
    if not filename.startswith(prefix):
        raise HTTPException(status_code=403, detail="No autorizado")

    base_dir = (Path(settings.STATIC_DIR) / "uploads" / category).resolve()
    file_path = (base_dir / filename).resolve()
    try:
        file_path.relative_to(base_dir)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not Found")
    if not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=(
                "Archivo no encontrado. En Railway sin volumen persistente las subidas "
                "se pierden al redeploy; vuelve a subir el vídeo o configura STATIC_DIR en un volumen."
            ),
        )

    media = _media_type_upload(filename)
    return FileResponse(
        file_path,
        media_type=media,
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Accept-Ranges": "bytes",
        },
    )
