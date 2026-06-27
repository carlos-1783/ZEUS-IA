"""PERSEO job queue — DB-backed workers with retry policy."""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.perseo_job import PerseoJob

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
JobHandler = Callable[[Session, PerseoJob], Dict[str, Any]]


def _now():
    return datetime.now(timezone.utc)


def _dump(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def _load(raw: Optional[str], default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def enqueue_job(
    db: Session,
    *,
    user_id: int,
    job_type: str,
    payload: Dict[str, Any],
    transaction_id: Optional[str] = None,
) -> Dict[str, Any]:
    job_id = str(uuid.uuid4())
    row = PerseoJob(
        job_id=job_id,
        job_type=job_type,
        status="queued",
        progress=0,
        user_id=user_id,
        transaction_id=transaction_id,
        input_json=_dump(payload),
        metrics_json=_dump({"events": [], "retry_count": 0}),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    from services.perseo_events_v1 import emit_generation_started

    emit_generation_started(user_id, job_id, job_type)
    return {"job_id": job_id, "status": "queued", "job_type": job_type}


def update_job(db: Session, job_id: str, **fields: Any) -> None:
    row = db.query(PerseoJob).filter(PerseoJob.job_id == job_id).first()
    if not row:
        return
    for k, v in fields.items():
        if k.endswith("_json") and isinstance(v, dict):
            setattr(row, k, _dump(v))
        else:
            setattr(row, k, v)
    row.updated_at = _now()
    db.add(row)
    db.commit()
    if "progress" in fields and row.user_id:
        from services.perseo_events_v1 import emit_generation_progress

        emit_generation_progress(row.user_id, job_id, int(fields.get("progress") or 0), str(fields.get("status") or row.status))


def get_job(db: Session, job_id: str, user_id: int) -> Dict[str, Any]:
    row = db.query(PerseoJob).filter(PerseoJob.job_id == job_id, PerseoJob.user_id == user_id).first()
    if not row:
        raise ValueError("job_not_found")
    return {
        "job_id": row.job_id,
        "job_type": row.job_type,
        "status": row.status,
        "progress": row.progress,
        "transaction_id": row.transaction_id,
        "input": _load(row.input_json, {}),
        "output": _load(row.output_json, {}),
        "error": row.error,
        "metrics": _load(row.metrics_json, {}),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def run_job_async(job_id: str, handler: JobHandler) -> None:
    thread = threading.Thread(
        target=_worker,
        args=(job_id, handler),
        daemon=True,
        name=f"perseo-job-{job_id[:8]}",
    )
    thread.start()


def _worker(job_id: str, handler: JobHandler) -> None:
    db = SessionLocal()
    try:
        row = db.query(PerseoJob).filter(PerseoJob.job_id == job_id).first()
        if not row:
            return
        metrics = _load(row.metrics_json, {})
        retry = int(metrics.get("retry_count") or 0)
        update_job(db, job_id, status="processing", progress=5)
        while retry <= MAX_RETRIES:
            try:
                output = handler(db, row)
                update_job(
                    db,
                    job_id,
                    status="completed",
                    progress=100,
                    output_json=output,
                    error=None,
                )
                from services.perseo_events_v1 import emit_generation_completed

                emit_generation_completed(row.user_id, job_id, output)
                return
            except Exception as exc:
                retry += 1
                metrics["retry_count"] = retry
                metrics.setdefault("errors", []).append(str(exc)[:300])
                logger.exception("[PERSEO_QUEUE] job=%s attempt=%s failed", job_id, retry)
                if retry > MAX_RETRIES:
                    update_job(
                        db,
                        job_id,
                        status="failed",
                        progress=0,
                        error=str(exc)[:500],
                        metrics_json=metrics,
                    )
                    return
                time.sleep(0.1 * (2**retry))
                update_job(db, job_id, metrics_json=metrics, progress=min(90, 10 + retry * 20))
    finally:
        db.close()


def count_jobs_by_status(db: Session, status: str) -> int:
    return db.query(PerseoJob).filter(PerseoJob.status == status).count()
