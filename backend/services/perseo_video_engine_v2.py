"""
PERSEO video engine v2 — FFmpeg async jobs, cloud storage, extended operations.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.perseo_job import PerseoJob
from app.models.user import User
from services.perseo_job_queue_v1 import enqueue_job, get_job, run_job_async, update_job
from services.perseo_storage_v2 import require_cloud_storage, storage_backend, upload_file
from services.perseo_video_engine_v1 import (
    _build_ffmpeg_filter,
    _ffmpeg_exe,
    _resolve_input_path,
    _video_duration,
)
from services.zeus_execution_controller_v1 import get_execution_status

logger = logging.getLogger(__name__)

MIN_OUTPUT_BYTES = 2048


def _validate_output(path: Path, duration: float) -> None:
    if not path.exists() or path.stat().st_size < MIN_OUTPUT_BYTES:
        raise RuntimeError("output file missing or below minimum threshold")
    if duration <= 0:
        raise RuntimeError("output duration must be > 0")


def _run_ffmpeg_v2(input_path: Path, output_path: Path, thumb_path: Path, operations: List[Dict[str, Any]]) -> float:
    ffmpeg = _ffmpeg_exe()
    vf_parts, trim_start, trim_end = _build_ffmpeg_filter(operations)
    text_overlay = next((o for o in operations if (o.get("type") or "").lower() == "text_overlay"), None)
    audio_path = next((o.get("audio_url") for o in operations if (o.get("type") or "").lower() == "audio_overlay"), None)

    cmd: List[str] = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
    if trim_start is not None and trim_start > 0:
        cmd.extend(["-ss", str(trim_start)])
    cmd.extend(["-i", str(input_path)])

    if text_overlay and text_overlay.get("text"):
        txt = str(text_overlay["text"]).replace(":", "\\:").replace("'", "\\'")
        vf_parts.append(f"drawtext=text='{txt}':fontsize=24:fontcolor=white:x=40:y=40")

    if audio_path:
        ap = _resolve_input_path(str(audio_path), 0)
        cmd.extend(["-i", str(ap), "-shortest", "-map", "0:v:0", "-map", "1:a:0"])

    if trim_end is not None and trim_start is not None:
        cmd.extend(["-t", str(max(0.1, trim_end - trim_start))])
    elif trim_end is not None:
        cmd.extend(["-t", str(trim_end)])

    if vf_parts:
        cmd.extend(["-vf", ",".join(vf_parts)])

    preset = str(getattr(settings, "PERSEO_FFMPEG_PRESET", "veryfast"))
    cmd.extend(
        [
            "-c:v",
            "libx264",
            "-preset",
            preset,
            "-crf",
            str(getattr(settings, "PERSEO_VIDEO_CRF", 23)),
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or "ffmpeg failed")

    ffmpeg = _ffmpeg_exe()
    subprocess.run(
        [ffmpeg, "-y", "-ss", "0.5", "-i", str(output_path), "-vframes", "1", str(thumb_path)],
        capture_output=True,
        timeout=60,
        check=False,
    )
    duration = _video_duration(ffmpeg, output_path)
    _validate_output(output_path, duration)
    return duration


def _video_job_handler(db: Session, row: PerseoJob) -> Dict[str, Any]:
    payload = __import__("json").loads(row.input_json or "{}")
    user_id = row.user_id
    input_path = _resolve_input_path(payload["input_url"], user_id)
    operations = payload.get("operations") or []

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / f"out_{uuid.uuid4().hex[:8]}.mp4"
        thumb = Path(tmp) / "thumb.jpg"
        update_job(db, row.job_id, progress=40)
        duration = _run_ffmpeg_v2(input_path, out, thumb, operations)
        update_job(db, row.job_id, progress=75)

        if getattr(settings, "PERSEO_V2_ENABLED", False) or storage_backend() == "s3":
            require_cloud_storage()
            video_store = upload_file(out, user_id=user_id, category="videos", content_type="video/mp4")
            thumb_store = (
                upload_file(thumb, user_id=user_id, category="images", content_type="image/jpeg")
                if thumb.exists()
                else None
            )
            return {
                "video_url": video_store["url"],
                "thumbnail_url": thumb_store["url"] if thumb_store else None,
                "duration": duration,
                "storage": video_store["storage"],
                "transaction_id": row.transaction_id,
            }

        dest_dir = Path(settings.STATIC_DIR) / "uploads" / "videos"
        dest_dir.mkdir(parents=True, exist_ok=True)
        final = dest_dir / f"u{user_id}_{uuid.uuid4().hex[:8]}_perseo_v2.mp4"
        final.write_bytes(out.read_bytes())
        return {
            "video_url": f"/static/uploads/videos/{final.name}",
            "duration": duration,
            "storage": "local",
        }


def create_video_edit_job_v2(
    db: Session,
    user: User,
    *,
    input_url: str,
    operations: Optional[List[Dict[str, Any]]] = None,
    transaction_id: Optional[str] = None,
) -> Dict[str, Any]:
    execution = get_execution_status(db)
    if execution["execution_mode"] == "ERROR":
        raise HTTPException(status_code=503, detail="execution_mode ERROR")
    if not execution["writes_enabled"]:
        raise HTTPException(status_code=403, detail="writes_enabled false")
    _ffmpeg_exe()

    created = enqueue_job(
        db,
        user_id=user.id,
        job_type="video_processing",
        payload={"input_url": input_url, "operations": operations or []},
        transaction_id=transaction_id,
    )
    run_job_async(created["job_id"], _video_job_handler)
    return {
        **created,
        "poll_url": f"/api/v1/perseo/v2/jobs/{created['job_id']}",
        "module": "PERSEO",
        "action": "video_edit",
    }


def get_video_job_v2(db: Session, job_id: str, user_id: int) -> Dict[str, Any]:
    return get_job(db, job_id, user_id)
