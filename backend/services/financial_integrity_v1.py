"""Integridad financiera — company_id obligatorio y balances coherentes."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from services.zeus_core_guard_v1 import (
    ZeusGuardViolation,
    apply_guard,
    closure_active,
    guard_enforce,
    validate_critical_action,
)

logger = logging.getLogger(__name__)


def assert_financial_record_valid(
    db: Session,
    *,
    company_id: Optional[int],
    amount: float,
    domain: str = "cashflow",
    action: str = "record_movement",
    actor_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Valida registro financiero antes de persistir."""
    gr = validate_critical_action(
        domain,
        action,
        company_id=company_id,
        actor_id=actor_id,
        layer="service",
        db=db,
        payload={"amount": amount},
    )
    if float(amount or 0) < 0:
        gr.allowed = False
        gr.reason = "negative_amount"
        gr.human_message = "Importe negativo no permitido en ledger"

    if closure_active():
        try:
            apply_guard(gr, db=db)
        except ZeusGuardViolation as exc:
            return {"valid": False, "blocked": True, "guard": exc.result.to_dict()}

    if not gr.allowed and guard_enforce():
        return {"valid": False, "blocked": True, "guard": gr.to_dict()}

    return {"valid": True, "blocked": False, "guard": gr.to_dict()}


def validate_invoice_company(company_id: Optional[int], *, db: Optional[Session] = None) -> bool:
    gr = validate_critical_action(
        "invoices",
        "create_invoice",
        company_id=company_id,
        layer="service",
        db=db,
    )
    return gr.allowed or not guard_enforce()
