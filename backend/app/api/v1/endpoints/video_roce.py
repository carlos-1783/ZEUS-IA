"""
ROCE — API de edición básica de vídeo con FFmpeg.
Rutas: /api/v1/video/... y alias /api/video/... (mismo router).
No bloquea: POST /process encola trabajo; GET /jobs y /download consultan resultado.
"""

from __future__ import annotations

import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from app.core.auth import get_current_active_user
from app.core.config import settings
from app.models.user import User

from services.roce_video_ffmpeg import ffmpeg_binary, resolve_safe_under_uploads
from services.roce_video_jobs import (
    create_job,
    load_job,
    public_job_view,
    run_roce_job_safe,
)

router = APIRouter()

MAX_UPLOAD_BYTES = 100 * 1024 * 1024
VIDEO_CT = frozenset({"video/mp4", "video/webm", "video/quicktime"})
AUDIO_CT = frozenset(
    {
        "audio/mpeg",
        "audio/mp3",
        "audio/wav",
        "audio/x-wav",
        "audio/mp4",
        "audio/aac",
    }
)

_FILENAME_SAFE = re.compile(r"^[^/\\]+$")


def _safe_name(name: str) -> str:
    base = Path(name or "file").name
    base = re.sub(r"[^a-zA-Z0-9._-]", "_", base)[:120]
    return base or "file.bin"


def _save_upload(category: str, user: User, raw: bytes, filename: str) -> str:
    """Devuelve ruta relativa bajo uploads/ (p.ej. video_roce/u1_....mp4)."""
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Archivo demasiado grande (máx. 100 MB).")
    sub = (Path("uploads") / category).as_posix()
    root = (Path(settings.STATIC_DIR) / "uploads" / category).resolve()
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    fn = f"u{user.id}_{stamp}_{_safe_name(filename)}"
    dest = root / fn
    dest.write_bytes(raw)
    rel = f"{category}/{fn}"
    return rel


@router.get("/health")
async def video_health():
    """Comprueba que ffmpeg responde (Railway / Docker)."""
    try:
        r = subprocess.run(
            [ffmpeg_binary(), "-version"],
            capture_output=True,
            text=True,
            timeout=8.0,
            check=False,
        )
        blob = ((r.stdout or "") + (r.stderr or "")).lower()
        ok = r.returncode == 0 and "ffmpeg version" in blob
        return JSONResponse(
            {
                "success": ok,
                "ffmpeg": ffmpeg_binary(),
                "message": "ok" if ok else ((r.stderr or r.stdout or "")[:200] or "ffmpeg_error"),
            },
            status_code=200 if ok else 503,
        )
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)[:200]}, status_code=503)


@router.post("/upload")
async def video_upload(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
):
    """Sube un vídeo para la pipeline ROCE (queda en uploads/video_roce/)."""
    try:
        ct = (file.content_type or "").split(";")[0].strip().lower()
        if ct not in VIDEO_CT:
            raise HTTPException(status_code=415, detail=f"Tipo no permitido: {ct}")
        raw = await file.read()
        rel = _save_upload("video_roce", current_user, raw, file.filename or "video.mp4")
        url = f"{settings.STATIC_URL.rstrip('/')}/uploads/{rel}"
        return {"success": True, "file_id": rel, "url": url}
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse({"success": False, "detail": str(e)[:300]}, status_code=500)


@router.post("/upload-audio")
async def video_upload_audio(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
):
    """Sube pista de audio para operación music (uploads/roce_audio/)."""
    try:
        ct = (file.content_type or "").split(";")[0].strip().lower()
        if ct not in AUDIO_CT:
            raise HTTPException(status_code=415, detail=f"Tipo de audio no permitido: {ct}")
        raw = await file.read()
        if len(raw) > 30 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Audio máx. 30 MB")
        rel = _save_upload("roce_audio", current_user, raw, file.filename or "audio.mp3")
        url = f"{settings.STATIC_URL.rstrip('/')}/uploads/{rel}"
        return {"success": True, "file_id": rel, "url": url}
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse({"success": False, "detail": str(e)[:300]}, status_code=500)


class VideoProcessBody(BaseModel):
    """Operaciones en orden. Tipos: trim, text, music, convert, concat."""

    source_file_id: str = Field(..., min_length=5, max_length=400)
    operations: List[Dict[str, Any]] = Field(default_factory=list, max_length=12)
    workspace_document_id: Optional[int] = Field(
        default=None,
        description="Opcional: ID document_approvals para trazabilidad (no muta el workspace automáticamente).",
    )


@router.post("/process")
async def video_process(
    body: VideoProcessBody,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
):
    """
    Encola edición FFmpeg. Respuesta inmediata con job_id.
    Presupuesto de CPU total: ROCE_VIDEO_JOB_BUDGET_SEC (default 30).
    """
    try:
        resolve_safe_under_uploads(body.source_file_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="source_file_id no válido")
    if not isinstance(body.operations, list):
        raise HTTPException(status_code=400, detail="operations debe ser lista")
    job_id = create_job(
        current_user.id,
        body.source_file_id,
        body.operations,
        workspace_document_id=body.workspace_document_id,
    )
    background_tasks.add_task(run_roce_job_safe, job_id)
    return {
        "success": True,
        "job_id": job_id,
        "status": "queued",
        "message": "Procesamiento encolado. Consulta GET /api/v1/video/jobs/{job_id} o GET /api/video/jobs/{job_id}",
    }


@router.get("/jobs/{job_id}")
async def video_job_status(job_id: str, current_user: User = Depends(get_current_active_user)):
    rec = load_job(job_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    if int(rec.get("user_id") or 0) != int(current_user.id):
        raise HTTPException(status_code=403, detail="No autorizado")
    return {"success": True, "job": public_job_view(rec)}


@router.get("/download/{job_id}")
async def video_download(job_id: str, current_user: User = Depends(get_current_active_user)):
    """Descarga el MP4 resultante cuando status=completed."""
    rec = load_job(job_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    if int(rec.get("user_id") or 0) != int(current_user.id):
        raise HTTPException(status_code=403, detail="No autorizado")
    if rec.get("status") != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Job no listo: status={rec.get('status')}",
        )
    rel = str(rec.get("output_relative") or "")
    try:
        p = resolve_safe_under_uploads(rel)
    except ValueError:
        raise HTTPException(status_code=500, detail="Ruta de salida inválida")
    if not p.is_file():
        raise HTTPException(status_code=404, detail="Archivo de salida no encontrado")
    return FileResponse(
        path=str(p),
        media_type="video/mp4",
        filename=f"roce_{job_id}.mp4",
    )
