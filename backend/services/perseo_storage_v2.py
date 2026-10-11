"""
PERSEO storage — salidas de los motores (imagenes, videos, GIF) en Cloudflare R2.

Fase 2 / Step 1: este modulo es ahora un adaptador fino sobre `services.object_storage`
(el almacenamiento comun del nucleo). Se conservan los nombres publicos para que los
motores PERSEO no cambien de contrato, pero:
- ya no hay respaldo en disco local ni URLs /static (se perdian en cada deploy y se
  servian sin autenticacion);
- todo objeto queda bajo `empresa/{company_id}/...` y registrado en `stored_files`;
- la URL devuelta es la estable `/api/v1/files/{id}` (acceso con filtro de empresa).
"""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import HTTPException

from services import object_storage

logger = logging.getLogger(__name__)

# Categorias de PERSEO -> categorias del almacenamiento comun.
_CATEGORY_MAP = {"images": "images", "videos": "videos", "thumbnails": "images", "gifs": "images"}


class PerseoStorageError(RuntimeError):
    pass


def storage_backend() -> str:
    return "r2" if object_storage.is_configured() else "none"


def s3_configured() -> bool:
    """Compatibilidad de nombre: True si el almacenamiento externo (R2) esta configurado."""
    return object_storage.is_configured()


def require_cloud_storage() -> None:
    """Sin almacenamiento externo no hay donde guardar salidas: 503 explicito."""
    missing = object_storage.missing_config()
    if missing:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "cloud_storage_required",
                "message": "PERSEO necesita almacenamiento externo (Cloudflare R2) configurado.",
                "missing": missing,
            },
        )


def _company_for_user(db, user_id: int) -> int:
    import services.crm_office_service as crm_svc
    from app.models.user import User

    user = db.get(User, int(user_id)) if user_id else None
    cid = crm_svc.primary_company_id(db, user) if user is not None else None
    if not isinstance(cid, int):
        raise PerseoStorageError(f"El usuario {user_id} no tiene empresa: no se puede guardar el fichero.")
    return cid


def _store(
    local_path: Path,
    *,
    company_id: Optional[int],
    user_id: Optional[int],
    category: str,
    filename: Optional[str],
    content_type: Optional[str],
) -> Dict[str, Any]:
    from app.db.base import SessionLocal

    require_cloud_storage()
    fname = filename or local_path.name
    ct = content_type or mimetypes.guess_type(fname)[0] or "application/octet-stream"
    data = Path(local_path).read_bytes()
    db = SessionLocal()
    try:
        cid = company_id if isinstance(company_id, int) else _company_for_user(db, user_id)
        try:
            row = object_storage.store_file(
                db,
                company_id=cid,
                user_id=user_id or None,
                category=_CATEGORY_MAP.get(category, "media"),
                filename=fname,
                content_type=ct,
                data=data,
            )
        except object_storage.StorageNotConfigured:
            require_cloud_storage()
            raise
        except object_storage.StorageError as exc:
            raise HTTPException(
                status_code=502, detail={"error": "storage_upload_failed", "message": str(exc)}
            ) from exc
        logger.info("[PERSEO_STORAGE] r2 file_id=%s company_id=%s category=%s", row.id, cid, row.category)
        return {
            "storage": "r2",
            "file_id": row.id,
            "key": row.object_key,
            "url": object_storage.file_url(row),
            "signed_url": False,
            "content_type": row.content_type,
            "size_bytes": row.size_bytes,
            "company_id": cid,
        }
    finally:
        db.close()


def upload_file(
    local_path: Path,
    *,
    user_id: int,
    category: str,
    filename: Optional[str] = None,
    content_type: Optional[str] = None,
    company_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Sube una salida de PERSEO a R2 bajo la empresa del usuario."""
    return _store(
        local_path,
        company_id=company_id,
        user_id=user_id,
        category=category,
        filename=filename,
        content_type=content_type,
    )


def upload_tenant_video(
    local_path: Path,
    *,
    tenant_id: int,
    user_id: int,
    filename: Optional[str] = None,
) -> Dict[str, Any]:
    """Video (o GIF de vista previa) de produccion PERSEO bajo la empresa `tenant_id`."""
    from datetime import datetime, timezone

    fname = filename or f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.mp4"
    category = "gifs" if fname.lower().endswith(".gif") else "videos"
    return _store(
        local_path,
        company_id=int(tenant_id),
        user_id=user_id or None,
        category=category,
        filename=fname,
        content_type=None,
    )
