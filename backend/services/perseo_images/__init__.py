"""
📁 PERSEO Image Utilities
Servicio minimalista para almacenar imágenes de referencia de campañas.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

from fastapi import UploadFile

from app.core.config import settings

ALLOWED_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

UPLOAD_ROOT = Path(settings.PERSEO_IMAGE_UPLOAD_DIR).resolve()
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

MAX_BYTES = settings.PERSEO_IMAGE_MAX_BYTES


def _build_relative_path(filename: str) -> str:
    relative = Path("uploads") / "perseo" / filename
    return relative.as_posix()


def _build_public_url(relative_path: str) -> str:
    base = settings.STATIC_URL.rstrip("/") or "/static"
    return f"{base}/{relative_path.lstrip('/')}"


async def save_image(upload_file: UploadFile) -> Dict[str, Any]:
    """
    Guardar imagen subida por el usuario y devolver metadatos.
    """
    if upload_file.content_type not in ALLOWED_TYPES:
        raise ValueError(
            "Formato no soportado. Usa JPEG, PNG o WEBP."
        )

    extension = ALLOWED_TYPES[upload_file.content_type]
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    token = secrets.token_urlsafe(6)
    filename = f"perseo_{timestamp}_{token}{extension}"
    destination = UPLOAD_ROOT / filename

    size = 0
    try:
        with destination.open("wb") as buffer:
            while True:
                chunk = await upload_file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ValueError(
                        f"La imagen supera el límite de {MAX_BYTES // (1024 * 1024)}MB."
                    )
                buffer.write(chunk)
    except Exception:
        if destination.exists():
            destination.unlink(missing_ok=True)
        raise
    finally:
        await upload_file.close()

    relative_path = _build_relative_path(filename)
    public_url = _build_public_url(relative_path)

    return {
        "filename": filename,
        "path": str(destination),
        "relative_path": relative_path,
        "url": public_url,
        "size_bytes": size,
        "content_type": upload_file.content_type,
        "storage": settings.IMAGE_STORAGE,
        "expires_at": (datetime.utcnow() + timedelta(days=30)).isoformat(),
    }

