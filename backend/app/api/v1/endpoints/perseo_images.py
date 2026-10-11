"""
🖼️ PERSEO Image Upload Endpoint
Permite subir imágenes de referencia locales para las campañas de PERSEO.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from services.perseo_images import save_image

router = APIRouter(prefix="/perseo", tags=["perseo-images"])


@router.post(
    "/upload-image",
    status_code=status.HTTP_201_CREATED,
)
async def upload_perseo_image(
    image: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Guardar la imagen de referencia en R2 (empresa del usuario) y devolver su URL de acceso.
    """
    if not settings.PERSEO_IMAGES_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Las cargas de imágenes están deshabilitadas.",
        )

    asset = await save_image(db, current_user, image)  # 4xx/503 explicitos desde upload_intake
    return {"success": True, **asset}

