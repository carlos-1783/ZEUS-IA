"""THALOS v1 — ciclo de monitorización (wrapper sobre security engine + executor)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from services import thalos_executor, thalos_security_engine

logger = logging.getLogger(__name__)


def run_monitoring_cycle(
    db: Session,
    *,
    company_id: Optional[int] = None,
    user_id: Optional[int] = None,
    auto_execute: bool = False,
    force_scan: bool = False,
) -> Dict[str, Any]:
    """
    Escaneo real de logs y evaluación de reglas.
    Con force_scan=True (UI workspace) ejecuta scan aunque flags estén off.
    """
    scan: Dict[str, Any] = {}
    if settings.THALOS_REAL_MONITORING or settings.THALOS_EXECUTION_ENABLED or force_scan:
        scan = thalos_security_engine.scan_logs(db, hours=24, company_id=company_id)
    else:
        scan = {
            "status": "monitoring_disabled",
            "note": "Enable THALOS_REAL_MONITORING or THALOS_EXECUTION_ENABLED",
        }

    rules = thalos_security_engine.evaluate_decision_rules(db, company_id=company_id)
    actions_taken: List[Dict[str, Any]] = []

    if auto_execute and settings.THALOS_EXECUTION_ENABLED:
        for rule in rules:
            action = rule.get("action")
            if not action:
                continue
            ctx = rule.get("context") or {}
            if action == "block_user" and ctx.get("email"):
                actions_taken.append(
                    thalos_executor.execute_action(
                        db,
                        "block_user",
                        company_id=company_id,
                        user_id=user_id,
                        user_email=ctx["email"],
                    )
                )
            elif action == "audit_cashflow_anomaly" and company_id:
                actions_taken.append(
                    thalos_executor.execute_action(
                        db,
                        "audit_cashflow_anomaly",
                        company_id=company_id,
                        user_id=user_id,
                    )
                )
            elif action == "trigger_backup":
                actions_taken.append(
                    thalos_executor.execute_action(
                        db, "trigger_backup", company_id=company_id, user_id=user_id
                    )
                )
            elif action == "alert_admin":
                actions_taken.append(
                    thalos_executor.execute_action(
                        db,
                        "alert_admin",
                        company_id=company_id,
                        user_id=user_id,
                        payload={"message": f"THALOS rule: {rule.get('condition')}"},
                    )
                )

    result = {
        "monitoring_enabled": settings.THALOS_REAL_MONITORING,
        "execution_enabled": settings.THALOS_EXECUTION_ENABLED,
        "auto_block_enabled": settings.THALOS_AUTO_BLOCK,
        "scan": scan,
        "rules_triggered": rules,
        "actions_taken": actions_taken,
    }

    if user_id and scan and scan.get("status") != "monitoring_disabled":
        from services.thalos_workspace_writer_v1 import write_from_action_result

        write_from_action_result(
            db,
            user_id=user_id,
            company_id=company_id,
            action="security_monitor",
            result={"status": "completed", "executed": True, "result": scan, "rules": rules},
            source="monitoring_cycle",
        )

    return result
