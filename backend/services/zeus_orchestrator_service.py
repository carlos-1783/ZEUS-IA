"""
ZEUS Core — orquestador central: intent → action → ejecución multi-módulo.

Módulos: CRM, PERSEO (marketing), TPV, control horario, analytics, activity log.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.user import User
from pydantic import ValidationError

from app.schemas.zeus_action import ZeusAction
from app.schemas.zeus_task import ZeusExecutionResult, ZeusTaskObject
from services.agent_memory_service import load as memory_load, persist_operational_state
from services.intent_parser_service import (
    build_action,
    is_confirmation_message,
    parse_message,
)
from services import zeus_orchestrator_handlers as handlers

logger = logging.getLogger(__name__)

PENDING_ACTION_KEY = "pending_zeus_action"
LEGACY_PENDING_KEY = "pending_zeus_task"
AGENT_ZEUS = "ZEUS CORE"
MIN_CONFIDENCE = 0.7


def _company_key(user: User, context: Optional[Dict[str, Any]]) -> str:
    if context and context.get("company_id"):
        return str(context["company_id"])
    return str(user.id)


def _thread_id(context: Optional[Dict[str, Any]]) -> str:
    return str((context or {}).get("thread_id") or "main")


def _get_pending(company_id: str, thread_id: str) -> Optional[Dict[str, Any]]:
    mem = memory_load(company_id, AGENT_ZEUS, thread_id)
    artifacts = (mem.get("operational") or {}).get("artifacts") or {}
    pending = artifacts.get(PENDING_ACTION_KEY) or artifacts.get(LEGACY_PENDING_KEY)
    return pending if isinstance(pending, dict) else None


def _pending_to_action(
    db: Session,
    user: User,
    pending_raw: Dict[str, Any],
) -> ZeusAction:
    try:
        return ZeusAction.model_validate(pending_raw)
    except ValidationError:
        task = ZeusTaskObject.model_validate(pending_raw)
        return build_action(db, user, task)


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
        artifacts={PENDING_ACTION_KEY: action.model_dump()},
        blocked=None,
    )


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
    *,
    force_execute: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Si el mensaje dispara una acción ejecutable, devuelve respuesta estructurada.
    Si no, devuelve None (continuar con LLM).
    """
    company_id = _company_key(user, context)
    thread_id = _thread_id(context)
    ctx = context or {}

    if ctx.get("skip_action_execution"):
        return None

    if is_confirmation_message(message) or force_execute:
        pending_raw = _get_pending(company_id, thread_id)
        if pending_raw:
            action = _pending_to_action(db, user, pending_raw)
            result = await execute_action(db, user, action, force_execute=True)
            _set_pending(company_id, thread_id, None)
            return _to_chat_payload(result)
        if is_confirmation_message(message) and not pending_raw:
            return {
                "handled": True,
                "success": False,
                "message": "No hay ninguna acción pendiente de confirmar. Describe lo que quieres hacer.",
                "executed": False,
            }

    task = parse_message(message)
    if task.intent == "unknown" or task.confidence < MIN_CONFIDENCE:
        return None

    action = build_action(db, user, task)

    if action.requires_confirmation and not force_execute and action.action_type == "send_campaign":
        preview = handlers.preview_send_campaign(db, user, action)
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

    result = await execute_action(db, user, action, force_execute=force_execute)
    return _to_chat_payload(result)


__all__ = ["try_handle_zeus_chat", "execute_action", "AGENT_ZEUS"]
