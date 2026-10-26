"""THALOS background worker — continuous log polling and event processing."""

from __future__ import annotations

import logging
import threading
import time

from app.core.config import settings
from app.db.rls_context import open_system_session

logger = logging.getLogger(__name__)

_worker_thread: threading.Thread | None = None
_worker_running = False


def _worker_loop() -> None:
    global _worker_running
    interval = max(5, int(getattr(settings, "THALOS_WORKER_INTERVAL_SEC", 30) or 30))
    logger.info("[THALOS_WORKER] started interval=%ss", interval)
    while _worker_running:
        # Vision global EXPLICITA (modo system auditado): el monitor de seguridad correlaciona eventos de
        # todas las empresas (fuerza bruta, IPs, patrones) y escribe cada alerta con la empresa resuelta;
        # no sirve datos a ningun tenant. Ver app/db/rls_context.py.
        db = open_system_session("thalos_worker: ciclo global del monitor de seguridad")
        try:
            from services.thalos_monitor_service import run_monitor_cycle

            result = run_monitor_cycle(db)
            db.commit()
            if result.get("file_events_inserted") or result.get("alerts_created"):
                logger.info(
                    "[THALOS_WORKER] cycle events=%s alerts=%s",
                    result.get("file_events_inserted"),
                    result.get("alerts_created"),
                )
        except Exception:
            logger.exception("[THALOS_WORKER] cycle failed")
            db.rollback()
        finally:
            db.close()
        time.sleep(interval)
    logger.info("[THALOS_WORKER] stopped")


def start_thalos_worker() -> None:
    global _worker_thread, _worker_running
    if not getattr(settings, "THALOS_ENABLED", True):
        logger.info("[THALOS_WORKER] skipped (THALOS_ENABLED=false)")
        return
    if not (
        settings.THALOS_REAL_MONITORING
        or settings.THALOS_REAL_LOGS_ENABLED
        or settings.THALOS_EXECUTION_ENABLED
    ):
        logger.info("[THALOS_WORKER] skipped (no monitoring flags enabled)")
        return
    if _worker_thread and _worker_thread.is_alive():
        return
    _worker_running = True
    _worker_thread = threading.Thread(target=_worker_loop, daemon=True, name="thalos-worker")
    _worker_thread.start()


def stop_thalos_worker() -> None:
    global _worker_running
    _worker_running = False


def worker_status() -> dict:
    return {
        "running": bool(_worker_thread and _worker_thread.is_alive()),
        "enabled": bool(getattr(settings, "THALOS_ENABLED", True)),
        "interval_sec": int(getattr(settings, "THALOS_WORKER_INTERVAL_SEC", 30) or 30),
    }
