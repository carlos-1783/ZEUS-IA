"""
ZEUS Core — orquestador central: intent → action → ejecución multi-módulo.

Módulos: CRM, PERSEO (marketing), TPV, control horario, analytics, activity log.
Toda acción operativa pasa por aquí; el chat no invoca agentes directamente.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.zeus_pending_approval import ZeusPendingApproval
from app.schemas.zeus_action import ZeusAction
from app.schemas.zeus_task import ZeusExecutionResult
from services.agent_memory_service import load as memory_load, persist_operational_state
from services.intent_parser_service import (
    build_action,
    is_affirmative_message,
    is_cancel_message,
    is_confirmation_message,
    looks_like_operational,
    parse_message,
)
from services.zeus_global_context import attach_context_to_action_payload, enrich_chat_context
from services.zeus_human_approval_v1 import (
    CHAT_APPROVAL_TTL_SECONDS,
    execute_approval,
    is_expired,
    request_approval,
    resolve_approval,
)
from services import zeus_orchestrator_handlers as handlers

logger = logging.getLogger(__name__)

PENDING_ACTION_KEY = "pending_zeus_action"
LEGACY_PENDING_KEY = "pending_zeus_task"
AGENT_ZEUS = "ZEUS CORE"
MIN_CONFIDENCE = 0.7
PENDING_TTL_SECONDS = CHAT_APPROVAL_TTL_SECONDS
# Acciones con consecuencias (envían emails / crean datos): exigen vista previa + confirmación.
CONFIRMABLE_ACTIONS = frozenset({"send_campaign", "create_customer"})

_OPERATIONAL_HELP = (
    "No pude ejecutar esa acción. Prueba con frases concretas, por ejemplo:\n"
    "• «¿cuántos clientes tengo?»\n"
    "• «envía oferta 5% a clientes» (luego «confirmar»)\n"
    "• «qué ventas hicimos hoy»\n"
    "• «¿tengo turno activo?»\n"
    "• «resumen de actividad últimos 30 días»"
)


def _company_key(user: User, context: Optional[Dict[str, Any]]) -> str:
    """Clave de empresa para la memoria de ZEUS.

    H-01: sale SOLO del contexto construido por el servidor (`zeus_global_context`), nunca de
    un `company_id` que envíe el cliente. El respaldo para usuarios sin empresa lleva prefijo
    para que jamás coincida con el id de una empresa real (antes `str(user.id)` podía
    colisionar con `str(company_id)`).
    """
    gc = (context or {}).get("zeus_global_context") or {}
    if gc.get("company_id"):
        return str(gc["company_id"])
    return f"user:{user.id}"


def _thread_id(context: Optional[Dict[str, Any]]) -> str:
    return str((context or {}).get("thread_id") or "main")


def _pending_thread_key(user: User, context: Optional[Dict[str, Any]]) -> str:
    """Hilo bajo el que se guarda la solicitud: atado al usuario que la pidió.

    H-01: antes el pending se indexaba solo por (empresa, hilo), así que cualquier usuario que
    escribiera «confirmar» en ese hilo ejecutaba la acción de otro. La columna `thread_id` es
    String(128): se recorta la parte del cliente para dejar sitio al sufijo.
    """
    return f"{_thread_id(context)[:100]}:u{user.id}"


def _discard_legacy_pending(company_id: str, thread_id: str) -> None:
    """J3b: el único estado de confirmación es zeus_pending_approvals. Un pending legado en
    AgentOperationalState (versiones previas) jamás se ejecuta: se descarta si existe."""
    mem = memory_load(company_id, AGENT_ZEUS, thread_id)
    artifacts = (mem.get("operational") or {}).get("artifacts") or {}
    if artifacts.get(PENDING_ACTION_KEY) or artifacts.get(LEGACY_PENDING_KEY):
        persist_operational_state(
            company_id,
            AGENT_ZEUS,
            thread_id,
            current_task=None,
            status="idle",
            next_action=None,
            artifacts={},
            blocked=None,
        )


def _find_chat_pending(
    db: Session, company_id: Optional[int], user: User, thread_key: str
) -> Optional[ZeusPendingApproval]:
    """Solicitud pending más reciente del MISMO usuario, empresa e hilo de chat."""
    if company_id is None:
        return None
    return (
        db.query(ZeusPendingApproval)
        .filter(
            ZeusPendingApproval.company_id == company_id,
            ZeusPendingApproval.user_id == user.id,
            ZeusPendingApproval.thread_id == thread_key,
            ZeusPendingApproval.status == "pending",
        )
        .order_by(ZeusPendingApproval.id.desc())
        .first()
    )


def _reject_pending(db: Session, user: User, row: ZeusPendingApproval, reason: str) -> None:
    approval_id = row.id
    try:
        resolve_approval(db, approval_id=approval_id, user=user, approve=False, reason=reason)
    except HTTPException as exc:
        # 409: otro worker o la barra del workspace ya la resolvió; nada que hacer.
        logger.info("zeus_chat_reject_skipped approval=%s status=%s", approval_id, exc.status_code)
    except Exception:
        db.rollback()
        logger.exception("No se pudo rechazar la aprobacion %s (%s)", approval_id, reason)


def _clean_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in (payload or {}).items() if not str(k).startswith("_")}


async def _confirm_pending(db: Session, user: User, row: ZeusPendingApproval) -> Dict[str, Any]:
    """Resuelve (pending→approved, atómico) y ejecuta (approved→executing→executed|failed)."""
    fail = {"handled": True, "success": False, "executed": False}
    approval_id = row.id
    try:
        resolved = resolve_approval(db, approval_id=approval_id, user=user, approve=True)
    except HTTPException as exc:
        db.rollback()
        if exc.status_code == 403:
            return {**fail, "message": f"No tienes permiso para confirmar esta acción: {exc.detail}"}
        if "caducada" in str(exc.detail):
            return {**fail, "message": "La confirmación caducó (15 min). Describe de nuevo la acción."}
        return {**fail, "message": "Esa acción ya fue resuelta; no se ejecuta de nuevo."}
    except Exception:
        db.rollback()
        logger.exception("zeus_chat: fallo al aprobar %s; no se ejecuta nada", approval_id)
        return {
            **fail,
            "message": "No se pudo registrar tu confirmación. No se ha ejecutado nada; inténtalo de nuevo.",
        }

    try:
        done = await execute_approval(db, row=resolved, user=user)
    except HTTPException:
        db.rollback()
        return {**fail, "message": "Esa acción ya está en ejecución o ejecutada; no se ejecuta de nuevo."}
    except Exception:
        db.rollback()
        logger.exception("zeus_chat: fallo ejecutando aprobacion %s", approval_id)
        return {**fail, "message": "Error al ejecutar la acción confirmada."}

    outcome = json.loads(done.result_json or "{}")
    logger.info(
        "zeus_chat_confirmed_execution user=%s company=%s action=%s approval=%s status=%s",
        user.id, done.company_id, done.action_type, done.id, done.status,
    )
    if done.status == "executed":
        result = outcome.get("result") or {}
        return {
            "handled": True,
            "success": True,
            "executed": True,
            "approval_id": done.id,
            "message": result.get("message") or "Acción ejecutada.",
            "execution": result,
        }
    return {
        **fail,
        "approval_id": done.id,
        "message": f"No se pudo ejecutar la acción: {outcome.get('error') or 'error desconocido'}",
        "execution": outcome.get("result"),
    }


def _preview_create_customer(action: ZeusAction) -> Optional[Dict[str, Any]]:
    name = str(action.payload.get("name") or "").strip()
    email = str(action.payload.get("email") or "").strip()
    if not name or not email:
        return None  # faltan datos: execute_action responde pidiéndolos, sin crear nada
    return {
        "message": f"Voy a crear el cliente «{name}» ({email}). Responde «confirmar» para crearlo.",
        "name": name,
        "email": email,
    }


def _with_global_context(action: ZeusAction, global_context: Dict[str, Any]) -> ZeusAction:
    action.payload = attach_context_to_action_payload(action.payload, global_context)
    if action.company_id is None and global_context.get("company_id"):
        action.company_id = global_context["company_id"]
    return action


def _to_chat_payload(result: ZeusExecutionResult) -> Dict[str, Any]:
    return {
        "handled": True,
        "success": result.success,
        "message": result.message,
        "executed": result.executed,
        "needs_confirmation": result.needs_confirmation,
        "execution": result.model_dump(),
    }


async def execute_action(
    db: Session,
    user: User,
    action: ZeusAction,
    *,
    force_execute: bool = False,
) -> ZeusExecutionResult:
    """Ejecuta una ZeusAction en los módulos indicados."""
    at = action.action_type

    if at == "list_customers":
        return handlers.execute_list_customers(db, user, action)

    if at == "send_campaign":
        if action.requires_confirmation and not force_execute:
            preview = handlers.preview_send_campaign(db, user, action)
            return ZeusExecutionResult(
                success=True,
                intent="create_campaign_send",
                message=preview["message"],
                executed=False,
                needs_confirmation=True,
                metrics={
                    "customer_count": preview.get("customer_count"),
                    "will_send": preview.get("will_send"),
                },
            )
        return await handlers.execute_send_campaign(db, user, action)

    if at == "analytics_summary":
        return handlers.execute_analytics_summary(db, user, action)

    if at == "tpv_sales_summary":
        return handlers.execute_tpv_sales_summary(db, user, action)

    if at == "shift_status":
        return handlers.execute_shift_status(db, user, action)

    if at == "create_customer":
        return handlers.execute_create_customer(db, user, action)

    if at == "get_cashflow":
        return handlers.execute_get_cashflow(db, user, action)

    if at == "get_metrics":
        return handlers.execute_get_core_metrics(db, user, action)

    return ZeusExecutionResult(
        success=False,
        intent="unknown",
        message="Acción no reconocida por el orquestador.",
        executed=False,
    )


async def try_handle_zeus_chat(
    db: Session,
    user: User,
    message: str,
    context: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Si el mensaje dispara una acción ejecutable, devuelve respuesta estructurada.
    Si no, devuelve None (continuar con LLM solo para consultas no operativas).

    J3/J3b: la ejecución de acciones con consecuencias (enviar campaña, crear cliente) SOLO
    ocurre cuando el mismo usuario, en el mismo hilo y empresa, confirma explícitamente una
    fila vigente de zeus_pending_approvals (único estado de confirmación, compartido con la
    barra de decisión del workspace). Ningún flag del cliente (force_execute, confirm_action,
    skip_action_execution) influye: este módulo no los lee.
    """
    ctx = enrich_chat_context(db, user, context)
    global_context = ctx["zeus_global_context"]
    company_id = _company_key(user, ctx)
    thread_id = _pending_thread_key(user, ctx)
    company_int = global_context.get("company_id")

    _discard_legacy_pending(company_id, thread_id)

    pending_row = _find_chat_pending(db, company_int, user, thread_id)
    expired_notice = False
    if pending_row is not None and is_expired(pending_row):
        _reject_pending(db, user, pending_row, "caducada")
        pending_row, expired_notice = None, True

    explicit = is_confirmation_message(message)
    affirmative = is_affirmative_message(message)

    if pending_row is not None:
        if explicit or affirmative:
            return await _confirm_pending(db, user, pending_row)
        if is_cancel_message(message):
            cancelled_id = pending_row.id
            _reject_pending(db, user, pending_row, "cancelado por el usuario")
            return {
                "handled": True,
                "success": True,
                "executed": False,
                "approval_id": cancelled_id,
                "message": "Acción cancelada. No se ha ejecutado nada.",
            }
        # Cambio de tema: se rechaza la solicitud para que la barra de decisión del workspace
        # no muestre algo que el chat ya abandonó.
        _reject_pending(db, user, pending_row, "cambio de tema")
    elif explicit:
        return {
            "handled": True,
            "success": False,
            "executed": False,
            "message": (
                "La confirmación caducó (15 min). Describe de nuevo lo que quieres hacer."
                if expired_notice
                else "No hay ninguna acción pendiente de confirmar. Describe lo que quieres hacer."
            ),
        }

    task = parse_message(message)
    if task.intent == "unknown" or task.confidence < MIN_CONFIDENCE:
        if looks_like_operational(message):
            return {
                "handled": True,
                "success": False,
                "executed": False,
                "message": _OPERATIONAL_HELP,
            }
        return None

    action = _with_global_context(build_action(db, user, task), global_context)

    if action.action_type in CONFIRMABLE_ACTIONS:
        action.requires_confirmation = True
        if action.action_type == "send_campaign":
            preview = handlers.preview_send_campaign(db, user, action)
        else:
            preview = _preview_create_customer(action)
            if preview is None:
                return _to_chat_payload(await execute_action(db, user, action, force_execute=False))
        refusal = {"handled": True, "success": False, "executed": False}
        try:
            row = request_approval(
                db,
                user=user,
                company_id=company_int,
                agent_name="ZEUS",
                action_type=action.action_type,
                payload=_clean_payload(action.payload),
                thread_id=thread_id,
                ttl_seconds=PENDING_TTL_SECONDS,
            )
        except HTTPException as exc:
            db.rollback()
            if exc.status_code == 403:
                return {**refusal, "message": f"No tienes permiso para esta acción: {exc.detail}"}
            return {**refusal, "message": str(exc.detail)}
        except Exception:
            db.rollback()
            logger.exception("zeus_chat: no se pudo persistir la solicitud; no se ejecuta nada")
            return {
                **refusal,
                "message": (
                    "No se pudo registrar la solicitud de confirmación. "
                    "No se ha ejecutado nada; inténtalo de nuevo."
                ),
            }
        return {
            "handled": True,
            "success": True,
            "executed": False,
            "needs_confirmation": True,
            "approval_id": row.id,
            "message": preview["message"],
            "execution": preview,
            "action": {**action.model_dump(), "payload": _clean_payload(action.payload)},
        }

    result = await execute_action(db, user, action, force_execute=False)
    return _to_chat_payload(result)


__all__ = ["try_handle_zeus_chat", "execute_action", "AGENT_ZEUS", "enrich_chat_context"]
