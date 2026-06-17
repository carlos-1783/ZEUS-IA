"""
Runtime guard zeus_phase_2 — detecta mutaciones fuera de capas de servicio.

Se registra en Session.before_flush cuando ZEUS_TOTAL_SYSTEM_CLOSURE_ENABLED=true.
"""

from __future__ import annotations

import json
import logging
import traceback
from typing import Any, Dict, Optional, Set

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_registered = False
_guard_depth: Set[int] = set()  # session id() en mutación autorizada


def mark_authorized_session(session: Session) -> None:
    """Marcar sesión como autorizada para mutación (llamado desde services)."""
    _guard_depth.add(id(session))


def clear_authorized_session(session: Session) -> None:
    _guard_depth.discard(id(session))


def _log_runtime_violation(
    *,
    violation_type: str,
    details: Dict[str, Any],
    session: Session,
    enforced: bool,
) -> None:
    stack = traceback.format_stack(limit=12)
    payload = {**details, "stack_trace": stack[-8:]}
    logger.warning("[RUNTIME_GUARD] %s enforced=%s %s", violation_type, enforced, details)

    try:
        from app.models.zeus_closure_audit import ZeusClosureAudit

        row = ZeusClosureAudit(
            layer="runtime",
            domain=details.get("domain", "unknown"),
            action=violation_type,
            target_id=str(details.get("target_id", "")),
            company_id=details.get("company_id"),
            result="rejected" if enforced else "observed",
            execution_mode="real",
            human_message=details.get("message", violation_type),
            details_json=json.dumps(payload, ensure_ascii=False)[:4000],
        )
        session.add(row)
    except Exception:
        logger.exception("runtime violation audit failed")


def _before_flush(session: Session, flush_context, instances) -> None:
    from app.core.config import settings
    from services.zeus_core_guard_v1 import (
        ZeusGuardViolation,
        closure_active,
        guard_enforce,
        is_protected_user,
    )

    if not closure_active():
        return

    if id(session) in _guard_depth:
        return

    enforced = guard_enforce()

    for obj in session.dirty:
        cls_name = type(obj).__name__

        if cls_name == "User":
            attr = inspect(obj).attrs.is_active
            if attr.history.has_changes() and obj.is_active is False:
                if is_protected_user(obj):
                    msg = f"Runtime: intento desactivar usuario protegido id={obj.id}"
                    _log_runtime_violation(
                        violation_type="user_deactivate_bypass",
                        details={
                            "domain": "users",
                            "target_id": obj.id,
                            "email": obj.email,
                            "message": msg,
                        },
                        session=session,
                        enforced=enforced,
                    )
                    if enforced:
                        from services.zeus_core_guard_v1 import GuardResult

                        raise ZeusGuardViolation(
                            msg,
                            result=GuardResult(
                                allowed=False,
                                domain="users",
                                action="deactivate_user",
                                reason="protected_user_or_superuser",
                                human_message=msg,
                                enforced=True,
                            ),
                        )

        if cls_name == "CashflowLedgerEntry":
            cid = getattr(obj, "company_id", None)
            if cid is None:
                msg = "Runtime: cashflow sin company_id"
                _log_runtime_violation(
                    violation_type="financial_bypass",
                    details={"domain": "cashflow", "target_id": getattr(obj, "id", None), "message": msg},
                    session=session,
                    enforced=enforced,
                )
                if enforced:
                    from services.zeus_core_guard_v1 import GuardResult

                    raise ZeusGuardViolation(
                        msg,
                        result=GuardResult(
                            allowed=False,
                            domain="cashflow",
                            action="record_movement",
                            reason="company_id_required",
                            human_message=msg,
                            enforced=True,
                        ),
                    )

    for obj in session.deleted:
        if type(obj).__name__ == "User" and getattr(obj, "is_superuser", False):
            msg = f"Runtime: intento eliminar superuser id={obj.id}"
            _log_runtime_violation(
                violation_type="user_delete_bypass",
                details={"domain": "users", "target_id": obj.id, "message": msg},
                session=session,
                enforced=enforced,
            )
            if enforced:
                from services.zeus_core_guard_v1 import GuardResult

                raise ZeusGuardViolation(
                    msg,
                    result=GuardResult(
                        allowed=False,
                        domain="users",
                        action="delete_user",
                        reason="protected_user_or_superuser",
                        human_message=msg,
                        enforced=True,
                    ),
                )


def attach_runtime_guard() -> None:
    global _registered
    if _registered:
        return
    event.listen(Session, "before_flush", _before_flush, retval=False)
    _registered = True
    logger.info("[RUNTIME_GUARD] attached to Session.before_flush")


def detach_runtime_guard() -> None:
    global _registered
    if not _registered:
        return
    event.remove(Session, "before_flush", _before_flush)
    _registered = False
