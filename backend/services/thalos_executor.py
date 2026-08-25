"""THALOS v1 — executor con feature flags y salvaguardas."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.thalos_security_event import ThalosSecurityEvent
from app.models.user import User
from services import thalos_backup_service, thalos_security_engine
from services.activity_logger import ActivityLogger

logger = logging.getLogger(__name__)


def _log_action(
    db: Session,
    *,
    action: str,
    status: str,
    details: Dict[str, Any],
    company_id: Optional[int] = None,
) -> None:
    if company_id is not None:
        details = {**details, "company_id": company_id}
    ActivityLogger.log_activity(
        agent_name="THALOS",
        action_type=f"thalos_v1_{action}",
        action_description=f"THALOS v1 {action}: {status}",
        details=details,
        status=status if status in ("completed", "failed", "pending") else "completed",
        priority="critical" if action == "block_user" else "high",
    )
    db.add(
        ThalosSecurityEvent(
            event_type=f"action_{action}",
            severity="info" if status == "completed" else "warning",
            source="thalos_executor",
            company_id=company_id,
            details_json=json.dumps(details, ensure_ascii=False),
            action_taken=action,
        )
    )
    db.flush()


def _disabled(action: str) -> Dict[str, Any]:
    return {
        "status": "skipped",
        "action": action,
        "reason": "THALOS_EXECUTION_ENABLED is false",
        "executed": False,
    }


def block_user(
    db: Session,
    *,
    user_email: str,
    reason: str = "thalos_security",
    company_id: Optional[int] = None,
) -> Dict[str, Any]:
    email = (user_email or "").strip().lower()

    # Aislamiento multi-tenant: si se conoce el company_id del solicitante
    # (siempre lo conocen las dos vías reales que llaman a esta función:
    # thalos_v1.py::thalos_v1_execute y ThalosAgent._block, ambas resuelven
    # el tenant del usuario autenticado antes de invocar el bloqueo), el
    # usuario objetivo (`user_email`) debe pertenecer a una empresa de ese
    # company_id. Sin este chequeo, cualquier tenant autenticado podía pedir
    # el bloqueo de la cuenta de OTRO tenant con solo conocer su email (ver
    # AUDIT_FIX_THALOS_SHIELD.md, sección 6, hallazgo ALTO #2). Se comprueba
    # antes de revelar nada sobre el usuario objetivo (protegido, existencia,
    # superusuario) para no habilitar enumeración cross-tenant. Si no se
    # conoce company_id (llamadas internas/tests de bajo nivel sin contexto
    # de tenant), se preserva el comportamiento previo: no se puede validar
    # lo que no se conoce.
    if company_id is not None:
        from app.models.company import UserCompany

        target_belongs = (
            db.query(UserCompany)
            .join(User, User.id == UserCompany.user_id)
            .filter(func.lower(User.email) == email, UserCompany.company_id == company_id)
            .first()
        )
        if not target_belongs:
            result = {
                "status": "forbidden",
                "action": "block_user",
                "email": email,
                "executed": False,
                "reason": "target_user_not_in_requester_company",
            }
            _log_action(db, action="block_user", status="forbidden", details=result, company_id=company_id)
            logger.warning(
                "THALOS.BLOCK rechazado por aislamiento multi-tenant: email=%s no pertenece a company_id=%s",
                email,
                company_id,
            )
            return result

    if email in thalos_security_engine.PROTECTED_EMAILS:
        result = {
            "status": "blocked_by_safeguard",
            "action": "block_user",
            "email": email,
            "executed": False,
            "reason": "protected_user",
        }
        _log_action(db, action="block_user", status="safeguard", details=result, company_id=company_id)
        return result

    if not settings.THALOS_AUTO_BLOCK:
        result = {
            "status": "dry_run",
            "action": "block_user",
            "email": email,
            "executed": False,
            "reason": "THALOS_AUTO_BLOCK is false",
        }
        _log_action(db, action="block_user", status="dry_run", details=result, company_id=company_id)
        return result

    user = db.query(User).filter(func.lower(User.email) == email).first()
    if not user:
        result = {"status": "not_found", "action": "block_user", "email": email, "executed": False}
        _log_action(db, action="block_user", status="not_found", details=result, company_id=company_id)
        return result

    if user.is_superuser:
        result = {
            "status": "blocked_by_safeguard",
            "action": "block_user",
            "email": email,
            "executed": False,
            "reason": "superuser",
        }
        _log_action(db, action="block_user", status="safeguard", details=result, company_id=company_id)
        return result

    from services.user_service_v1 import secure_deactivate

    secured = secure_deactivate(db, user, reason=reason, actor_id=None)
    if not secured.get("executed"):
        result = {
            "status": secured.get("status", "blocked_by_guard"),
            "action": "block_user",
            "email": email,
            "executed": False,
            "reason": secured.get("reason", "guard"),
            "human_message": secured.get("human_message"),
            "guard": secured.get("guard"),
        }
        _log_action(db, action="block_user", status="guard", details=result, company_id=company_id)
        return result

    result = {
        "status": "completed",
        "action": "block_user",
        "email": email,
        "user_id": user.id,
        "executed": True,
        "reason": reason,
    }
    _log_action(db, action="block_user", status="completed", details=result, company_id=company_id)
    return result


def alert_admin(
    db: Session,
    *,
    message: str,
    severity: str = "high",
    company_id: Optional[int] = None,
) -> Dict[str, Any]:
    result = {
        "status": "completed",
        "action": "alert_admin",
        "message": message,
        "severity": severity,
        "executed": True,
        "channels": ["activity_log"],
    }
    _log_action(db, action="alert_admin", status="completed", details=result, company_id=company_id)
    logger.warning("[THALOS] alert_admin: %s", message)
    return result


def execute_action(
    db: Session,
    action: str,
    *,
    company_id: Optional[int] = None,
    user_id: Optional[int] = None,
    user_email: Optional[str] = None,
    ip_address: Optional[str] = None,
    hours: int = 24,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Puente de ejecución: solo actúa si THALOS_EXECUTION_ENABLED=true."""
    payload = payload or {}
    if not settings.THALOS_EXECUTION_ENABLED:
        return _disabled(action)

    result: Dict[str, Any]
    if action == "detect_suspicious_activity":
        scan = thalos_security_engine.scan_logs(db, hours=hours, company_id=company_id)
        _log_action(db, action=action, status="completed", details=scan, company_id=company_id)
        result = {"status": "completed", "action": action, "executed": True, "result": scan}
    elif action == "audit_cashflow_anomaly":
        cid = company_id or payload.get("company_id")
        if not cid:
            return {"status": "error", "action": action, "executed": False, "reason": "company_id required"}
        cf = thalos_security_engine.detect_cashflow_anomaly(db, company_id=int(cid))
        _log_action(db, action=action, status="completed", details=cf, company_id=int(cid))
        result = {"status": "completed", "action": action, "executed": True, "result": cf}
    elif action == "trigger_backup":
        bk = thalos_backup_service.create_backup()
        _log_action(db, action=action, status="completed", details=bk, company_id=company_id)
        result = {"status": "completed", "action": action, "executed": True, "result": bk}
    elif action == "block_user":
        email = user_email or payload.get("email") or payload.get("user_email")
        if not email:
            return {"status": "error", "action": action, "executed": False, "reason": "user_email required"}
        return block_user(db, user_email=str(email), company_id=company_id)
    elif action == "alert_admin":
        msg = payload.get("message") or "THALOS security alert"
        result = alert_admin(db, message=str(msg), severity=payload.get("severity", "high"), company_id=company_id)
    else:
        return {"status": "error", "action": action, "executed": False, "reason": "unknown_action"}

    if user_id:
        from services.thalos_workspace_writer_v1 import write_from_action_result

        write_from_action_result(
            db,
            user_id=user_id,
            company_id=company_id,
            action=action,
            result=result,
        )
    return result
