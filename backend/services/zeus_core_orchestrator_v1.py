"""ZEUS CORE orchestrator — multi-agent real execution for payment_due and beyond."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.compliance_event import ComplianceEvent
from app.models.user import User

logger = logging.getLogger(__name__)

CORE_ORCHESTRATION_ENV: Dict[str, str] = {
    "ZEUS_CORE_ENABLED": "true",
    "ZEUS_AGENT_ENABLED": "true",
    "RAFAEL_EXECUTION_ENABLED": "true",
    "AFRODITA_EXECUTION_ENABLED": "true",
    "THALOS_EXECUTION_ENABLED": "true",
    "JUSTICE_REAL_AUDIT_ENABLED": "true",
}


def _env_ok(name: str, expected: str) -> bool:
    raw = os.getenv(name)
    if raw is not None:
        return raw.strip().lower() == expected.lower()
    if name == "ZEUS_AGENT_ENABLED":
        return bool(getattr(settings, "ZEUS_AGENT_ENABLED", True)) == (expected.lower() == "true")
    if name == "ZEUS_CORE_ENABLED":
        return bool(getattr(settings, "ZEUS_CORE_ENABLED", False)) == (expected.lower() == "true")
    if name == "THALOS_EXECUTION_ENABLED":
        return bool(getattr(settings, "THALOS_EXECUTION_ENABLED", False)) == (expected.lower() == "true")
    if name == "JUSTICE_REAL_AUDIT_ENABLED":
        return bool(getattr(settings, "JUSTICE_REAL_AUDIT_ENABLED", False)) == (
            expected.lower() == "true"
        )
    if name == "AFRODITA_EXECUTION_ENABLED":
        from config.afrodita_flags_v1 import get_afrodita_safety_flags

        return bool(get_afrodita_safety_flags().get("AFRODITA_EXECUTION_ENABLED")) == (
            expected.lower() == "true"
        )
    return False


def check_core_orchestration_env() -> Dict[str, Any]:
    flags: Dict[str, Any] = {}
    all_ok = True
    for name, expected in CORE_ORCHESTRATION_ENV.items():
        ok = _env_ok(name, expected)
        flags[name] = {"expected": expected, "actual": os.getenv(name), "ok": ok}
        if not ok:
            all_ok = False
    return {"all_ok": all_ok, "flags": flags}


def is_core_orchestration_active() -> bool:
    return check_core_orchestration_env()["all_ok"]


def _agent_rafael_payment(payload: Dict[str, Any]) -> Dict[str, Any]:
    from services.zeus_crm_payment_risk_v1 import evaluate_payment_risk

    out = evaluate_payment_risk(payload)
    out["agent"] = "RAFAEL"
    out["action"] = "evaluate_payment_risk"
    return out


def _agent_afrodita_create_task(
    db: Session,
    user: User,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    from services.teamflow_persistence_v1 import create_item

    name = payload.get("name") or payload.get("client_name") or "cliente"
    item = create_item(
        db,
        user,
        owner_agent="AFRODITA",
        source_agent="ZEUS_CORE",
        target_agent="AFRODITA",
        title=f"Gestión cobro — {name}",
        item_type="payment_ops_task",
        status="pending",
        content={**payload, "action": "create_task"},
    )
    return {"agent": "AFRODITA", "action": "create_task", "item": item}


def _agent_justicia_legal_check(
    db: Session,
    user: User,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    if not getattr(settings, "JUSTICE_REAL_AUDIT_ENABLED", False):
        return {
            "agent": "JUSTICIA",
            "action": "legal_check",
            "skipped": True,
            "reason": "JUSTICE_REAL_AUDIT_ENABLED=false",
        }
    row = ComplianceEvent(
        event_type="legal_check",
        severity="medium",
        source="JUSTICIA",
        details_json=json.dumps(
            {
                "client_id": payload.get("client_id") or payload.get("customer_id"),
                "amount": payload.get("amount"),
                "risk": payload.get("risk") or payload.get("risk_level"),
                "action": "legal_check",
            },
            ensure_ascii=False,
            default=str,
        ),
    )
    db.add(row)
    db.flush()
    return {"agent": "JUSTICIA", "action": "legal_check", "compliance_event": True}


def _agent_thalos_monitor_case(
    db: Session,
    user: User,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    from services.teamflow_persistence_v1 import create_item

    name = payload.get("name") or payload.get("client_name") or "cliente"
    item = create_item(
        db,
        user,
        owner_agent="THALOS",
        source_agent="ZEUS_CORE",
        target_agent="THALOS",
        title=f"Monitor caso pago — {name}",
        item_type="payment_risk_monitor",
        status="pending",
        content={**payload, "action": "monitor_case"},
    )
    try:
        from services.zeus_analytics_real_v1 import record_zeus_alert

        record_zeus_alert(
            db,
            level=payload.get("risk_level") or payload.get("risk") or "high",
            message=f"ZEUS CORE monitor — {name}",
            user_id=user.id,
        )
    except Exception:
        pass
    return {"agent": "THALOS", "action": "monitor_case", "item": item}


def zeus_core_orchestrate_payment_due(
    db: Session,
    user: Optional[User],
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
  Multi-agent orchestration for payment_due:
  RAFAEL → (if high) AFRODITA + JUSTICIA + THALOS
    """
    if not user:
        return {
            "orchestrated": False,
            "reason": "user_required",
            "fallback": True,
        }

    env_check = check_core_orchestration_env()
    if not env_check["all_ok"]:
        return {
            "orchestrated": False,
            "reason": "core_flags_incomplete",
            "env": env_check,
            "fallback": True,
        }

    results: Dict[str, Any] = {}
    merged = dict(payload)

    rafael = _agent_rafael_payment(merged)
    results["rafael"] = rafael
    merged.update(rafael)

    risk = rafael.get("risk")
    if risk == "high":
        if _env_ok("AFRODITA_EXECUTION_ENABLED", "true"):
            results["afrodita"] = _agent_afrodita_create_task(db, user, merged)
        if _env_ok("JUSTICE_REAL_AUDIT_ENABLED", "true"):
            results["justicia"] = _agent_justicia_legal_check(db, user, merged)
        if _env_ok("THALOS_EXECUTION_ENABLED", "true"):
            results["thalos"] = _agent_thalos_monitor_case(db, user, merged)

    try:
        from services.zeus_automation_audit_v1 import record_automation_audit

        record_automation_audit(
            db,
            automation_name="zeus_core_orchestration",
            agent="ZEUS",
            trigger_type="payment_due",
            status="success",
            input_data=payload,
            output_data=results,
            user_id=user.id,
        )
    except Exception as exc:
        logger.warning("[ZEUS_CORE] audit failed: %s", exc)

    return {
        "orchestrated": True,
        "mode": "multi_agent_real_execution",
        "event_type": "payment_due",
        "risk": risk,
        "results": results,
        "agents_invoked": list(results.keys()),
    }
