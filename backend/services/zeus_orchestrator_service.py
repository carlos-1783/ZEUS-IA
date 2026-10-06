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
from services.agent_memory_service import (
    load as memory_load,
    persist_operational_state,
    scoped_thread_id,
)
from services.intent_parser_service import (
    _map_intent_to_action_type,
    build_action,
    is_affirmative_message,
    is_cancel_message,
    is_confirmation_message,
    looks_like_operational,
    parse_message,
)
from services.intent_parser import clarification_for_unknown, has_negation, is_conversational_request
from services import jarvis_clarification as clarif
from services import jarvis_model_comprehension as model_comp
from services import module_gate
from services.zeus_global_context import attach_context_to_action_payload, enrich_chat_context
from services.chain_log import log_chain_step
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
    return scoped_thread_id(_thread_id(context), user.id)


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


def _reject_pending(db: Session, user: User, row: ZeusPendingApproval, reason: str) -> bool:
    """Rechaza la solicitud y VERIFICA en BD que ya no esta pending (fail-closed).

    True si deja de estar pending (rechazada, o resuelta por otro actor); False si sigue
    pending porque el rechazo no se pudo persistir."""
    approval_id = row.id
    try:
        resolve_approval(db, approval_id=approval_id, user=user, approve=False, reason=reason)
    except HTTPException as exc:
        # 409: otro worker o la barra del workspace ya la resolvio.
        logger.info("zeus_chat_reject_skipped approval=%s status=%s", approval_id, exc.status_code)
    except Exception:
        db.rollback()
        logger.exception("No se pudo rechazar la aprobacion %s (%s)", approval_id, reason)
    try:
        db.expire_all()
        current = (
            db.query(ZeusPendingApproval.status).filter(ZeusPendingApproval.id == approval_id).scalar()
        )
    except Exception:
        db.rollback()
        logger.exception("No se pudo verificar el estado de la aprobacion %s", approval_id)
        return False
    return current != "pending"


_REJECT_FAILED_MSG = (
    "No se pudo cancelar la acción pendiente anterior. No he ejecutado nada ni creado otra; "
    "inténtalo de nuevo."
)


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
    if done.status == "audit_failed":
        return {
            **fail,
            "approval_id": done.id,
            "status": "audit_failed",
            "message": (
                "La acción pudo producirse pero no se ha podido verificar. "
                "Se ha avisado al equipo de seguridad; no la repitas hasta que se revise."
            ),
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
    """Ejecuta una ZeusAction en los módulos indicados.

    J5b: el resultado lleva `company_id` = empresa con la que se ejecuto realmente la accion
    (la de la accion, resuelta en servidor, o la primaria del usuario como hacen los
    handlers), para que la auditoria THALOS post-accion compruebe un tenant real."""
    import services.crm_office_service as crm_svc

    exec_company = action.company_id
    if exec_company is None:
        try:
            exec_company = crm_svc.primary_company_id(db, user)
        except Exception:
            logger.exception("execute_action: no se pudo resolver la empresa de ejecucion")
            exec_company = None
    # J9a: modulo activo de la empresa (mismo registro que el menu). Sin modulo no se ejecuta nada.
    blocked = module_gate.check_action(db, user, action.action_type)
    if blocked:
        log_chain_step(
            "ORQUESTAR", company_id=exec_company, user=user, agent=AGENT_ZEUS,
            action=action.action_type, status="blocked_module",
            details={"module": blocked["module"], "action_type": action.action_type},
        )
        return ZeusExecutionResult(
            success=False, intent=action.action_type, message=blocked["message"],
            executed=False, company_id=exec_company,
        )
    result = await _dispatch_action(db, user, action, force_execute=force_execute)
    result.company_id = exec_company
    return result


async def _dispatch_action(
    db: Session,
    user: User,
    action: ZeusAction,
    *,
    force_execute: bool = False,
) -> ZeusExecutionResult:
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

    def _step(step: str, action: str, status: str, **details: Any) -> bool:
        return log_chain_step(
            step, company_id=company_int, user=user, agent="ZEUS CORE",
            action=action, status=status, details=details,
        )

    def _module_block(action_type: str) -> Optional[Dict[str, Any]]:
        """J9a: si la empresa no tiene activo el modulo de la accion, ZEUS lo dice y no ejecuta."""
        blocked = module_gate.check_action(db, user, action_type)
        if not blocked:
            return None
        _step("ORQUESTAR", action_type, "blocked_module", module=blocked["module"], action_type=action_type)
        return {"handled": True, "success": False, "executed": False, "message": blocked["message"]}

    pending_row = _find_chat_pending(db, company_int, user, thread_id)
    expired_notice = False
    if pending_row is not None and is_expired(pending_row):
        _reject_pending(db, user, pending_row, "caducada")
        pending_row, expired_notice = None, True

    # CONTEXTO (J7): que contexto de empresa se uso; sin contenidos (ni clientes ni textos).
    _step(
        "CONTEXTO", "load_company_context", "success",
        company_id=company_int,
        company_type=global_context.get("company_type"),
        modules=sorted(k for k, v in (global_context.get("permissions") or {}).items() if v),
        pending_open=pending_row is not None,
        pending_expired=expired_notice,
        thread_id=thread_id,
    )

    explicit = is_confirmation_message(message)
    affirmative = is_affirmative_message(message)

    # J8: si ZEUS preguntó en este hilo, esta respuesta puede completar el dato. Solo cuando no hay
    # una aprobación abierta (el «sí/confirmar» de una aprobación tiene siempre prioridad).
    resumed = None
    if pending_row is None:
        clar_state = clarif.load_state(company_id, thread_id)
        if clar_state is not None:
            clarif.clear_state(company_id, thread_id)
            if is_cancel_message(message):
                _step("COMPRENDER", "clarification_cancelled", "rejected", intent=clar_state.get("intent"))
                return {"handled": True, "success": True, "executed": False,
                        "message": "De acuerdo, lo dejo. No he hecho nada."}
            resumed = clarif.resolve_reply(clar_state, message)
            _step("COMPRENDER", "clarification_reply",
                  "success" if resumed is not None else "abandoned",
                  intent=clar_state.get("intent"), kind=clar_state.get("kind"),
                  missing=clar_state.get("missing"))

    if pending_row is not None:
        if explicit or affirmative:
            confirmed_id, confirmed_action = pending_row.id, pending_row.action_type
            out = await _confirm_pending(db, user, pending_row)
            _step(
                "ORQUESTAR", "confirm_pending",
                "audit_failed" if out.get("status") == "audit_failed"
                else "success" if out.get("success") else "failed",
                approval_id=confirmed_id, pending_action=confirmed_action,
                executed=bool(out.get("executed")),
            )
            return out
        if is_cancel_message(message):
            cancelled_id = pending_row.id
            if not _reject_pending(db, user, pending_row, "cancelado por el usuario"):
                _step("ORQUESTAR", "cancel_pending", "failed", approval_id=cancelled_id)
                return {"handled": True, "success": False, "executed": False, "message": _REJECT_FAILED_MSG}
            _step("ORQUESTAR", "cancel_pending", "rejected", approval_id=cancelled_id)
            return {
                "handled": True,
                "success": True,
                "executed": False,
                "approval_id": cancelled_id,
                "message": "Acción cancelada. No se ha ejecutado nada.",
            }
        # Cambio de tema: se rechaza la solicitud para que la barra de decisión del workspace
        # no muestre algo que el chat ya abandonó.
        topic_ok = _reject_pending(db, user, pending_row, "cambio de tema")
        _step("ORQUESTAR", "reject_pending_topic_change", "rejected" if topic_ok else "failed",
              approval_id=pending_row.id)
        if not topic_ok:
            # Fail-closed: no se deja una fila confirmable en silencio ni se encadena otra accion.
            return {"handled": True, "success": False, "executed": False, "message": _REJECT_FAILED_MSG}
    elif explicit and resumed is None:
        _step("ORQUESTAR", "confirm_without_pending", "rejected", pending_expired=expired_notice)
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

    notice = None
    if resumed is not None:
        task = resumed
    else:
        task = parse_message(message)  # criterio estricto J8: red de seguridad y fallback
        # J9a: intencion clara de un modulo que la empresa no tiene -> se responde ya, sin modelo.
        if task.intent != "unknown" and not task.ambiguous_with and not (
            {"explicit_intent", "single_action"} & set(task.missing_entities)
        ):
            early = _module_block(_map_intent_to_action_type(task.intent, task.action))
            if early:
                return early
        # J8b: si el mensaje PUEDE pedir una accion con consecuencias, la comprension la hace el
        # modelo (salida validada; ante cualquier fallo se conserva `task`). Nunca ejecuta: solo
        # produce una tarea o una respuesta; la aprobacion humana sigue siendo obligatoria.
        comp = await model_comp.comprehend(db, user, company_int, message, task, _step)
        if comp.reply is not None:
            return {
                "handled": True, "success": True, "executed": False,
                "needs_clarification": comp.reply_is_question, "intent": "unknown", "message": comp.reply,
            }
        task = comp.task
        notice = comp.notice
    understood = task.intent != "unknown" and task.confidence >= MIN_CONFIDENCE and not task.needs_clarification
    if understood:
        comp_status = "success"
    elif task.needs_clarification and task.missing_entities and not task.ambiguous_with:
        comp_status = "needs_more_data"
    else:
        comp_status = "not_understood"
    _step(
        "COMPRENDER", "parse_intent", comp_status,
        intent=task.intent, confidence=float(task.confidence), min_confidence=float(MIN_CONFIDENCE),
        urgency=task.urgency, missing_entities=task.missing_entities, ambiguous_with=task.ambiguous_with,
        confidence_rule=(task.confidence_breakdown or {}).get("rule"),
        # solo TIPOS de entidad detectados, nunca sus valores (nombres/emails/importes son datos del cliente)
        entity_kinds=sorted(k for k, v in task.entities.model_dump().items() if v),
    )
    if task.needs_clarification and task.intent != "unknown":
        # J8: NO se ejecuta ni se crea aprobación. Se pregunta algo concreto y se recuerda lo entendido.
        question = task.clarification_question
        # Negacion/duda y varias peticiones no esperan un dato: no hay estado que continuar.
        if not ({"explicit_intent", "single_action"} & set(task.missing_entities)):
            if not clarif.save_state(company_id, thread_id, task):
                question += (
                    " (Aviso: no he podido recordar esta conversación; si respondes, incluye todos los "
                    "datos en un solo mensaje.)"
                )
        return {
            "handled": True, "success": True, "executed": False, "needs_clarification": True,
            "intent": task.intent, "message": question,
        }
    if not understood:
        if looks_like_operational(message) and has_negation(message):
            # «nunca envíes», «no mandes…» sin objeto reconocible: se entiende como NO hacer nada.
            return {
                "handled": True, "success": True, "executed": False, "needs_clarification": True,
                "intent": "unknown",
                "message": "Entendido, no hago nada. Si quieres que haga algo, dímelo de forma explícita.",
            }
        if looks_like_operational(message) and not is_conversational_request(message):
            return {
                "handled": True, "success": True, "executed": False, "needs_clarification": True,
                "intent": "unknown", "message": clarification_for_unknown(message),
            }
        return None

    action = _with_global_context(build_action(db, user, task), global_context)
    _step("COMPRENDER", "derive_action", "success", intent=task.intent, action_type=action.action_type)
    blocked_reply = _module_block(action.action_type)
    if blocked_reply:
        return blocked_reply

    if action.action_type in CONFIRMABLE_ACTIONS:
        action.requires_confirmation = True
        if action.action_type == "send_campaign":
            preview = handlers.preview_send_campaign(db, user, action)
        else:
            preview = _preview_create_customer(action)
            if preview is None:
                _step("ORQUESTAR", action.action_type, "needs_more_data", requires_confirmation=True)
                return _to_chat_payload(await execute_action(db, user, action, force_execute=False))
        if notice:
            # J8b: el modelo dijo «sí» sobre un mensaje con negacion/duda: aviso explicito en la vista previa.
            preview = {**preview, "message": f"{notice} {preview['message']}"}
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
            _step("ORQUESTAR", action.action_type, "rejected" if exc.status_code == 403 else "failed",
                  requires_confirmation=True, http_status=exc.status_code)
            if exc.status_code == 403:
                return {**refusal, "message": f"No tienes permiso para esta acción: {exc.detail}"}
            return {**refusal, "message": str(exc.detail)}
        except Exception:
            db.rollback()
            logger.exception("zeus_chat: no se pudo persistir la solicitud; no se ejecuta nada")
            _step("ORQUESTAR", action.action_type, "failed", requires_confirmation=True)
            return {
                **refusal,
                "message": (
                    "No se pudo registrar la solicitud de confirmación. "
                    "No se ha ejecutado nada; inténtalo de nuevo."
                ),
            }
        _step("ORQUESTAR", action.action_type, "needs_confirmation",
              requires_confirmation=True, approval_id=row.id)
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

    _step("ORQUESTAR", action.action_type, "success", requires_confirmation=False)
    result = await execute_action(db, user, action, force_execute=False)
    payload = _to_chat_payload(result)
    if result.executed or not result.success:
        # ACTUAR de la rama directa (las acciones confirmables las registra approval_executed).
        _step("ACTUAR", action.action_type, "success" if result.executed else "failed",
              executed=bool(result.executed), result_company_id=result.company_id)
    if result.executed:
        # THALOS (J5): auditoria post-accion de la rama directa del chat.
        from services.thalos_request_guard_v1 import thalos_audit_result

        audit = thalos_audit_result(
            db, user=user, company_id=company_int, agent="ZEUS", action=action.action_type,
            result={"success": result.success, "executed": result.executed,
                    "company_id": result.company_id},
            source="thalos_audit_chat",
        )
        if not audit["ok"]:
            return {"handled": True, "success": False, "executed": False,
                    "message": f"No se puede confirmar la accion: auditoria THALOS fallida ({audit['reason']})."}
    return payload


__all__ = ["try_handle_zeus_chat", "execute_action", "AGENT_ZEUS", "enrich_chat_context"]
