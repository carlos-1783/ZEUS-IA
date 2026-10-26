"""ZEUS automation background worker — daily policy expiration and event jobs."""

from __future__ import annotations

import logging
import threading
import time

from app.core.config import settings

logger = logging.getLogger(__name__)

_worker_thread: threading.Thread | None = None
_worker_running = False
_last_run_at: float = 0.0


def _interval_sec() -> int:
    # Default 24h; override for dev with ZEUS_AUTOMATION_INTERVAL_SEC
    return max(3600, int(getattr(settings, "ZEUS_AUTOMATION_INTERVAL_SEC", 86400) or 86400))


def run_cycle_all_companies() -> int:
    """Un ciclo del job recorriendo las empresas UNA A UNA, cada una en una sesion con SU contexto RLS
    (nunca una sesion sin filtro). Listar las empresas es lo unico que necesita vision global: se hace en
    modo system auditado y solo se leen los ids. Devuelve el total de eventos emitidos."""
    from app.db.rls_context import open_tenant_session, system_db
    from app.models.company import Company
    from services.zeus_automation_engine_v1 import run_automation_cycle

    with system_db("zeus_automation_worker: listar ids de empresas para recorrerlas una a una") as sdb:
        company_ids = [int(r[0]) for r in sdb.query(Company.id).order_by(Company.id.asc()).all()]
    emitted = 0
    for cid in company_ids:
        db = open_tenant_session(cid)
        try:
            result = run_automation_cycle(db, company_id=cid)
            db.commit()
            emitted += int(result.get("policy_expiration_check", {}).get("emitted") or 0)
        except Exception:
            logger.exception("[ZEUS_AUTOMATION_WORKER] cycle failed company_id=%s", cid)
            db.rollback()
        finally:
            db.close()
    return emitted


def _worker_loop() -> None:
    global _worker_running, _last_run_at
    interval = _interval_sec()
    logger.info("[ZEUS_AUTOMATION_WORKER] started interval=%ss", interval)
    while _worker_running:
        now = time.monotonic()
        if now - _last_run_at >= interval:
            try:
                emitted = run_cycle_all_companies()
                _last_run_at = now
                logger.info("[ZEUS_AUTOMATION_WORKER] cycle policy_emitted=%s", emitted)
            except Exception:
                logger.exception("[ZEUS_AUTOMATION_WORKER] cycle failed")
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
