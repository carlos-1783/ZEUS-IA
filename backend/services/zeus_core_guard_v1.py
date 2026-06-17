"""
ZEUS Core Guard v1 — capa de control global (zeus_total_system_closure_v1).

Non-destructive: con flags desactivados solo audita; con enforce activo bloquea bypass.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from services.thalos_security_engine import PROTECTED_EMAILS

logger = logging.getLogger(__name__)

CRITICAL_DOMAINS = frozenset({"users", "payments", "invoices", "cashflow", "crm", "agents"})

DESTRUCTIVE_USER_ACTIONS = frozenset(
    {
        "block_user",
        "deactivate_user",
        "delete_user",
        "user_deactivate",
        "user_delete",
    }
)

SIMULATED_HANDLER_ACTIONS = frozenset(
    {
        "image_analyzer",
        "ads_campaign_builder",
        "autonomo_paperwork_prepare",
        "invoice_sent",
        "contract_generator",
        "contract_creator_rrhh",
    }
)


class ZeusGuardViolation(Exception):
    """Acción crítica bloqueada por zeus_core_guard."""

    def __init__(self, message: str, *, result: Optional["GuardResult"] = None):
        super().__init__(message)
        self.result = result


@dataclass
class GuardResult:
    allowed: bool
    domain: str
    action: str
    reason: str
    execution_mode: str = "real"
    human_message: str = ""
    enforced: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "domain": self.domain,
            "action": self.action,
            "reason": self.reason,
            "execution_mode": self.execution_mode,
            "human_message": self.human_message,
            "enforced": self.enforced,
        }


def closure_active() -> bool:
    return bool(getattr(settings, "ZEUS_TOTAL_SYSTEM_CLOSURE_ENABLED", False))


def guard_enforce() -> bool:
    return closure_active() and bool(getattr(settings, "ZEUS_CORE_GUARD_ENFORCE", False))


def is_protected_user(
    user: Optional[User] = None,
    *,
    email: Optional[str] = None,
) -> bool:
    em = (email or (user.email if user else "") or "").strip().lower()
    if em in PROTECTED_EMAILS:
        return True
    if user is not None:
        if getattr(user, "is_superuser", False):
            return True
        if (getattr(user, "role", "") or "").strip().lower() == "superuser":
            return True
    return False


def _human_message(domain: str, action: str, reason: str, allowed: bool) -> str:
    verb = "permitida" if allowed else "bloqueada"
    return f"Acción {verb}: [{domain}] {action} — {reason}"


def _persist_audit(
    db: Optional[Session],
    *,
    layer: str,
    domain: str,
    action: str,
    result: GuardResult,
    actor_id: Optional[str] = None,
    actor_email: Optional[str] = None,
    target_id: Optional[str] = None,
    company_id: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    if not closure_active():
        return
    try:
        from app.models.zeus_closure_audit import ZeusClosureAudit

        row = ZeusClosureAudit(
            layer=layer,
            domain=domain,
            action=action,
            actor_id=actor_id,
            actor_email=actor_email,
            target_id=target_id,
            company_id=company_id,
            result="allowed" if result.allowed else ("rejected" if result.enforced else "observed"),
            execution_mode=result.execution_mode,
            human_message=result.human_message,
            details_json=json.dumps(details or result.to_dict(), ensure_ascii=False),
        )
        if db is not None:
            db.add(row)
            db.flush()
        else:
            from app.db.session import SessionLocal

            s = SessionLocal()
            try:
                s.add(row)
                s.commit()
            finally:
                s.close()
    except Exception:
        logger.exception("zeus_closure_audit persist failed")


def validate_critical_action(
    domain: str,
    action: str,
    *,
    target_user: Optional[User] = None,
    target_email: Optional[str] = None,
    company_id: Optional[int] = None,
    actor_id: Optional[Union[int, str]] = None,
    actor_email: Optional[str] = None,
    layer: str = "service",
    db: Optional[Session] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> GuardResult:
    """Valida permisos, company_id y reglas de negocio para acciones críticas."""
    domain_n = (domain or "").strip().lower()
    action_n = (action or "").strip().lower()
    enforced = guard_enforce()

    if domain_n not in CRITICAL_DOMAINS:
        result = GuardResult(
            allowed=True,
            domain=domain_n,
            action=action_n,
            reason="non_critical_domain",
            human_message=_human_message(domain_n, action_n, "dominio no crítico", True),
            enforced=enforced,
        )
        return result

    if action_n in SIMULATED_HANDLER_ACTIONS:
        result = GuardResult(
            allowed=True,
            domain=domain_n,
            action=action_n,
            reason="simulated_handler",
            execution_mode="simulated",
            human_message="Acción simulada — no puede mutar datos reales",
            enforced=enforced,
        )
        _persist_audit(
            db,
            layer=layer,
            domain=domain_n,
            action=action_n,
            result=result,
            actor_id=str(actor_id) if actor_id is not None else None,
            actor_email=actor_email,
            company_id=company_id,
        )
        return result

    if action_n in DESTRUCTIVE_USER_ACTIONS or action_n == "block_user":
        if is_protected_user(target_user, email=target_email):
            result = GuardResult(
                allowed=False,
                domain=domain_n,
                action=action_n,
                reason="protected_user_or_superuser",
                human_message=_human_message(
                    domain_n, action_n, "usuario protegido o superusuario", False
                ),
                enforced=enforced,
            )
            _persist_audit(
                db,
                layer=layer,
                domain=domain_n,
                action=action_n,
                result=result,
                actor_id=str(actor_id) if actor_id is not None else None,
                actor_email=actor_email,
                target_id=str(target_user.id) if target_user else target_email,
                company_id=company_id,
            )
            return result

    if domain_n in ("payments", "invoices", "cashflow", "crm") and company_id is None:
        if closure_active():
            result = GuardResult(
                allowed=False,
                domain=domain_n,
                action=action_n,
                reason="company_id_required",
                human_message=_human_message(domain_n, action_n, "company_id obligatorio", False),
                enforced=enforced,
            )
            _persist_audit(
                db,
                layer=layer,
                domain=domain_n,
                action=action_n,
                result=result,
                actor_id=str(actor_id) if actor_id is not None else None,
                actor_email=actor_email,
                company_id=company_id,
                details=payload,
            )
            return result

    result = GuardResult(
        allowed=True,
        domain=domain_n,
        action=action_n,
        reason="ok",
        human_message=_human_message(domain_n, action_n, "validación OK", True),
        enforced=enforced,
    )
    if closure_active():
        _persist_audit(
            db,
            layer=layer,
            domain=domain_n,
            action=action_n,
            result=result,
            actor_id=str(actor_id) if actor_id is not None else None,
            actor_email=actor_email,
            company_id=company_id,
        )
    return result


def apply_guard(
    result: GuardResult,
    *,
    db: Optional[Session] = None,
) -> GuardResult:
    """Si enforce activo y no permitido → excepción; si no, solo observa."""
    if result.allowed or not result.enforced:
        if not result.allowed:
            logger.warning("[ZEUS_GUARD] observed violation: %s", result.human_message)
        return result
    raise ZeusGuardViolation(result.human_message, result=result)


def validate_event_emit(
    event_name: str,
    *,
    company_id: Optional[int],
    user_id: Optional[int] = None,
    user_email: Optional[str] = None,
    destructive: bool = False,
    db: Optional[Session] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> GuardResult:
    """Validación previa a emisión en event_bus."""
    domain = "payments" if "payment" in event_name else "cashflow"
    if "invoice" in event_name:
        domain = "invoices"
    if "client" in event_name:
        domain = "crm"
    action = f"emit_{event_name}"
    if destructive:
        gr = validate_critical_action(
            "users",
            "block_user",
            company_id=company_id,
            actor_id=user_id,
            actor_email=user_email,
            layer="event_bus",
            db=db,
            payload=payload,
        )
    else:
        gr = validate_critical_action(
            domain,
            action,
            company_id=company_id,
            actor_id=user_id,
            actor_email=user_email,
            layer="event_bus",
            db=db,
            payload=payload,
        )
    return gr