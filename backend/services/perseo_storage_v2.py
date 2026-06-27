"""
PERSEO storage v2 — S3/cloud object storage with signed URLs (no local-only in V2 mode).
"""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)


class PerseoStorageError(RuntimeError):
    pass


def storage_backend() -> str:
    return (getattr(settings, "PERSEO_STORAGE_BACKEND", "local") or "local").lower()


def s3_configured() -> bool:
    return bool(
        getattr(settings, "AWS_S3_BUCKET", "")
        and getattr(settings, "AWS_ACCESS_KEY_ID", "")
        and getattr(settings, "AWS_SECRET_ACCESS_KEY", "")
    )


def require_cloud_storage() -> None:
    """V2 mode rejects local-only persistence for outputs."""
    if not getattr(settings, "PERSEO_V2_ENABLED", False):
        return
    if storage_backend() != "s3" or not s3_configured():
        raise HTTPException(
            status_code=503,
            detail={
                "error": "cloud_storage_required",
                "message": (
                    "PERSEO_V2 requires PERSEO_STORAGE_BACKEND=s3 and AWS_S3_BUCKET + credentials"
                ),
            },
        )


def _s3_client():
    try:
        import boto3  # type: ignore
    except ImportError as exc:
        raise PerseoStorageError("boto3 not installed — pip install boto3 for S3 storage") from exc
    return boto3.client(
        "s3",
        region_name=getattr(settings, "AWS_S3_REGION", "eu-west-1"),
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


def build_object_key(*, user_id: int, category: str, filename: str) -> str:
    safe = filename.replace("..", "").lstrip("/")
    return f"perseo/u{user_id}/{category}/{safe}"


def upload_file(
    local_path: Path,
    *,
    user_id: int,
    category: str,
    filename: Optional[str] = None,
    content_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Upload to S3 when configured; otherwise local /static (v1 compat only)."""
    require_cloud_storage()
    fname = filename or local_path.name
    key = build_object_key(user_id=user_id, category=category, filename=fname)
    ct = content_type or mimetypes.guess_type(fname)[0] or "application/octet-stream"

    if storage_backend() == "s3" and s3_configured():
        client = _s3_client()
        bucket = settings.AWS_S3_BUCKET
        with open(local_path, "rb") as fh:
            client.upload_fileobj(fh, bucket, key, ExtraArgs={"ContentType": ct})
        prefix = getattr(settings, "AWS_S3_PUBLIC_URL_PREFIX", "") or ""
        if prefix:
            url = f"{prefix}/{key}"
            signed = False
        else:
            url = client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=int(getattr(settings, "AWS_S3_SIGNED_URL_TTL_SEC", 3600)),
            )
            signed = True
        logger.info("[PERSEO_STORAGE] s3 upload key=%s user=%s", key, user_id)
        return {
            "storage": "s3",
            "bucket": bucket,
            "key": key,
            "url": url,
            "signed_url": signed,
            "content_type": ct,
            "size_bytes": local_path.stat().st_size,
        }

    raise HTTPException(
        status_code=503,
        detail={"error": "storage_not_configured", "backend": storage_backend()},
    )


def store_local_fallback(local_path: Path, *, user_id: int, category: str) -> Dict[str, Any]:
    """Legacy local path — blocked when PERSEO_V2_ENABLED."""
    if getattr(settings, "PERSEO_V2_ENABLED", False):
        require_cloud_storage()
    rel = local_path.relative_to(Path(settings.STATIC_DIR)) if str(local_path).startswith(str(settings.STATIC_DIR)) else local_path.name
    url = f"/static/{rel}".replace("\\", "/")
    return {"storage": "local", "url": url, "path": str(local_path)}
