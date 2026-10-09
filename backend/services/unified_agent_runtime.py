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
    scoped_thread_id,
)
from services.activity_logger import ActivityLogger
from services.automation.handlers import resolve_handler
from services.automation.utils import merge_dict

logger = logging.getLogger(__name__)

def _agent_executor_max_workers() -> int:
    # Contenedores pequeños: muchos hilos + numpy/moviepy = pico de RSS y OOM killer.
    raw = (os.getenv("ZEUS_AGENT_THREAD_POOL_MAX") or "").strip()
    if raw.isdigit():
        return max(1, min(8, int(raw)))
    cpu = os.cpu_count() or 2
    return max(1, min(4, cpu))


# Ejecutor dedicado: timeouts de agente sin bloquear el event loop del worker.
_AGENT_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=_agent_executor_max_workers(),
    thread_name_prefix="zeus_agent",
)


def _get_agents():
    """Misma pila de agentes que el endpoint de chat (inicialización lazy por worker)."""
    from app.api.v1.endpoints import chat as chat_mod

    chat_mod.ensure_agent_stack()
    return chat_mod.AGENTS


PLATFORM_SCOPE = "platform"


class MemoryScopeError(ValueError):
    """No hay empresa/usuario resueltos en servidor: no existe clave de memoria segura."""


def _memory_scope(company_id: Any, context: Optional[Dict]) -> tuple:
    """(company_key, user_id) de la memoria conversacional. Sin fallbacks compartidos.

    - user_id: lo fija el servidor en el contexto; sin el no hay aislamiento por usuario.
    - company_id: la empresa resuelta en servidor. Sin empresa solo el superusuario
      (`_is_superuser`, fijado por el servidor) opera, en el espacio "platform" y siempre
      acotado a su propio user_id. Cualquier otro caso es un error (nunca "default" ni email).
    """
    ctx = context or {}
    user_id = ctx.get("user_id")
    if user_id in (None, ""):
        raise MemoryScopeError("Sesion de usuario requerida para la memoria de conversacion.")
    cid = company_id if company_id not in (None, "") else ctx.get("company_id")
    if cid not in (None, ""):
        return str(cid), user_id
    if ctx.get("_is_superuser") is True:
        return PLATFORM_SCOPE, user_id
    raise MemoryScopeError("El usuario no tiene empresa asignada: no se puede abrir la conversacion.")


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


def _log_memory_context(agent_name, thread_id, company_key, user_id, context, n_messages) -> None:
    from types import SimpleNamespace

    from services.chain_log import log_chain_step

    ctx = context or {}
    cid = ctx.get("company_id")
    log_chain_step(
        "CONTEXTO",
        company_id=cid if isinstance(cid, int) else None,
        user=SimpleNamespace(id=user_id, email=ctx.get("user_email")),
        agent=agent_name,
        action="load_conversation_memory",
        status="success",
        details={
            "memory_scope": company_key,
            "thread_id": thread_id,
            "memory_messages": n_messages,
            "memory_turns": n_messages // 2,
        },
    )


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
    agent_name = agent_name.upper().replace("-", " ").replace("_", " ")
    try:
        company_id, user_id = _memory_scope(company_id, context)
    except MemoryScopeError as exc:
        logger.warning("run_chat rechazado (%s): agente=%s", exc, agent_name)
        return {"success": False, "error": "memory_scope_required", "message": str(exc)}
    # Memoria aislada por empresa + usuario + agente + hilo (R6).
    thread_id = scoped_thread_id(thread_id, user_id)
    agents = _get_agents()

    if agent_name not in agents or agents[agent_name] is None:
        return {"success": False, "error": f"Agente '{agent_name}' no disponible", "message": ""}

    agent = agents[agent_name]
    memory = memory_load(company_id, agent_name, thread_id)
    buf = memory.get("short_term") or []
    if not isinstance(buf, list):
        buf = []

    # CONTEXTO (J7): memoria cargada, solo cardinalidades (nunca contenidos).
    _log_memory_context(agent_name, thread_id, company_id, user_id, context, len(buf))

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


def _resolve_activity_company(activity) -> Optional[int]:
    """Empresa de una actividad de workspace: su propio company_id si existe; si no, la empresa
    primaria del usuario del email (BD). None si no hay ninguna (sin fallback a "default")."""
    cid = getattr(activity, "company_id", None)
    if isinstance(cid, int):
        return cid
    email = (getattr(activity, "user_email", None) or "").strip()
    if not email:
        return None
    from app.db.session import SessionLocal
    from app.models.user import User
    import services.crm_office_service as crm_svc

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        return crm_svc.primary_company_id(db, user) if user else None
    except Exception:
        logger.exception("run_workspace_task: no se pudo resolver la empresa del usuario")
        return None
    finally:
        db.close()


def run_workspace_task(activity) -> Dict[str, Any]:
    """
    Unified workspace: load memory, run handler (execute), persist state + decision log.
    Uses same agent identity: agent_name, thread_id = task_{activity.id}, company from user_email.
    """
    agent_name = (activity.agent_name or "").upper()
    thread_id = f"task_{activity.id}"
    resolved = _resolve_activity_company(activity)
    if resolved is None:
        # J7: sin empresa no hay clave de memoria segura ni ejecucion: error controlado y
        # registrado, nunca una empresa "default" compartida ni el email como empresa.
        logger.error("run_workspace_task: actividad %s sin empresa resoluble; no se ejecuta", activity.id)
        from types import SimpleNamespace

        from services.chain_log import log_chain_step

        log_chain_step(
            "ACTUAR",
            company_id=None,
            user=SimpleNamespace(id=None, email=activity.user_email),
            agent=agent_name or "UNKNOWN",
            action="workspace_task_blocked_no_company",
            action_type="workspace_task_blocked",
            description=f"Actividad {activity.id} ({agent_name}, {activity.action_type}) bloqueada: sin empresa resoluble.",
            status="blocked_no_company",
            priority="high",
            details={"original_activity_id": activity.id, "reason": "company_unresolved", "executed": False},
        )
        return {
            "status": "blocked_no_company",
            "notes": "La actividad no tiene empresa resoluble (company_id ni usuario con empresa). No se ejecuta.",
            "executed_handler": None,
        }
    company_id = str(resolved)

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
