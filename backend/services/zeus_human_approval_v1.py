"""
Capa de control humano v1 — acciones críticas requieren aprobación CEO/usuario.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.orm import Session

from app.models.zeus_pending_approval import ZeusPendingApproval
from app.models.user import User

CRITICAL_ACTIONS: Set[str] = frozenset({
    "send_campaign",
    "launch_campaign",
    "generate_invoice",
    "generate_model_303",
    "high_value_actions",
    "contract_generation",
})

HIGH_VALUE_THRESHOLD_EUR = 500.0


def requires_approval(action_type: str, payload: Optional[Dict[str, Any]] = None) -> bool:
    if action_type in CRITICAL_ACTIONS:
        return True
    if action_type == "register_payment":
        amt = float((payload or {}).get("amount") or 0)
        return amt >= HIGH_VALUE_THRESHOLD_EUR
    return False


def request_approval(
    db: Session,
    *,
    user: User,
    company_id: int,
    agent_name: str,
    action_type: str,
    payload: Dict[str, Any],
    role_required: str = "ceo",
) -> ZeusPendingApproval:
    row = ZeusPendingApproval(
        company_id=company_id,
        user_id=user.id,
        agent_name=agent_name,
        action_type=action_type,
        payload_json=json.dumps(payload, ensure_ascii=False),
        status="pending",
        role_required=role_required,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_pending(db: Session, *, user: User, company_id: int) -> List[Dict[str, Any]]:
    rows = (
        db.query(ZeusPendingApproval)
        .filter(
            ZeusPendingApproval.company_id == company_id,
            ZeusPendingApproval.status == "pending",
        )
        .order_by(ZeusPendingApproval.created_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "agent_name": r.agent_name,
            "action_type": r.action_type,
            "payload": json.loads(r.payload_json or "{}"),
            "role_required": r.role_required,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


def resolve_approval(
    db: Session,
    *,
    approval_id: int,
    user: User,
    approve: bool,
) -> ZeusPendingApproval:
    row = db.query(ZeusPendingApproval).filter(ZeusPendingApproval.id == approval_id).first()
    if not row:
        raise ValueError("Solicitud no encontrada")
    if row.status != "pending":
        raise ValueError("Solicitud ya resuelta")
    row.status = "approved" if approve else "rejected"
    row.resolved_at = datetime.now(timezone.utc)
    row.resolved_by_user_id = user.id
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
