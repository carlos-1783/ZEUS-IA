"""
🖼️ PERSEO Image Upload Endpoint
Permite subir imágenes de referencia locales para las campañas de PERSEO.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.core.auth import get_current_active_user
from app.core.config import settings
from app.models.user import User
from services.perseo_images import save_image

router = APIRouter(prefix="/perseo", tags=["perseo-images"])


@router.post(
    "/upload-image",
    status_code=status.HTTP_201_CREATED,
)
async def upload_perseo_image(
    image: UploadFile = File(...),
    _: User = Depends(get_current_active_user),
):
    """
    Guardar una imagen temporal y devolver una URL pública.
    """
    if not settings.PERSEO_IMAGES_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Las cargas de imágenes están deshabilitadas.",
        )

    try:
        asset = await save_image(image)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo guardar la imagen subida.",
        ) from exc

    return {
        "success": True,
        "url": asset["url"],
        "relative_path": asset["relative_path"],
        "filename": asset["filename"],
        "content_type": asset["content_type"],
        "size_bytes": asset["size_bytes"],
        "storage": asset["storage"],
        "expires_at": asset["expires_at"],
    }

