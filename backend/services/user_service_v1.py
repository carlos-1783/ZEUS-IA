"""User mutations — todas las rutas críticas pasan por zeus_core_guard."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.user import User
from services.zeus_core_guard_v1 import (
    ZeusGuardViolation,
    apply_guard,
    guard_enforce,
    validate_critical_action,
)

logger = logging.getLogger(__name__)


def secure_deactivate(
    db: Session,
    user: User,
    *,
    reason: str = "security",
    actor_email: Optional[str] = None,
    actor_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Desactivar usuario con validación de guard (sustituye is_active=False directo)."""
    gr = validate_critical_action(
        "users",
        "deactivate_user",
        target_user=user,
        actor_email=actor_email,
        actor_id=actor_id,
        layer="service",
        db=db,
        payload={"reason": reason},
    )
    try:
        apply_guard(gr, db=db)
    except ZeusGuardViolation as exc:
        return {
            "success": False,
            "executed": False,
            "status": "blocked_by_guard",
            "reason": exc.result.reason,
            "human_message": exc.result.human_message,
        }

    if not gr.allowed:
        return {
            "success": False,
            "executed": False,
            "status": "blocked_by_guard",
            "reason": gr.reason,
            "human_message": gr.human_message,
            "guard": gr.to_dict(),
        }

    user.is_active = False
    from services.zeus_runtime_guard_v1 import clear_authorized_session, mark_authorized_session

    mark_authorized_session(db)
    try:
        db.flush()
    finally:
        clear_authorized_session(db)
    return {
        "success": True,
        "executed": True,
        "user_id": user.id,
        "email": user.email,
        "status": "inactive",
        "reason": reason,
        "guard": gr.to_dict(),
    }


def secure_update(
    db: Session,
    user: User,
    updates: Dict[str, Any],
    *,
    actor_email: Optional[str] = None,
    actor_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Actualización segura de usuario — intercepta is_active=false."""
    if updates.get("is_active") is False or updates.get("is_active") == 0:
        return secure_deactivate(
            db,
            user,
            reason=str(updates.get("reason") or "admin_update"),
            actor_email=actor_email,
            actor_id=actor_id,
        )

    allowed_fields = {
        "full_name",
        "phone",
        "company_name",
        "plan",
        "employees",
        "role",
        "is_active",
    }
    applied: Dict[str, Any] = {}
    for key, val in updates.items():
        if key not in allowed_fields:
            continue
        if key == "is_active" and val is True:
            user.is_active = True
            applied[key] = val
        elif key != "is_active":
            setattr(user, key, val)
            applied[key] = val

    db.flush()
    return {"success": True, "user_id": user.id, "applied": applied}
