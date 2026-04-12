"""
ROCE — colas de edición de vídeo en JSON bajo STATIC_DIR (sin migraciones).
El procesamiento pesado corre en BackgroundTasks / hilo; no bloquea el event loop.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import settings

from services.roce_video_ffmpeg import apply_operations, resolve_safe_under_uploads, uploads_root


def jobs_dir() -> Path:
    d = uploads_root() / "video_roce_jobs"
    d.mkdir(parents=True, exist_ok=True)
    return d

logger = logging.getLogger(__name__)

MAX_OPS = 12


def _job_path(job_id: str) -> Path:
    return jobs_dir() / f"{job_id}.json"


def create_job(
    user_id: int,
    source_relative: str,
    operations: List[Dict[str, Any]],
    workspace_document_id: Optional[int] = None,
) -> str:
    job_id = uuid.uuid4().hex
    rec: Dict[str, Any] = {
        "job_id": job_id,
        "user_id": int(user_id),
        "status": "queued",
        "source_relative": source_relative.strip(),
        "operations": operations[:MAX_OPS],
        "workspace_document_id": workspace_document_id,
        "output_relative": None,
        "error": None,
        "public_url": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _job_path(job_id).write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    return job_id


def load_job(job_id: str) -> Optional[Dict[str, Any]]:
    p = _job_path(job_id)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("roce job json corrupto job_id=%s", job_id)
        return None


def save_job(rec: Dict[str, Any]) -> None:
    rec["updated_at"] = datetime.now(timezone.utc).isoformat()
    _job_path(str(rec["job_id"])).write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")


def _try_attach_workspace(user_id: int, workspace_document_id: Any, public_url: str, job_id: str) -> None:
    if workspace_document_id is None:
        return
    try:
        did = int(workspace_document_id)
    except (TypeError, ValueError):
        logger.warning("roce workspace_document_id inválido job=%s", job_id)
        return
    try:
        from app.db.session import SessionLocal
        from services.workspace_deliverables import attach_roce_processed_video_to_document

        db = SessionLocal()
        try:
            attach_roce_processed_video_to_document(
                db,
                document_id=did,
                user_id=int(user_id),
                public_url=public_url,
                job_id=job_id,
            )
        finally:
            db.close()
    except Exception:
        logger.exception("roce workspace attach error job=%s", job_id)


def _budget_sec() -> float:
    try:
        v = float(os.getenv("ROCE_VIDEO_JOB_BUDGET_SEC", "30") or "30")
    except (TypeError, ValueError):
        v = 30.0
    return max(10.0, min(v, 120.0))


def run_roce_job(job_id: str) -> None:
    rec = load_job(job_id)
    if not rec:
        return
    # Permitir reintento desde failed (mismo job_id no se reusa; nuevo job desde API).
    if rec.get("status") not in ("queued",):
        return
    uid = int(rec.get("user_id") or 0)
    try:
        rec["status"] = "running"
        rec["error"] = None
        save_job(rec)

        src_rel = str(rec.get("source_relative") or "")
        src = resolve_safe_under_uploads(src_rel)
        if not src.is_file():
            rec["status"] = "failed"
            rec["error"] = "archivo_fuente_no_encontrado"
            save_job(rec)
            return

        ops = rec.get("operations") or []
        if not isinstance(ops, list):
            ops = []
        ops = [o for o in ops if isinstance(o, dict)][:MAX_OPS]

        tmp_root = Path(tempfile.mkdtemp(prefix=f"roce_job_{job_id}_"))
        try:
            work = tmp_root / "work"
            work.mkdir(parents=True, exist_ok=True)
            local_src = work / "source_in.mp4"
            shutil.copy2(src, local_src)

            ok, out_path, err = apply_operations(
                local_src,
                ops,
                work,
                budget_sec=_budget_sec(),
            )
            if not ok:
                rec["status"] = "failed"
                rec["error"] = err or "pipeline_fallo"
                save_job(rec)
                return

            out_dir = uploads_root() / "video_roce"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_name = f"roce_out_{job_id}.mp4"
            final = out_dir / out_name
            shutil.copy2(out_path, final)
            rel_out = f"video_roce/{out_name}"
            base = (settings.STATIC_URL or "").rstrip("/")
            if base.startswith("http://") or base.startswith("https://"):
                url = f"{base}/uploads/{rel_out}"
            elif base:
                url = f"{base}/uploads/{rel_out}"
            else:
                url = f"/uploads/{rel_out}"
            rec["status"] = "completed"
            rec["output_relative"] = rel_out
            rec["public_url"] = url
            rec["error"] = None
            save_job(rec)
            _try_attach_workspace(uid, rec.get("workspace_document_id"), url, job_id)
            logger.info("roce job ok job_id=%s out=%s", job_id, rel_out)
        finally:
            shutil.rmtree(tmp_root, ignore_errors=True)
    except Exception as e:
        logger.exception("roce job error job_id=%s", job_id)
        try:
            rec = load_job(job_id) or {"job_id": job_id, "user_id": uid}
            rec["status"] = "failed"
            rec["error"] = str(e)[:400]
            save_job(rec)
        except Exception:
            pass


def run_roce_job_safe(job_id: str) -> None:
    try:
        run_roce_job(job_id)
    except Exception:
        logger.exception("roce job safe wrapper job_id=%s", job_id)
        try:
            rec = load_job(job_id)
            if rec:
                rec["status"] = "failed"
                rec["error"] = "error_interno_job"
                save_job(rec)
        except Exception:
            pass


def public_job_view(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Respuesta API sin rutas absolutas internas."""
    return {
        "job_id": rec.get("job_id"),
        "status": rec.get("status"),
        "error": rec.get("error"),
        "public_url": rec.get("public_url"),
        "source_relative": rec.get("source_relative"),
        "workspace_document_id": rec.get("workspace_document_id"),
        "created_at": rec.get("created_at"),
        "updated_at": rec.get("updated_at"),
    }
