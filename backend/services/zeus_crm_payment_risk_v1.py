"""CRM payment risk scoring — amount-based evaluation + RAFAEL agent propagation."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.user import User

logger = logging.getLogger(__name__)


def evaluate_payment_risk(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Simple real scoring by pending amount."""
    try:
        amount = float(payload.get("amount") or 0)
    except (TypeError, ValueError):
        amount = 0.0

    if amount > 1000:
        risk = "high"
    elif amount > 300:
        risk = "medium"
    else:
        risk = "low"

    client_id = payload.get("client_id") or payload.get("customer_id")
    return {
        "client_id": client_id,
        "customer_id": client_id,
        "name": payload.get("name") or payload.get("client_name") or "Cliente",
        "amount": amount,
        "risk": risk,
        "risk_level": risk,
        "status": payload.get("status") or "pending",
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "source": "crm_payment_risk_v1",
    }


def handle_crm_payment_risk(
    db: Session,
    user: Optional[User],
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Evaluate payment_due payload, audit, and propagate payment_risk to agents when needed.
    """
    result = evaluate_payment_risk(payload)

    try:
        from services.zeus_automation_audit_v1 import record_automation_audit

        record_automation_audit(
            db,
            automation_name="crm_payment_risk",
            agent="RAFAEL",
            trigger_type="payment_due",
            status="success",
            input_data=payload,
            output_data=result,
            user_id=user.id if user else None,
        )
    except Exception as exc:
        logger.warning("[CRM_PAYMENT_RISK] audit failed: %s", exc)

    payment_risk_out: Optional[Dict[str, Any]] = None
    if result["risk"] in ("medium", "high"):
        try:
            from services.zeus_event_bus_v1 import emit_event

            payment_risk_out = emit_event(
                db,
                user,
                event_name="payment_risk",
                source_module="RAFAEL",
                payload={**payload, **result},
            )
        except Exception as exc:
            logger.warning("[CRM_PAYMENT_RISK] payment_risk emit failed: %s", exc)

    return {
        "evaluation": result,
        "payment_risk_emitted": payment_risk_out is not None,
        "payment_risk": payment_risk_out,
    }
