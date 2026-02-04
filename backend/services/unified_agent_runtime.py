"""
Unified agent runtime: one execution loop for chat and workspace.
Load memory -> Evaluate -> Decide -> Execute -> Persist.
NO_RESPONSE_WITHOUT_MEMORY_WRITE.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from services.agent_memory_service import (
    load as memory_load,
    persist_short_term,
    persist_operational_state,
    append_decision_log,
)
from services.activity_logger import ActivityLogger
from services.automation.handlers import resolve_handler
from services.automation.utils import merge_dict


def _get_agents():
    """Use same agent instances as chat endpoint."""
    from app.api.v1.endpoints.chat import AGENTS
    return AGENTS


def _company_from_context(context: Optional[Dict]) -> str:
    if not context:
        return "default"
    return str(context.get("company_id") or context.get("user_email") or "default")


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

    buf.append({"role": "user", "content": message})
    ctx = dict(context or {})
    ctx["user_message"] = message
    ctx["_memory"] = memory
    ctx["_thread_id"] = thread_id
    ctx["_company_id"] = company_id
    ctx["conversation_history"] = memory.get("short_term") or []

    try:
        result = agent.process_request(ctx)
    except Exception as e:
        append_decision_log(company_id, agent_name, thread_id, "chat_error", {"error": str(e)})
        return {"success": False, "error": str(e), "message": f"Error: {e}"}

    content = result.get("content") or result.get("response") or "Sin respuesta"
    buf.append({"role": "assistant", "content": content})

    persist_short_term(company_id, agent_name, thread_id, buf)
    append_decision_log(
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
    append_decision_log(
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
