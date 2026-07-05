"""ZEUS Phase B — safe single-flow contract test (real event bus, no stubs)."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.user import User

logger = logging.getLogger(__name__)

PHASE_B_ENV: Dict[str, str] = {
    "AFRODITA_EXECUTION_ENABLED": "true",
    "AFRODITA_OPS_WRITES": "true",
    "ZEUS_EVENT_BUS_ENABLED": "true",
    "ZEUS_AUTOMATION_ENGINE_ENABLED": "true",
}


def _env_ok(name: str, expected: str) -> bool:
    raw = os.getenv(name)
    if raw is None:
        from config.afrodita_flags_v1 import get_afrodita_safety_flags

        flags = get_afrodita_safety_flags()
        if name == "AFRODITA_EXECUTION_ENABLED":
            return bool(flags.get("AFRODITA_EXECUTION_ENABLED")) == (expected.lower() == "true")
        if name == "AFRODITA_OPS_WRITES":
            return bool(flags.get("writes_enabled")) == (expected.lower() == "true")
        return False
    return raw.strip().lower() == expected.lower()


def check_phase_b_env() -> Dict[str, Any]:
    flags: Dict[str, Any] = {}
    all_ok = True
    for name, expected in PHASE_B_ENV.items():
        ok = _env_ok(name, expected)
        flags[name] = {
            "expected": expected,
            "actual": os.getenv(name),
            "ok": ok,
        }
        if not ok:
            all_ok = False
    return {"all_ok": all_ok, "flags": flags}


def run_test_contract_flow(db: Session, user: Optional[User]) -> Dict[str, Any]:
    """
    Emit one contract_rrhh_created through the real event bus (pipeline + audit).
    Does not create RRHH employee — safe synthetic payload only.
    """
    env_check = check_phase_b_env()
    now = datetime.now(timezone.utc)
    contract_id = f"test-{int(now.timestamp())}"
    payload: Dict[str, Any] = {
        "contract_id": contract_id,
        "document_id": contract_id,
        "employee_name": "TEST USER",
        "employee_code": "TEST-PHASE-B",
        "status": "created",
        "contract_type": "indefinido",
        "role": "Test Role",
        "salary": 25000,
        "test_flow": True,
        "phase_b": True,
        "legal_document": {
            "document_id": contract_id,
            "content_preview": (
                "# Contrato laboral test Phase B\n"
                "Partes: TEST USER · Empresa\n"
                "RGPD 2016/679 " + "x" * 200
            ),
        },
        "owner_agent": "AFRODITA",
    }

    if not env_check["all_ok"]:
        return {
            "success": False,
            "triggered": False,
            "reason": "phase_b_flags_incomplete",
            "env": env_check,
            "event": payload,
            "hint": "Set Railway env: " + ", ".join(PHASE_B_ENV.keys()),
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
        event_name="contract_rrhh_created",
        source_module="AFRODITA",
        payload=payload,
    )

    try:
        from services.zeus_automation_audit_v1 import record_automation_audit

        record_automation_audit(
            db,
            automation_name="contract_rrhh_pipeline",
            agent="AFRODITA",
            trigger_type="phase_b_test",
            status="success" if bus_out.get("active") else "partial",
            input_data=payload,
            output_data=bus_out,
            user_id=user.id if user else None,
        )
    except Exception as exc:
        logger.warning("[PHASE_B_TEST] audit record failed: %s", exc)

    try:
        db.commit()
    except Exception as exc:
        logger.warning("[PHASE_B_TEST] commit failed: %s", exc)
        db.rollback()
        return {
            "success": False,
            "triggered": False,
            "reason": "db_commit_failed",
            "error": str(exc),
            "bus": bus_out,
        }

    return {
        "success": True,
        "triggered": True,
        "real_execution": True,
        "event": payload,
        "bus": bus_out,
        "env": env_check,
        "pipeline": bus_out.get("pipeline"),
    }
