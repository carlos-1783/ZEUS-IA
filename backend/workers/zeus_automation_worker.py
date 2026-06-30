"""ZEUS automation background worker — daily policy expiration and event jobs."""

from __future__ import annotations

import logging
import threading
import time

from app.core.config import settings
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

_worker_thread: threading.Thread | None = None
_worker_running = False
_last_run_at: float = 0.0


def _interval_sec() -> int:
    # Default 24h; override for dev with ZEUS_AUTOMATION_INTERVAL_SEC
    return max(3600, int(getattr(settings, "ZEUS_AUTOMATION_INTERVAL_SEC", 86400) or 86400))


def _worker_loop() -> None:
    global _worker_running, _last_run_at
    interval = _interval_sec()
    logger.info("[ZEUS_AUTOMATION_WORKER] started interval=%ss", interval)
    while _worker_running:
        now = time.monotonic()
        if now - _last_run_at >= interval:
            db = SessionLocal()
            try:
                from services.zeus_automation_engine_v1 import run_automation_cycle

                result = run_automation_cycle(db)
                db.commit()
                _last_run_at = now
                logger.info(
                    "[ZEUS_AUTOMATION_WORKER] cycle policy_emitted=%s",
                    result.get("policy_expiration_check", {}).get("emitted"),
                )
            except Exception:
                logger.exception("[ZEUS_AUTOMATION_WORKER] cycle failed")
                db.rollback()
            finally:
                db.close()
        time.sleep(min(60, interval // 10))


def start_zeus_automation_worker() -> None:
    global _worker_thread, _worker_running
    if not getattr(settings, "ZEUS_AUTOMATION_ENABLED", True):
        logger.info("[ZEUS_AUTOMATION_WORKER] skipped (ZEUS_AUTOMATION_ENABLED=false)")
        return
    if _worker_thread and _worker_thread.is_alive():
        return
    _worker_running = True
    _worker_thread = threading.Thread(target=_worker_loop, daemon=True, name="zeus-automation-worker")
    _worker_thread.start()


def stop_zeus_automation_worker() -> None:
    global _worker_running
    _worker_running = False


def worker_status() -> dict:
    return {
        "running": bool(_worker_thread and _worker_thread.is_alive()),
        "interval_sec": _interval_sec(),
        "last_run_at": _last_run_at,
    }
