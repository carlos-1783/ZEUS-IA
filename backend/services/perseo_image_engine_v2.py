"""PERSEO image engine v2 — Replicate or Stability AI (real URLs only)."""

from __future__ import annotations

import logging
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from services.perseo_job_queue_v1 import enqueue_job, get_job, run_job_async, update_job
from services.perseo_storage_v2 import require_cloud_storage, upload_file
from services.zeus_execution_controller_v1 import get_execution_status

logger = logging.getLogger(__name__)


def _provider_configured() -> bool:
    provider = getattr(settings, "PERSEO_IMAGE_PROVIDER", "replicate")
    if provider == "stability":
        return bool(getattr(settings, "STABILITY_API_KEY", ""))
    return bool(getattr(settings, "REPLICATE_API_TOKEN", ""))


def _generate_replicate(prompt: str) -> bytes:
    token = settings.REPLICATE_API_TOKEN
    headers = {"Authorization": f"Token {token}", "Content-Type": "application/json"}
    body = {
        "version": "39ed52f2a78e934b3ba6e2a89f5f1c245ec606edddb6454572f5a0885f138e2",
        "input": {"prompt": prompt, "width": 1024, "height": 1024},
    }
    r = requests.post("https://api.replicate.com/v1/predictions", json=body, headers=headers, timeout=30)
    r.raise_for_status()
    pred = r.json()
    poll_url = pred.get("urls", {}).get("get") or f"https://api.replicate.com/v1/predictions/{pred['id']}"
    for _ in range(60):
        pr = requests.get(poll_url, headers=headers, timeout=30)
        pr.raise_for_status()
        data = pr.json()
        if data.get("status") == "succeeded":
            out = data.get("output")
            img_url = out[0] if isinstance(out, list) else out
            ir = requests.get(img_url, timeout=60)
            ir.raise_for_status()
            return ir.content
        if data.get("status") in ("failed", "canceled"):
            raise RuntimeError(data.get("error") or "replicate failed")
        __import__("time").sleep(2)
    raise RuntimeError("replicate timeout")


def _generate_stability(prompt: str) -> bytes:
    key = settings.STABILITY_API_KEY
    r = requests.post(
        "https://api.stability.ai/v2beta/stable-image/generate/sd3",
        headers={"Authorization": f"Bearer {key}", "Accept": "image/*"},
        files={"none": ""},
        data={"prompt": prompt, "output_format": "png"},
        timeout=120,
    )
    r.raise_for_status()
    return r.content


def _image_job_handler(db: Session, row) -> Dict[str, Any]:
    payload = __import__("json").loads(row.input_json or "{}")
    prompt = payload.get("prompt") or ""
    if not prompt:
        raise RuntimeError("prompt required")
    update_job(db, row.job_id, progress=30)
    provider = getattr(settings, "PERSEO_IMAGE_PROVIDER", "replicate")
    raw = _generate_stability(prompt) if provider == "stability" else _generate_replicate(prompt)
    update_job(db, row.job_id, progress=70)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"img_{uuid.uuid4().hex[:8]}.png"
        path.write_bytes(raw)
        require_cloud_storage()
        stored = upload_file(path, user_id=row.user_id, category="images", content_type="image/png")
    return {"image_url": stored["url"], "storage": stored["storage"], "provider": provider}


def create_image_generation_job(
    db: Session,
    user: User,
    *,
    prompt: str,
    transaction_id: Optional[str] = None,
) -> Dict[str, Any]:
    execution = get_execution_status(db)
    if execution["execution_mode"] == "ERROR":
        raise HTTPException(status_code=503, detail="execution_mode ERROR")
    if not execution["writes_enabled"]:
        raise HTTPException(status_code=403, detail="writes_enabled false")
    if not _provider_configured():
        raise HTTPException(
            status_code=503,
            detail={"error": "image_provider_not_configured", "provider": settings.PERSEO_IMAGE_PROVIDER},
        )
    created = enqueue_job(
        db,
        user_id=user.id,
        job_type="image_generation",
        payload={"prompt": prompt},
        transaction_id=transaction_id,
    )
    run_job_async(created["job_id"], _image_job_handler)
    return {**created, "poll_url": f"/api/v1/perseo/v2/jobs/{created['job_id']}"}


def get_image_job(db: Session, job_id: str, user_id: int) -> Dict[str, Any]:
    return get_job(db, job_id, user_id)
