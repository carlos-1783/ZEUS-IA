"""
ZEUS Core — orquestador central: intent → action → ejecución multi-módulo.

Módulos: CRM, PERSEO (marketing), TPV, control horario, analytics, activity log.
Toda acción operativa pasa por aquí; el chat no invoca agentes directamente.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.user import User
from pydantic import ValidationError

from app.schemas.zeus_action import ZeusAction
from app.schemas.zeus_task import ZeusExecutionResult, ZeusTaskObject
from services.agent_memory_service import load as memory_load, persist_operational_state
from services.intent_parser_service import (
    build_action,
    is_affirmative_message,
    is_confirmation_message,
    looks_like_operational,
    parse_message,
)
from services.zeus_global_context import attach_context_to_action_payload, enrich_chat_context
from services import zeus_orchestrator_handlers as handlers

logger = logging.getLogger(__name__)

PENDING_ACTION_KEY = "pending_zeus_action"
LEGACY_PENDING_KEY = "pending_zeus_task"
AGENT_ZEUS = "ZEUS CORE"
MIN_CONFIDENCE = 0.7
PENDING_TTL_SECONDS = 15 * 60
PENDING_AT_KEY = "_pending_at"
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
    """Clave de empresa para la memoria/pending de ZEUS.

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
    """Hilo bajo el que se guarda el pending: atado al usuario que lo solicitó.

    H-01: antes el pending se indexaba solo por (empresa, hilo), así que cualquier usuario que
    escribiera «confirmar» en ese hilo ejecutaba la acción de otro. La columna `thread_id` es
    String(128): se recorta la parte del cliente para dejar sitio al sufijo.
    """
    return f"{_thread_id(context)[:100]}:u{user.id}"


def _get_pending(company_id: str, thread_id: str) -> Optional[Dict[str, Any]]:
    mem = memory_load(company_id, AGENT_ZEUS, thread_id)
    artifacts = (mem.get("operational") or {}).get("artifacts") or {}
    pending = artifacts.get(PENDING_ACTION_KEY) or artifacts.get(LEGACY_PENDING_KEY)
    return pending if isinstance(pending, dict) else None


def _pending_expired(pending: Dict[str, Any]) -> bool:
    """Un pending sin marca temporal (legado) o más antiguo que el TTL no es ejecutable."""
    at = pending.get(PENDING_AT_KEY)
    if not isinstance(at, (int, float)):
        return True
    return (time.time() - at) > PENDING_TTL_SECONDS


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


def _pending_to_action(
    db: Session,
    user: User,
    pending_raw: Dict[str, Any],
    global_context: Dict[str, Any],
) -> ZeusAction:
    try:
        action = ZeusAction.model_validate(pending_raw)
    except ValidationError:
        task = ZeusTaskObject.model_validate(pending_raw)
        action = build_action(db, user, task)
    action.payload = attach_context_to_action_payload(action.payload, global_context)
    return action


def _set_pending(company_id: str, thread_id: str, action: Optional[ZeusAction]) -> None:
    if action is None:
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
        return
    persist_operational_state(
        company_id,
        AGENT_ZEUS,
        thread_id,
        current_task=action.action_type,
        status="awaiting_confirmation",
        next_action="Escribe «confirmar» para ejecutar",
        artifacts={PENDING_ACTION_KEY: {**action.model_dump(), PENDING_AT_KEY: time.time()}},
        blocked=None,
    )


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

    J3: la ejecución de acciones con consecuencias (enviar campaña, crear cliente) SOLO ocurre
    cuando el mismo usuario, en el mismo hilo y empresa, confirma explícitamente un pending
    persistido y vigente. Ningún flag del cliente (force_execute, confirm_action,
    skip_action_execution) influye: este módulo no los lee.
    """
    ctx = enrich_chat_context(db, user, context)
    global_context = ctx["zeus_global_context"]
    company_id = _company_key(user, ctx)
    thread_id = _pending_thread_key(user, ctx)

    pending_raw = _get_pending(company_id, thread_id)
    if pending_raw and _pending_expired(pending_raw):
        _set_pending(company_id, thread_id, None)
        pending_raw = None

    explicit = is_confirmation_message(message)
    affirmative = bool(pending_raw) and is_affirmative_message(message)

    if explicit or affirmative:
        if not pending_raw:
            return {
                "handled": True,
                "success": False,
                "message": "No hay ninguna acción pendiente de confirmar. Describe lo que quieres hacer.",
                "executed": False,
            }
        action = _pending_to_action(db, user, pending_raw, global_context)
        # El pending se consume ANTES de ejecutar: una sola ejecución por confirmación.
        _set_pending(company_id, thread_id, None)
        if action.action_type not in CONFIRMABLE_ACTIONS:
            return {
                "handled": True,
                "success": False,
                "executed": False,
                "message": "La acción pendiente no es válida. Describe de nuevo lo que quieres hacer.",
            }
        result = await execute_action(db, user, action, force_execute=True)
        logger.info(
            "zeus_chat_confirmed_execution user=%s company=%s action=%s success=%s",
            user.id, company_id, action.action_type, result.success,
        )
        return _to_chat_payload(result)

    if pending_raw:
        # Cambio de tema: cualquier mensaje que no confirma invalida el pending anterior.
        _set_pending(company_id, thread_id, None)

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
        _set_pending(company_id, thread_id, action)
        return {
            "handled": True,
            "success": True,
            "executed": False,
            "needs_confirmation": True,
            "message": preview["message"],
            "execution": preview,
            "action": action.model_dump(),
        }

    result = await execute_action(db, user, action, force_execute=False)
    return _to_chat_payload(result)


__all__ = ["try_handle_zeus_chat", "execute_action", "AGENT_ZEUS", "enrich_chat_context"]
