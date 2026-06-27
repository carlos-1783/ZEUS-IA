"""PERSEO video generation v2 — Replicate zeroscope-v2-xl → S3."""

from __future__ import annotations

import logging
import tempfile
import time
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

# Replicate zeroscope-v2-xl
ZEROscope_VERSION = "9f747673945c62854b24ada4488997143068011a9bb9446db6eae2611fb0318"
MAX_DURATION_SEC = int(getattr(settings, "PERSEO_VIDEO_GEN_MAX_SEC", 10) or 10)
DEFAULT_FPS = 8


def video_gen_configured() -> bool:
    return bool(getattr(settings, "REPLICATE_API_TOKEN", ""))


def _generate_zeroscope(prompt: str, duration_sec: float = 5.0) -> bytes:
    token = settings.REPLICATE_API_TOKEN
    if not token:
        raise RuntimeError("REPLICATE_API_TOKEN not configured")
    duration_sec = min(float(duration_sec), MAX_DURATION_SEC)
    num_frames = max(24, min(int(duration_sec * DEFAULT_FPS), 80))
    headers = {"Authorization": f"Token {token}", "Content-Type": "application/json"}
    body = {
        "version": ZEROscope_VERSION,
        "input": {"prompt": prompt, "num_frames": num_frames, "fps": DEFAULT_FPS},
    }
    r = requests.post("https://api.replicate.com/v1/predictions", json=body, headers=headers, timeout=30)
    r.raise_for_status()
    pred = r.json()
    poll_url = pred.get("urls", {}).get("get") or f"https://api.replicate.com/v1/predictions/{pred['id']}"
    for _ in range(90):
        pr = requests.get(poll_url, headers=headers, timeout=30)
        pr.raise_for_status()
        data = pr.json()
        status = data.get("status")
        if status == "succeeded":
            out = data.get("output")
            video_url = out if isinstance(out, str) else (out[0] if isinstance(out, list) and out else None)
            if not video_url:
                raise RuntimeError("replicate returned no video url")
            vr = requests.get(video_url, timeout=120)
            vr.raise_for_status()
            return vr.content
        if status in ("failed", "canceled"):
            raise RuntimeError(data.get("error") or "video generation failed")
        time.sleep(3)
    raise RuntimeError("replicate video timeout")


def _video_gen_handler(db: Session, row) -> Dict[str, Any]:
    payload = __import__("json").loads(row.input_json or "{}")
    prompt = (payload.get("prompt") or "").strip()
    if not prompt:
        raise RuntimeError("prompt required")
    duration = float(payload.get("duration_sec") or 5)
    update_job(db, row.job_id, progress=20)
    raw = _generate_zeroscope(prompt, duration_sec=duration)
    update_job(db, row.job_id, progress=75)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"gen_{uuid.uuid4().hex[:8]}.mp4"
        path.write_bytes(raw)
        require_cloud_storage()
        stored = upload_file(path, user_id=row.user_id, category="videos", content_type="video/mp4")
    return {
        "video_url": stored["url"],
        "storage": stored["storage"],
        "provider": "replicate/zeroscope-v2-xl",
        "duration_sec": duration,
    }


def create_video_generation_job(
    db: Session,
    user: User,
    *,
    prompt: str,
    duration_sec: float = 5.0,
    transaction_id: Optional[str] = None,
) -> Dict[str, Any]:
    execution = get_execution_status(db)
    if execution["execution_mode"] == "ERROR":
        raise HTTPException(status_code=503, detail="execution_mode ERROR")
    if not execution["writes_enabled"]:
        raise HTTPException(status_code=403, detail="writes_enabled false")
    if not video_gen_configured():
        raise HTTPException(
            status_code=503,
            detail={"error": "video_gen_not_configured", "required": ["REPLICATE_API_TOKEN"]},
        )
    created = enqueue_job(
        db,
        user_id=user.id,
        job_type="video_generation",
        payload={"prompt": prompt, "duration_sec": min(duration_sec, MAX_DURATION_SEC)},
        transaction_id=transaction_id,
    )
    run_job_async(created["job_id"], _video_gen_handler)
    return {**created, "poll_url": f"/api/v1/perseo/v2/jobs/{created['job_id']}"}


def get_video_gen_job(db: Session, job_id: str, user_id: int) -> Dict[str, Any]:
    return get_job(db, job_id, user_id)
