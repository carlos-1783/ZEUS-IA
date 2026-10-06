"""
Capa de control humano v1 — acciones críticas requieren aprobación CEO/usuario.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.company import UserCompany
from app.models.zeus_pending_approval import ZeusPendingApproval
from app.models.user import User

CRITICAL_ACTIONS: Set[str] = frozenset({
    "send_campaign",
    "create_customer",
    "launch_campaign",
    "generate_invoice",
    "generate_model_303",
    "high_value_actions",
    "contract_generation",
    # J9c AFRODITA: escrituras operativas.
    "create_ops_route",
    "create_inventory_movement",
})

HIGH_VALUE_THRESHOLD_EUR = 500.0

# Rol minimo para PEDIR (y confirmar) cada accion; el resto usa "ceo" (owner/company_admin).
# send_campaign envia correos a terceros -> owner/company_admin.
# create_customer solo crea un registro de la propia empresa -> cualquier miembro.
# J9c: create_ops_route crea un registro de planificacion interno de la propia empresa, sin efecto
# externo ni sobre valor de existencias -> cualquier miembro. create_inventory_movement MODIFICA
# el stock (y el del TPV), que afecta a valoracion y compras -> owner/company_admin ("ceo").
ACTION_ROLE_REQUIRED: Dict[str, str] = {
    "send_campaign": "ceo",
    "create_customer": "member",
    "create_ops_route": "member",
    "create_inventory_movement": "ceo",
}
# Caducidad de las solicitudes nacidas en el chat.
CHAT_APPROVAL_TTL_SECONDS = 15 * 60


def role_required_for(action_type: str) -> str:
    return ACTION_ROLE_REQUIRED.get(action_type, "ceo")


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def is_expired(row: ZeusPendingApproval) -> bool:
    exp = _aware(row.expires_at)
    return exp is not None and datetime.now(timezone.utc) > exp

logger = logging.getLogger(__name__)

# UserCompany.role admite: owner | company_admin | member.
# role_required (por defecto "ceo") se mapea a los roles de empresa que pueden resolver.
# Criterio estricto: cualquier valor desconocido exige owner/company_admin.
_ROLE_MAP: Dict[str, Set[str]] = {
    "ceo": {"owner", "company_admin"},
    "owner": {"owner"},
    "admin": {"owner", "company_admin"},
    "company_admin": {"owner", "company_admin"},
    "member": {"owner", "company_admin", "member"},
}
_STRICT_ROLES = {"owner", "company_admin"}


def _is_superuser(user: User) -> bool:
    return bool(getattr(user, "is_superuser", False))


def user_company_role(db: Session, user: User, company_id: int) -> Optional[str]:
    """Rol del usuario en la empresa, o None si no pertenece."""
    uc = (
        db.query(UserCompany)
        .filter(UserCompany.user_id == user.id, UserCompany.company_id == company_id)
        .first()
    )
    return uc.role if uc else None


def assert_company_access(db: Session, user: User, company_id: int) -> None:
    """403 si el usuario no pertenece a la empresa (el superusuario es global)."""
    if _is_superuser(user):
        return
    if user_company_role(db, user, company_id) is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso a esta empresa")


def role_allows(role: Optional[str], role_required: Optional[str]) -> bool:
    allowed = _ROLE_MAP.get((role_required or "ceo").lower(), _STRICT_ROLES)
    return role in allowed


def _log(agent: str, action: str, desc: str, user: User, company_id: Optional[int], details: Dict[str, Any], st: str) -> None:
    """Registra aprobaciones/ejecuciones como pasos de la cadena JARVIS (J7): la ejecucion
    (approval_executed/failed/audit_failed) es ACTUAR; el resto, ORQUESTAR. Lleva el
    correlation_id de la peticion si existe; empresa y usuario explicitos."""
    try:
        from services.chain_log import log_chain_step

        step = "ACTUAR" if action in ("approval_executed", "approval_failed", "approval_audit_failed") else "ORQUESTAR"
        log_chain_step(
            step,
            company_id=company_id,
            user=user,
            agent=agent,
            action=action,
            action_type=action,
            description=desc,
            status=st,
            details=details,
            visible_to_client=True,
        )
    except Exception:
        logger.exception("No se pudo registrar actividad de aprobacion (%s)", action)


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
    company_id: Optional[int],
    agent_name: str,
    action_type: str,
    payload: Dict[str, Any],
    role_required: Optional[str] = None,
    thread_id: Optional[str] = None,
    ttl_seconds: Optional[int] = None,
) -> ZeusPendingApproval:
    role_required = role_required or role_required_for(action_type)
    if company_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede solicitar aprobacion: el usuario no tiene empresa asociada",
        )
    # Regla J2: solo el solicitante puede aprobar/ejecutar. Si el solicitante no
    # tiene el rol requerido nadie podria ejecutarla: se rechaza ya, sin crear fila.
    if not _is_superuser(user):
        role = user_company_role(db, user, company_id)
        if not role_allows(role, role_required):
            _log(
                agent_name, "approval_request_denied",
                f"Solicitud denegada por rol insuficiente: {action_type}",
                user, company_id,
                {"action_type": action_type, "user_role": role, "role_required": role_required},
                "failed",
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Tu rol no permite solicitar la accion {action_type} (requiere {role_required}).",
            )
    row = ZeusPendingApproval(
        company_id=company_id,
        user_id=user.id,
        agent_name=agent_name,
        action_type=action_type,
        payload_json=json.dumps(payload, ensure_ascii=False),
        status="pending",
        role_required=role_required,
        thread_id=thread_id,
        expires_at=(datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)) if ttl_seconds else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    _log(
        agent_name, "approval_requested",
        f"Aprobacion solicitada: {action_type} (ID {row.id})",
        user, company_id,
        {"approval_id": row.id, "action_type": action_type, "role_required": role_required},
        "pending",
    )
    return row


def list_pending(db: Session, *, user: User, company_id: int) -> List[Dict[str, Any]]:
    assert_company_access(db, user, company_id)
    rows = (
        db.query(ZeusPendingApproval)
        .filter(
            ZeusPendingApproval.company_id == company_id,
            ZeusPendingApproval.status == "pending",
        )
        .order_by(ZeusPendingApproval.created_at.desc())
        .all()
    )
    rows = [r for r in rows if not is_expired(r)]
    return [
        {
            "id": r.id,
            "agent_name": r.agent_name,
            "action_type": r.action_type,
            "payload": json.loads(r.payload_json or "{}"),
            "role_required": r.role_required,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "expires_at": r.expires_at.isoformat() if r.expires_at else None,
        }
        for r in rows
    ]


def resolve_approval(
    db: Session,
    *,
    approval_id: int,
    user: User,
    approve: bool,
    reason: Optional[str] = None,
) -> ZeusPendingApproval:
    """404 si no existe o es de otra empresa (sin revelar existencia); 403 si no
    puede resolver; 409 ya resuelta.

    - approve: solo el usuario que solicito la accion (row.user_id) y con el rol
      requerido. Ni el superusuario aprueba en nombre de otro.
    - reject: el solicitante, un owner/company_admin de la empresa o el superusuario.
    Solo transiciona estado (pending -> approved/rejected, UPDATE condicional
    atomico); la ejecucion la hace execute_approval()."""
    row = db.query(ZeusPendingApproval).filter(ZeusPendingApproval.id == approval_id).first()
    role = user_company_role(db, user, row.company_id) if row else None
    if not row or (role is None and not _is_superuser(user)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solicitud no encontrada")

    is_requester = row.user_id == user.id
    deny: Optional[str] = None
    if approve:
        if not is_requester:
            deny = "Solo quien solicito la accion puede confirmarla"
        elif not _is_superuser(user) and not role_allows(role, row.role_required):
            deny = "Rol insuficiente para resolver esta solicitud"
    else:
        if not (is_requester or _is_superuser(user) or role in _STRICT_ROLES):
            deny = "Sin permiso para rechazar esta solicitud"
    if deny:
        _log(
            row.agent_name, "approval_resolve_denied",
            f"Resolucion denegada (ID {row.id}): {deny}",
            user, row.company_id,
            {"approval_id": row.id, "user_role": role, "role_required": row.role_required,
             "requested_by_user_id": row.user_id, "approve": approve},
            "failed",
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=deny)

    expired = approve and is_expired(row)
    if expired:
        approve, reason = False, "caducada"
    new_status = "approved" if approve else "rejected"
    values: Dict[str, Any] = {
        "status": new_status,
        "resolved_at": datetime.now(timezone.utc),
        "resolved_by_user_id": user.id,
    }
    if not approve and reason:
        values["result_json"] = json.dumps({"reason": reason}, ensure_ascii=False)
    # UPDATE condicional atomico: evita doble resolucion concurrente.
    updated = (
        db.query(ZeusPendingApproval)
        .filter(ZeusPendingApproval.id == approval_id, ZeusPendingApproval.status == "pending")
        .update(values, synchronize_session=False)
    )
    db.commit()
    if not updated:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Solicitud ya resuelta")
    if expired:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Solicitud caducada")
    db.refresh(row)
    _log(
        row.agent_name, f"approval_{new_status}",
        f"Aprobacion {new_status}: {row.action_type} (ID {row.id})",
        user, row.company_id,
        {"approval_id": row.id, "action_type": row.action_type, "resolved_by_user_id": user.id},
        "completed",
    )
    return row


async def execute_approval(db: Session, *, row: ZeusPendingApproval, user: User) -> ZeusPendingApproval:
    """Ejecuta en el servidor la accion almacenada de una aprobacion ya aprobada.

    approved -> executing (UPDATE condicional: una sola ejecucion aunque lleguen
    dos peticiones) -> executed | failed. El resultado/error real queda en
    result_json. Se ejecuta como el usuario solicitante (ya verificado == user)."""
    from services.zeus_agent_executor_v1 import execute_agent_action
    import services.crm_office_service as crm_svc

    claimed = (
        db.query(ZeusPendingApproval)
        .filter(ZeusPendingApproval.id == row.id, ZeusPendingApproval.status == "approved")
        .update({"status": "executing"}, synchronize_session=False)
    )
    db.commit()
    if not claimed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Solicitud ya ejecutada o en ejecucion")

    final_status = "failed"
    outcome: Dict[str, Any]
    try:
        if row.user_id != user.id:
            raise RuntimeError("El ejecutor no es el usuario solicitante")
        if crm_svc.primary_company_id(db, user) != row.company_id:
            raise RuntimeError("La empresa de la aprobacion no coincide con la empresa activa del solicitante")
        result = await execute_agent_action(
            db,
            user=user,
            agent=row.agent_name,
            action=row.action_type,
            payload=json.loads(row.payload_json or "{}"),
            approval_id=row.id,
        )
        # THALOS (J5/J5b): auditoria post-accion. Sin veredicto OK no se declara "executed".
        from services.thalos_request_guard_v1 import record_security_event, thalos_audit_result

        really_executed = bool(isinstance(result, dict) and result.get("success") and result.get("executed"))
        try:
            audit = thalos_audit_result(
                db, user=user, company_id=row.company_id, agent=row.agent_name,
                action=row.action_type, result=result, approval_id=row.id,
            )
        except Exception as exc:
            if not really_executed:
                raise
            logger.exception("Fallo de la auditoria THALOS tras ejecutar la aprobacion %s", row.id)
            audit = {"ok": False, "reason": f"audit_error:{type(exc).__name__}"}
        if audit["ok"]:
            final_status = "executed"
            outcome = {"result": result, "audit": audit}
        elif really_executed:
            # La accion YA se ejecuto (efecto posiblemente producido) pero no se pudo verificar:
            # estado propio `audit_failed`, resultado conservado MARCADO como no verificado y
            # nunca devuelto al cliente (podria ser de otra empresa), evento critical.
            final_status = "audit_failed"
            outcome = {
                "unverified": True,
                "error": (
                    "La accion pudo producirse pero no se ha podido verificar "
                    f"(auditoria THALOS: {audit['reason']}). Se ha avisado al equipo de seguridad; "
                    "no la repitas hasta que se revise."
                ),
                "audit": audit,
                "unverified_result": result,
            }
            try:
                record_security_event(
                    db,
                    event_type="audit_failed_after_execution",
                    severity="critical",
                    source="zeus_human_approval",
                    details={
                        "approval_id": row.id, "agent": row.agent_name, "action": row.action_type,
                        "reason": audit["reason"], "executed": True, "verified": False,
                    },
                    user=user,
                    company_id=row.company_id,
                    action_taken="alert",
                    decision_rule=audit["reason"],
                )
            except Exception:
                logger.exception("No se pudo registrar el evento critical de audit_failed %s", row.id)
        else:
            outcome = {"error": result.get("message") or "La accion no se ejecuto", "result": result}
    except HTTPException as exc:
        db.rollback()
        outcome = {"error": str(exc.detail), "http_status": exc.status_code}
    except Exception as exc:  # error real: se registra como failed
        db.rollback()
        logger.exception("Fallo ejecutando aprobacion %s", row.id)
        outcome = {"error": f"{type(exc).__name__}: {exc}"}

    db.query(ZeusPendingApproval).filter(ZeusPendingApproval.id == row.id).update(
        {
            "status": final_status,
            "result_json": json.dumps(outcome, ensure_ascii=False, default=str),
            "executed_at": datetime.now(timezone.utc),
        },
        synchronize_session=False,
    )
    db.commit()
    db.refresh(row)
    _log(
        row.agent_name, f"approval_{final_status}",
        f"Aprobacion {final_status}: {row.action_type} (ID {row.id})",
        user, row.company_id,
        {"approval_id": row.id, "action_type": row.action_type,
         "error": outcome.get("error"), "executed_by_user_id": user.id},
        "completed" if final_status == "executed" else "failed",
    )
    return row
