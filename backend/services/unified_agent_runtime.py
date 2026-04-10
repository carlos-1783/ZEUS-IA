"""
Unified agent runtime: one execution loop for chat and workspace.
Load memory -> Evaluate -> Decide -> Execute -> Persist.
NO_RESPONSE_WITHOUT_MEMORY_WRITE.
"""

from __future__ import annotations

import concurrent.futures
import logging
import os
from typing import Any, Dict, Optional

from services.agent_memory_service import (
    load as memory_load,
    persist_short_term,
    persist_operational_state,
    append_decision_log,
)
from services.activity_logger import ActivityLogger
from services.automation.handlers import resolve_handler
from services.automation.utils import merge_dict

logger = logging.getLogger(__name__)

# Ejecutor dedicado: timeouts de agente sin bloquear el event loop del worker.
_AGENT_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=min(8, max(2, (os.cpu_count() or 2) * 2)),
    thread_name_prefix="zeus_agent",
)


def _get_agents():
    """Misma pila de agentes que el endpoint de chat (inicialización lazy por worker)."""
    from app.api.v1.endpoints import chat as chat_mod

    chat_mod.ensure_agent_stack()
    return chat_mod.AGENTS


def _company_from_context(context: Optional[Dict]) -> str:
    if not context:
        return "default"
    return str(context.get("company_id") or context.get("user_email") or "default")


def _safe_append_decision_log(*args: Any, **kwargs: Any) -> None:
    """Nunca relanza: fallos de memoria/BD no deben tumbar el chat tras respuesta LLM."""
    try:
        append_decision_log(*args, **kwargs)
    except Exception:
        logger.exception("unified_agent_runtime: append_decision_log omitido")


def _safe_persist_short_term(*args: Any, **kwargs: Any) -> None:
    try:
        persist_short_term(*args, **kwargs)
    except Exception:
        logger.exception("unified_agent_runtime: persist_short_term omitido")


def run_chat(
    agent_name: str,
    thread_id: str,
    message: str,
    company_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Unified chat: load memory, append user message, call agent, persist, return.
    """
    company_id = company_id or _company_from_context(context)
    agent_name = agent_name.upper().replace("-", " ").replace("_", " ")
    thread_id = thread_id or "main"
    agents = _get_agents()

    if agent_name not in agents or agents[agent_name] is None:
        return {"success": False, "error": f"Agente '{agent_name}' no disponible", "message": ""}

    agent = agents[agent_name]
    memory = memory_load(company_id, agent_name, thread_id)
    buf = memory.get("short_term") or []
    if not isinstance(buf, list):
        buf = []

    ctx = dict(context or {})
    ctx["user_message"] = message
    ctx["_memory"] = memory
    ctx["_thread_id"] = thread_id
    ctx["_company_id"] = company_id
    # Sin el turno actual: evita duplicar el último user en el prompt y reduce tokens.
    ctx["conversation_history"] = list(buf)

    buf.append({"role": "user", "content": message})

    timeout_sec = float(os.getenv("ZEUS_AGENT_PROCESS_TIMEOUT", "180") or "180")
    try:
        fut = _AGENT_EXECUTOR.submit(agent.process_request, ctx)
        result = fut.result(timeout=max(5.0, timeout_sec))
    except concurrent.futures.TimeoutError:
        _safe_append_decision_log(
            company_id,
            agent_name,
            thread_id,
            "chat_timeout",
            {"timeout_sec": timeout_sec},
        )
        msg = (
            "El agente tardó demasiado en responder. "
            "Reintenta con un mensaje más corto o revisa la carga del servicio."
        )
        return {"success": False, "error": "timeout", "message": msg}
    except Exception as e:
        _safe_append_decision_log(company_id, agent_name, thread_id, "chat_error", {"error": str(e)})
        return {"success": False, "error": str(e), "message": f"Error: {e}"}

    # Fallo explícito del agente (p. ej. error OpenAI): no mezclar con "respuesta vacía".
    if result.get("success") is False:
        err = (result.get("error") or "").strip() or "El agente no pudo completar la respuesta."
        _safe_append_decision_log(
            company_id,
            agent_name,
            thread_id,
            "chat_agent_failed",
            {"error": err[:500]},
        )
        return {
            "success": False,
            "message": err,
            "error": err,
        }

    content = result.get("content") or result.get("response") or ""
    if not str(content).strip():
        _safe_append_decision_log(
            company_id,
            agent_name,
            thread_id,
            "chat_empty_response",
            {"user_message_len": len(message)},
        )
        empty_err = "El agente no devolvió contenido. Reintenta en unos segundos."
        return {
            "success": False,
            "message": empty_err,
            "error": empty_err,
        }
    buf.append({"role": "assistant", "content": content})

    _safe_persist_short_term(company_id, agent_name, thread_id, buf)
    _safe_append_decision_log(
        company_id,
        agent_name,
        thread_id,
        "chat_response",
        {"user_message_len": len(message), "response_len": len(str(content))},
    )

    return {
        "success": result.get("success", True),
        "message": content,
        "confidence": result.get("confidence"),
        "hitl_required": result.get("human_approval_required", False),
        "error": result.get("error"),
    }


def run_workspace_task(activity) -> Dict[str, Any]:
    """
    Unified workspace: load memory, run handler (execute), persist state + decision log.
    Uses same agent identity: agent_name, thread_id = task_{activity.id}, company from user_email.
    """
    agent_name = (activity.agent_name or "").upper()
    thread_id = f"task_{activity.id}"
    company_id = (activity.user_email or "default").strip() or "default"

    memory = memory_load(company_id, agent_name, thread_id)
    handler = resolve_handler(agent_name, activity.action_type or "")

    if handler is None:
        result = {
            "status": "blocked_missing_handler",
            "notes": f"No handler for ({agent_name}, {activity.action_type}). Execution blocked.",
            "executed_handler": None,
        }
    else:
        result = handler(activity)
        if "executed_handler" not in result:
            result["executed_handler"] = getattr(handler, "__name__", None)

    status = result.get("status", "completed")
    artifacts = result.get("details_update", {}).get("automation", {}).get("deliverables") or result.get("details_update") or {}

    try:
        persist_operational_state(
            company_id,
            agent_name,
            thread_id,
            current_task=activity.action_description,
            status=status,
            next_action=None,
            artifacts=artifacts if isinstance(artifacts, dict) else {"raw": str(artifacts)},
            blocked=None,
        )
    except Exception:
        logger.exception("run_workspace_task: persist_operational_state omitido")
    _safe_append_decision_log(
        company_id,
        agent_name,
        thread_id,
        "workspace_execution",
        {
            "activity_id": activity.id,
            "action_type": activity.action_type,
            "status": status,
            "notes": result.get("notes"),
        },
    )

    return result
