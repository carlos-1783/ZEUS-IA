"""ZEUS Phase C — safe CRM payment risk production test (real event bus)."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.user import User
from services.emit_payment_event_v1 import build_payment_due_payload

logger = logging.getLogger(__name__)

PHASE_C_ENV: Dict[str, str] = {
    "RAFAEL_EXECUTION_ENABLED": "true",
    "ZEUS_EVENT_BUS_ENABLED": "true",
    "ZEUS_AUTOMATION_ENGINE_ENABLED": "true",
}


def _env_ok(name: str, expected: str) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return False
    return raw.strip().lower() == expected.lower()


def check_phase_c_env() -> Dict[str, Any]:
    flags: Dict[str, Any] = {}
    all_ok = True
    for name, expected in PHASE_C_ENV.items():
        ok = _env_ok(name, expected)
        flags[name] = {"expected": expected, "actual": os.getenv(name), "ok": ok}
        if not ok:
            all_ok = False
    return {"all_ok": all_ok, "flags": flags}


def run_test_payment_risk_flow(db: Session, user: Optional[User]) -> Dict[str, Any]:
    """Emit payment_due → crm_payment_risk → payment_risk agents (synthetic only)."""
    env_check = check_phase_c_env()
    payload = build_payment_due_payload()

    if not env_check["all_ok"]:
        return {
            "success": False,
            "triggered": False,
            "reason": "phase_c_flags_incomplete",
            "env": env_check,
            "event": payload,
            "hint": "Set Railway env: " + ", ".join(PHASE_C_ENV.keys()),
        }

    bus_enabled = os.getenv("ZEUS_EVENT_BUS_ENABLED", "true").strip().lower() != "false"
    if not bus_enabled:
        return {
            "success": False,
            "triggered": False,
            "reason": "event_bus_disabled",
            "env": env_check,
        }

    from services.zeus_event_bus_v1 import emit_event

    bus_out = emit_event(
        db,
        user,
        event_name="payment_due",
        source_module="CRM",
        payload=payload,
    )

    try:
        from services.zeus_automation_audit_v1 import record_automation_audit

        record_automation_audit(
            db,
            automation_name="crm_payment_risk",
            agent="RAFAEL",
            trigger_type="phase_c_test",
            status="success" if bus_out.get("active") else "partial",
            input_data=payload,
            output_data=bus_out,
            user_id=user.id if user else None,
        )
    except Exception as exc:
        logger.warning("[PHASE_C_TEST] audit record failed: %s", exc)

    try:
        db.commit()
    except Exception as exc:
        logger.warning("[PHASE_C_TEST] commit failed: %s", exc)
        db.rollback()
        return {
            "success": False,
            "triggered": False,
            "reason": "db_commit_failed",
            "error": str(exc),
            "bus": bus_out,
        }

    risk_eval = None
    pipeline = bus_out.get("pipeline")
    if isinstance(pipeline, dict):
        risk_eval = pipeline.get("crm_payment_risk")

    return {
        "success": True,
        "triggered": True,
        "real_execution": True,
        "event": payload,
        "bus": bus_out,
        "env": env_check,
        "risk": risk_eval.get("evaluation") if isinstance(risk_eval, dict) else None,
        "payment_risk_emitted": (
            risk_eval.get("payment_risk_emitted") if isinstance(risk_eval, dict) else None
        ),
    }
