"""THALOS v1 — ciclo de monitorización (wrapper sobre security engine + executor)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from services import thalos_executor

logger = logging.getLogger(__name__)


def run_monitoring_cycle(
    db: Session,
    *,
    company_id: Optional[int] = None,
    user_id: Optional[int] = None,
    auto_execute: bool = False,
    force_scan: bool = False,
) -> Dict[str, Any]:
    """Pipeline real: logs → parser → events → threat engine → alerts."""
    from services.thalos_monitor_service import run_monitor_cycle

    if getattr(settings, "THALOS_ENABLED", True) and (
        settings.THALOS_REAL_MONITORING or settings.THALOS_EXECUTION_ENABLED
        or settings.THALOS_REAL_LOGS_ENABLED or force_scan
    ):
        cycle = run_monitor_cycle(db, company_id=company_id, user_id=user_id)
        rules = cycle.get("alerts") or []
        actions_taken: List[Dict[str, Any]] = []

        if auto_execute and settings.THALOS_EXECUTION_ENABLED:
            for rule in rules:
                action = "alert_admin"
                actions_taken.append(
                    thalos_executor.execute_action(
                        db,
                        action,
                        company_id=company_id,
                        user_id=user_id,
                        payload={"message": rule.get("title") or "THALOS alert"},
                    )
                )

        return {
            "monitoring_enabled": settings.THALOS_REAL_MONITORING,
            "execution_enabled": settings.THALOS_EXECUTION_ENABLED,
            "auto_block_enabled": settings.THALOS_AUTO_BLOCK,
            "scan": cycle.get("security_scan") or cycle,
            "rules_triggered": rules,
            "actions_taken": actions_taken,
            "pipeline": cycle.get("pipeline"),
            "file_events_inserted": cycle.get("file_events_inserted", 0),
            "alerts_created": cycle.get("alerts_created", 0),
        }

    return {
        "monitoring_enabled": False,
        "status": "monitoring_disabled",
        "note": "Enable THALOS_ENABLED + THALOS_REAL_MONITORING or THALOS_REAL_LOGS_ENABLED",
    }
