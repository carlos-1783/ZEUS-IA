"""
PERSEO video engine v1 — FFmpeg trim/scale/edit with async job queue and local storage.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from fastapi import HTTPException, status

from app.core.config import settings
from app.models.user import User
from services.zeus_execution_controller_v1 import get_execution_status

logger = logging.getLogger(__name__)

_job_lock = threading.RLock()
_jobs: Dict[str, Dict[str, Any]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"error": "ffmpeg_unavailable", "message": str(exc)},
        ) from exc


def _video_duration(ffmpeg: str, path: Path) -> float:
    cmd = [ffmpeg, "-hide_banner", "-i", str(path)]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
        for line in (out.stderr or "").splitlines():
            if "Duration:" in line:
                part = line.split("Duration:", 1)[1].split(",")[0].strip()
                h, m, s = part.split(":")
                return round(float(h) * 3600 + float(m) * 60 + float(s), 2)
    except Exception:
        pass
    return 0.0


def _resolve_input_path(input_url: str, user_id: int) -> Path:
    raw = (input_url or "").strip()
    if not raw:
        raise HTTPException(status_code=422, detail="input_url required")

    if raw.startswith("/static/"):
        rel = raw[len("/static/") :]
        path = Path(settings.STATIC_DIR) / rel
    elif raw.startswith("http://") or raw.startswith("https://"):
        parsed = urlparse(raw)
        if parsed.path.startswith("/static/"):
            rel = parsed.path[len("/static/") :]
            path = Path(settings.STATIC_DIR) / rel
        else:
            raise HTTPException(
                status_code=422,
                detail="Remote URLs must be served from /static/ on this host",
            )
    else:
        path = Path(raw)
        if not path.is_absolute():
            path = Path(settings.STATIC_DIR) / raw.lstrip("/")

    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail=f"Input video not found: {raw}")
    if not str(path).startswith(str(Path(settings.STATIC_DIR).resolve())):
        raise HTTPException(status_code=403, detail="Input path outside static storage")
    return path


def _output_paths(user_id: int, job_id: str) -> tuple[Path, Path, str, str]:
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    base = f"u{user_id}_{stamp}_{job_id[:8]}_perseo_edit"
    video_dir = Path(settings.STATIC_DIR) / "uploads" / "videos"
    thumb_dir = Path(settings.STATIC_DIR) / "uploads" / "images"
    video_dir.mkdir(parents=True, exist_ok=True)
    thumb_dir.mkdir(parents=True, exist_ok=True)
    video_path = video_dir / f"{base}.mp4"
    thumb_path = thumb_dir / f"{base}_thumb.jpg"
    video_url = f"/static/uploads/videos/{video_path.name}"
    thumb_url = f"/static/uploads/images/{thumb_path.name}"
    return video_path, thumb_path, video_url, thumb_url


def _build_ffmpeg_filter(operations: List[Dict[str, Any]]) -> tuple[List[str], Optional[str]]:
    """Build ffmpeg args for trim + scale operations."""
    vf_parts: List[str] = []
    trim_start: Optional[float] = None
    trim_end: Optional[float] = None
    for op in operations:
        kind = (op.get("type") or "").lower()
        if kind == "trim":
            trim_start = float(op.get("start_sec") or 0)
            trim_end = float(op["end_sec"]) if op.get("end_sec") is not None else None
        elif kind == "scale":
            w = int(op.get("width") or 1280)
            h = int(op.get("height") or 720)
            vf_parts.append(f"scale={w}:{h}")
    return vf_parts, trim_start, trim_end


def _run_ffmpeg_edit(
    input_path: Path,
    output_path: Path,
    thumb_path: Path,
    operations: List[Dict[str, Any]],
) -> float:
    ffmpeg = _ffmpeg_exe()
    vf_parts, trim_start, trim_end = _build_ffmpeg_filter(operations)

    cmd: List[str] = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
    if trim_start is not None and trim_start > 0:
        cmd.extend(["-ss", str(trim_start)])
    cmd.extend(["-i", str(input_path)])
    if trim_end is not None and trim_start is not None:
        cmd.extend(["-t", str(max(0.1, trim_end - trim_start))])
    elif trim_end is not None:
        cmd.extend(["-t", str(trim_end)])

    if vf_parts:
        cmd.extend(["-vf", ",".join(vf_parts)])

    preset = str(getattr(settings, "PERSEO_FFMPEG_PRESET", "veryfast") or "veryfast")
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

    started = time.monotonic()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False)
    elapsed = time.monotonic() - started
    if proc.returncode != 0 or not output_path.exists() or output_path.stat().st_size < 1024:
        raise RuntimeError(proc.stderr or "FFmpeg produced no output")

    if elapsed < 0.05 and input_path.stat().st_size > 5_000_000:
        raise RuntimeError("Suspicious instant response for heavy video task")

    thumb_cmd = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        "0.5",
        "-i",
        str(output_path),
        "-vframes",
        "1",
        str(thumb_path),
    ]
    subprocess.run(thumb_cmd, capture_output=True, timeout=60, check=False)

    duration = _video_duration(ffmpeg, output_path)
    return duration


def _process_job(job_id: str, user_id: int, input_path: Path, operations: List[Dict[str, Any]]) -> None:
    with _job_lock:
        job = _jobs.get(job_id)
        if not job:
            return
        job["status"] = "processing"
        job["progress"] = 10
        job["updated_at"] = _now_iso()

    video_path, thumb_path, video_url, thumb_url = _output_paths(user_id, job_id)
    try:
        with _job_lock:
            _jobs[job_id]["progress"] = 30
        duration = _run_ffmpeg_edit(input_path, video_path, thumb_path, operations)
        with _job_lock:
            _jobs[job_id].update(
                {
                    "status": "completed",
                    "progress": 100,
                    "video_url": video_url,
                    "thumbnail_url": thumb_url if thumb_path.exists() else None,
                    "duration": duration,
                    "output_path": str(video_path),
                    "updated_at": _now_iso(),
                    "execution_ms": int((time.monotonic()) * 1000),
                }
            )
        logger.info("[PERSEO_VIDEO] job=%s completed duration=%s", job_id, duration)
    except Exception as exc:
        logger.exception("[PERSEO_VIDEO] job=%s failed", job_id)
        with _job_lock:
            _jobs[job_id].update(
                {
                    "status": "failed",
                    "progress": 0,
                    "error": str(exc)[:500],
                    "updated_at": _now_iso(),
                }
            )


def create_video_edit_job(
    db,
    user: User,
    *,
    input_url: str,
    operations: Optional[List[Dict[str, Any]]] = None,
    transaction_id: Optional[str] = None,
) -> Dict[str, Any]:
    execution = get_execution_status(db)
    if execution["execution_mode"] == "ERROR":
        raise HTTPException(status_code=503, detail="ZEUS execution_mode ERROR — DB unavailable")
    if not execution["writes_enabled"]:
        raise HTTPException(
            status_code=403,
            detail="writes_enabled false — enable AFRODITA_EXECUTION_ENABLED for PERSEO video edit",
        )

    _ffmpeg_exe()
    input_path = _resolve_input_path(input_url, user.id)
    ops = operations or [{"type": "scale", "width": 1280, "height": 720}]

    job_id = str(uuid.uuid4())
    job = {
        "job_id": job_id,
        "status": "queued",
        "progress": 0,
        "user_id": user.id,
        "input_url": input_url,
        "operations": ops,
        "transaction_id": transaction_id,
        "module": "PERSEO",
        "action": "video_edit",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    with _job_lock:
        _jobs[job_id] = job

    thread = threading.Thread(
        target=_process_job,
        args=(job_id, user.id, input_path, ops),
        daemon=True,
        name=f"perseo-video-{job_id[:8]}",
    )
    thread.start()

    return {
        "job_id": job_id,
        "status": "queued",
        "progress": 0,
        "poll_url": f"/api/v1/perseo/video/jobs/{job_id}",
        "transaction_id": transaction_id,
        "message": "Video edit job queued — poll for video_url",
    }


def get_video_job(job_id: str, user_id: int) -> Dict[str, Any]:
    with _job_lock:
        job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Job belongs to another user")
    return dict(job)


def execute_video_edit_sync(
    db,
    user: User,
    *,
    input_url: str,
    operations: Optional[List[Dict[str, Any]]] = None,
    transaction_id: Optional[str] = None,
    timeout_sec: float = 120.0,
) -> Dict[str, Any]:
    """Blocking edit for ZEUS transaction steps."""
    created = create_video_edit_job(
        db,
        user,
        input_url=input_url,
        operations=operations,
        transaction_id=transaction_id,
    )
    job_id = created["job_id"]
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        job = get_video_job(job_id, user.id)
        if job["status"] in ("completed", "failed"):
            if job["status"] == "failed":
                raise HTTPException(status_code=500, detail=job.get("error", "Video edit failed"))
            return {
                "success": True,
                "video_url": job["video_url"],
                "thumbnail_url": job.get("thumbnail_url"),
                "duration": job.get("duration"),
                "job_id": job_id,
                "transaction_id": transaction_id,
            }
        time.sleep(0.5)
    raise HTTPException(status_code=504, detail="Video edit job timeout")
