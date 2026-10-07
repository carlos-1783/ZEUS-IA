"""
Endpoint para chat con agentes IA
"""
import asyncio
import logging
import os
import sys
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.chat_message import ChatMessageListResponse, ChatMessageOut
from services import chat_persistence_service as chat_db

# Agregar el directorio raíz al path para importar agentes
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

from agents.zeus_core import ZeusCore
from agents.perseo import Perseo
from agents.rafael import Rafael
from agents.thalos import Thalos
from agents.justicia import Justicia
from agents.afrodita import Afrodita
from services.teamflow_engine import teamflow_engine
from app.core.auth import get_current_active_user
from app.core.config import settings as core_settings
from app.models.user import User
from services.activity_logger import ActivityLogger
from services.chain_log import (
    begin_chain,
    end_chain,
    log_chain_step,
    normalize_channel,
    summarize_text,
)
from services.thalos_request_guard_v1 import thalos_request_guard

router = APIRouter()
logger = logging.getLogger(__name__)

_agents_lock = threading.Lock()
_agents_ready = False

zeus: Optional[ZeusCore] = None
perseo: Optional[Perseo] = None
rafael: Optional[Rafael] = None
thalos: Optional[Thalos] = None
justicia: Optional[Justicia] = None
afrodita: Optional[Afrodita] = None

AGENTS: Dict[str, Any] = {}

AGENT_ORDER_KEYS = (
    "ZEUS CORE",
    "PERSEO",
    "RAFAEL",
    "THALOS",
    "JUSTICIA",
    "AFRODITA",
)


def ensure_agent_stack() -> None:
    """
    Inicializa agentes y TPV una sola vez por proceso (Gunicorn worker).
    Evita cargar modelos/pesos al importar el router → arranque Railway más rápido y menos RAM duplicada en import.
    """
    global zeus, perseo, rafael, thalos, justicia, afrodita, _agents_ready, AGENTS

    with _agents_lock:
        if _agents_ready:
            return

        try:
            print("🔄 Inicializando ZEUS CORE...")
            z = ZeusCore()
            print("✅ ZEUS CORE OK")
            z.set_teamflow_engine(teamflow_engine)

            print("🔄 Inicializando PERSEO...")
            p = Perseo()
            print("✅ PERSEO OK")

            print("🔄 Inicializando RAFAEL...")
            r = Rafael()
            print("✅ RAFAEL OK")

            print("🔄 Inicializando THALOS...")
            t = Thalos()
            print("✅ THALOS OK")

            print("🔄 Inicializando JUSTICIA...")
            j = Justicia()
            print("✅ JUSTICIA OK")

            print("🔄 Inicializando AFRODITA...")
            a = Afrodita()
            print("✅ AFRODITA OK")

            z.register_agent(p)
            z.register_agent(r)
            z.register_agent(t)
            z.register_agent(j)
            z.register_agent(a)

            p.set_zeus_core_ref(z)
            r.set_zeus_core_ref(z)
            t.set_zeus_core_ref(z)
            j.set_zeus_core_ref(z)
            a.set_zeus_core_ref(z)

            if os.getenv("ZEUS_AUTO_PRELAUNCH_PLAN", "false").strip().lower() in ("1", "true", "yes", "on"):
                try:
                    plan_result = z.ensure_prelaunch_plan()
                    if plan_result.get("success"):
                        print("✅ Plan pre-lanzamiento preparado automáticamente.")
                except Exception as prelaunch_error:
                    print(f"⚠️ No se pudo preparar el plan pre-lanzamiento automáticamente: {prelaunch_error}")

            try:
                from services.tpv_service import set_tpv_integrations

                set_tpv_integrations(
                    rafael=r,
                    justicia=j,
                    afrodita=a,
                )
                print("✅ Integraciones TPV configuradas")
            except Exception as tpv_error:
                print(f"⚠️ Error configurando integraciones TPV: {tpv_error}")

            zeus, perseo, rafael, thalos, justicia, afrodita = z, p, r, t, j, a
            AGENTS.clear()
            AGENTS.update(
                {
                    "ZEUS CORE": zeus,
                    "PERSEO": perseo,
                    "RAFAEL": rafael,
                    "THALOS": thalos,
                    "JUSTICIA": justicia,
                    "AFRODITA": afrodita,
                }
            )
            print("✅ Todos los agentes inicializados correctamente")
        except Exception as e:
            print(f"❌ Error inicializando agentes: {e}")
            import traceback

            print("📋 Traceback completo:")
            traceback.print_exc()
            zeus = perseo = rafael = thalos = justicia = afrodita = None
            AGENTS.clear()
            for k in AGENT_ORDER_KEYS:
                AGENTS[k] = None
        finally:
            _agents_ready = True

# H-01 (ZEUS_JARVIS_INTERACTION_AUDIT.md): identidad y estado interno que el cliente NO puede
# imponer. La empresa y el usuario se derivan solo en servidor (JWT -> BD).
_CLIENT_FORBIDDEN_CONTEXT_KEYS = frozenset(
    {
        "company_id",
        "tenant_id",
        "user_id",
        "user_email",
        "zeus_global_context",
        "conversation_history",
        # J3: control de ejecucion/enrutado que decide solo el servidor.
        "force_execute",
        "confirm_action",
        "skip_action_execution",
        "task_type",
        "phase",
        "workflow_id",
        "user_message",
        # J4: claves que ZEUS CORE fija al comunicar/coordinar agentes; el cliente no las impone.
        "requested_by",
        "workflow_payload",
        "from_agent",
        "inter_agent_communication",
        "multi_agent_task",
        "other_agents",
        "shared_context",
    }
)


def build_server_context(
    db: Session,
    user: User,
    client_context: Optional[Dict[str, Any]],
    thread_id: str,
) -> Dict[str, Any]:
    """Contexto de una petición de chat: lo que envía el cliente, sin identidad ni estado interno.

    Se descartan las claves de identidad (`company_id`, `user_id`, `user_email`, …) y todo lo
    que empiece por `_` (`_memory`, `_company_id`, … los fija el runtime). Se conservan los
    campos legítimos del cliente (p. ej. `image_url`, `pdf_url`, `video_url` de PERSEO). Después
    el servidor fija empresa y usuario a partir del usuario autenticado.
    """
    ctx: Dict[str, Any] = {
        k: v
        for k, v in (client_context or {}).items()
        if k not in _CLIENT_FORBIDDEN_CONTEXT_KEYS and not str(k).startswith("_")
    }
    ctx["thread_id"] = thread_id
    ctx["user_id"] = user.id
    ctx["user_email"] = user.email
    ctx["company_id"] = chat_db.resolve_company_id(db, user)
    return ctx


class ChatRequest(BaseModel):
    message: str
    context: Optional[dict] = None
    thread_id: Optional[str] = None

class ChatResponse(BaseModel):
    agent: str
    message: str
    success: bool
    confidence: Optional[float] = None
    hitl_required: Optional[bool] = None
    error: Optional[str] = None
    workspace_document_id: Optional[int] = None
    executed_action: Optional[bool] = None
    needs_confirmation: Optional[bool] = None
    execution: Optional[dict] = None
    approval_id: Optional[int] = None
    # J7: id de correlacion de la peticion (servidor); enlaza todos los pasos en agent_activities.
    request_id: Optional[str] = None
    # J7: avisos (p. ej. un paso ACTUAR/AUDITAR que no se pudo registrar). Nunca se ocultan.
    warnings: Optional[List[str]] = None
    # J8: ZEUS pregunta un dato concreto en vez de actuar (no se ha ejecutado ni aprobado nada).
    needs_clarification: Optional[bool] = None
    intent: Optional[str] = None
    # J9b: pasos del plan multiagente (agente, tipo, estado y resumen corto por paso).
    steps: Optional[List[dict]] = None
    # J10: evidencia enlazada (documento/aprobacion/recurso creado/registro J7): {kind, id, agent, title,
    # url, status}. Los entregables no se incrustan en `message`: se enlazan aqui.
    evidence: Optional[List[dict]] = None
    # J10 CONTINUAR: propuesta concreta del siguiente paso, o None si no hay nada logico que proponer.
    next_step: Optional[str] = None
    # Solo servidor: tipo del siguiente paso (se registra en J7; no sale en la respuesta).
    next_step_type: Optional[str] = Field(default=None, exclude=True)

class AgentCommunicationRequest(BaseModel):
    from_agent: str
    to_agent: str
    message: str
    context: Optional[dict] = None

class MultiAgentTaskRequest(BaseModel):
    task_description: str
    required_agents: List[str]
    context: Optional[dict] = None


def _persist_assistant(
    db: Session,
    user: User,
    agent_name: str,
    thread_id: str,
    text: str,
    company_id: Optional[int] = None,
) -> None:
    chat_db.save_message(
        db,
        user=user,
        agent_name=agent_name,
        thread_id=thread_id,
        role="assistant",
        message=text or "",
        company_id=company_id,
    )


@router.get("/messages", response_model=ChatMessageListResponse)
async def get_chat_messages(
    agent_name: str = Query(..., description="Nombre del agente (ej. ZEUS CORE, PERSEO)"),
    thread_id: str = Query("main"),
    limit: int = Query(200, ge=1, le=500),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Historial de chat persistido para el usuario y agente indicados."""
    agent_norm = chat_db.normalize_agent_name(agent_name)
    tid = (thread_id or "main").strip() or "main"
    rows = chat_db.list_messages(
        db,
        user=current_user,
        agent_name=agent_norm,
        thread_id=tid,
        limit=limit,
    )
    return ChatMessageListResponse(
        success=True,
        messages=[ChatMessageOut.model_validate(r) for r in rows],
        total=len(rows),
        agent_name=agent_norm,
        thread_id=tid,
    )


@router.post("/{agent_name}/chat", response_model=ChatResponse)
async def chat_with_agent(
    agent_name: str,
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(thalos_request_guard),
    db: Session = Depends(get_db),
):
    """Chat con un agente. J7: abre la cadena (correlation_id de servidor), registra ESCUCHAR
    al entrar y RESPONDER/CONTINUAR al salir, y devuelve `request_id` y `warnings`."""
    chain, token = begin_chain()
    norm_agent = agent_name.upper().replace("-", " ").replace("_", " ")
    try:
        chain_company = chat_db.resolve_company_id(db, current_user)
    except Exception:
        logger.exception("chat: no se pudo resolver la empresa para el registro de cadena")
        chain_company = None
    try:
        # ESCUCHAR: canal como dato no sensible (lista blanca text/voice); texto SOLO como resumen
        # truncado y enmascarado (el mensaje completo ya vive en chat_messages, no se duplica aqui).
        log_chain_step(
            "ESCUCHAR", company_id=chain_company, user=current_user, agent=norm_agent,
            action="message_received", status="success",
            details={
                "channel": normalize_channel((request.context or {}).get("channel")),
                "message_len": len(request.message or ""),
                "message_preview": summarize_text(request.message),
                "thread_id": request.thread_id or (request.context or {}).get("thread_id") or "main",
            },
        )
        try:
            resp = await _chat_impl(norm_agent, request, background_tasks, current_user, db, chain_company)
        except HTTPException as exc:
            log_chain_step(
                "RESPONDER", company_id=chain_company, user=current_user, agent=norm_agent,
                action="respond", status="rejected", details={"http_status": exc.status_code},
            )
            raise
        status = (
            "needs_confirmation" if resp.needs_confirmation
            else "needs_more_data" if resp.needs_clarification
            else "success" if resp.success else "failed"
        )
        log_chain_step(
            "RESPONDER", company_id=chain_company, user=current_user, agent=norm_agent,
            action="respond", status=status,
            details={
                "success": bool(resp.success),
                "executed_action": bool(resp.executed_action),
                "approval_id": resp.approval_id,
                "workspace_document_id": resp.workspace_document_id,
                "has_evidence": bool(resp.approval_id or resp.workspace_document_id),
                "response_len": len(resp.message or ""),
            },
        )
        step_type = resp.next_step_type  # solo el TIPO (nunca texto del usuario ni del paso)
        if resp.needs_confirmation and resp.approval_id:
            log_chain_step(
                "CONTINUAR", company_id=chain_company, user=current_user, agent=norm_agent,
                action="pending_confirmation_open", status="needs_confirmation",
                details={"approval_id": resp.approval_id, "next": "confirm_or_cancel", "next_step_type": step_type},
            )
        elif resp.needs_clarification:
            log_chain_step(
                "CONTINUAR", company_id=chain_company, user=current_user, agent=norm_agent,
                action="awaiting_user_clarification", status="needs_more_data",
                details={"intent": resp.intent, "next": "user_reply_in_same_thread", "next_step_type": step_type},
            )
        elif resp.hitl_required:
            log_chain_step(
                "CONTINUAR", company_id=chain_company, user=current_user, agent=norm_agent,
                action="human_review_required", status="needs_confirmation",
                details={"next": "human_review", "next_step_type": step_type},
            )
        elif step_type:
            log_chain_step(
                "CONTINUAR", company_id=chain_company, user=current_user, agent=norm_agent,
                action="next_step_proposed", status="success",
                details={"next_step_type": step_type,
                         "evidence_kinds": sorted({e.get("kind") for e in resp.evidence or []})},
            )
        resp.request_id = chain.correlation_id
        resp.warnings = list(chain.warnings) or None
        _attach_audit_evidence(db, current_user, chain_company, resp)
        return resp
    finally:
        end_chain(token)


def _attach_audit_evidence(db: Session, user: User, company_id: Optional[int], resp: ChatResponse) -> None:
    """J10: enlace al registro J7 de esta peticion (solo si se persistio algun paso de la cadena)."""
    if not resp.request_id or company_id is None:
        return
    try:
        from services import jarvis_evidence as jev

        item = jev.evidence_item(db, user, company_id, "audit", resp.request_id)
        if item is not None:
            resp.evidence = jev.dedupe(list(resp.evidence or []) + [item])
    except Exception:
        logger.exception("chat: no se pudo adjuntar la evidencia del registro J7")


async def _chat_impl(
    agent_name: str,
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    current_user: User,
    db: Session,
    chain_company: Optional[int],
) -> ChatResponse:
    """
    Chat con un agente específico
    
    Args:
        agent_name: Nombre del agente (ZEUS CORE, PERSEO, RAFAEL, THALOS, JUSTICIA)
        request: Mensaje y contexto opcional
    
    Returns:
        Respuesta del agente
    """
    # Carga de agentes antes de leer AGENTS (dict vacío hasta ensure).
    await asyncio.to_thread(ensure_agent_stack)

    # Normalizar nombre del agente
    agent_name = agent_name.upper().replace("-", " ").replace("_", " ")
    
    # Verificar que el agente existe
    if agent_name not in AGENTS:
        raise HTTPException(
            status_code=404,
            detail=f"Agente '{agent_name}' no encontrado. Agentes disponibles: {list(AGENTS.keys())}"
        )
    
    agent = AGENTS[agent_name]
    
    if agent is None:
        raise HTTPException(
            status_code=500,
            detail=f"Agente '{agent_name}' no está inicializado correctamente"
        )

    client_context = request.context or {}
    thread_id = request.thread_id or client_context.get("thread_id") or "main"

    try:
        from services.unified_agent_runtime import run_chat

        # H-01: empresa y usuario salen del usuario autenticado, nunca del `context` del cliente.
        context = build_server_context(db, current_user, client_context, thread_id)
        context["user_message"] = request.message

        # J9a: el agente destino declara su modulo (services.module_gate.AGENT_MODULE); sin modulo
        # activo no se llama al agente ni al modelo.
        from services import module_gate

        blocked_agent = module_gate.check_agent(db, current_user, agent_name)
        if blocked_agent:
            log_chain_step(
                "ORQUESTAR", company_id=chain_company, user=current_user, agent=agent_name,
                action="route_to_agent", status="blocked_module",
                details={"agent": agent_name, "module": blocked_agent["module"], "thread_id": thread_id},
            )
            return ChatResponse(
                agent=agent_name, message=blocked_agent["message"], success=False,
                error=blocked_agent["message"],
            )

        if agent_name == "ZEUS CORE":
            from services.zeus_global_context import enrich_chat_context

            context = enrich_chat_context(db, current_user, context)
        else:
            # J9a: empresa, tipo y modulos activos tambien para PERSEO/RAFAEL/JUSTICIA/AFRODITA/THALOS.
            from services.zeus_global_context import build_agent_company_context

            context["zeus_global_context"] = build_agent_company_context(db, current_user)

        company_id = context.get("company_id")
        if not isinstance(company_id, int):
            company_id = chat_db.resolve_company_id(db, current_user)

        chat_db.save_message(
            db,
            user=current_user,
            agent_name=agent_name,
            thread_id=thread_id,
            role="user",
            message=request.message,
            company_id=company_id,
        )

        # ZEUS Core: intent → task → ejecución real (CRM, campaña, email) antes del LLM.
        if agent_name == "ZEUS CORE":
            from services.zeus_orchestrator_service import try_handle_zeus_chat

            # J3: la ejecucion la decide el servidor (pending persistido + "confirmar" del mismo
            # usuario); ningun flag del cliente influye.
            bridge = await try_handle_zeus_chat(
                db,
                current_user,
                request.message,
                context,
            )
            if bridge and bridge.get("handled"):
                bridge_msg = bridge.get("message", "") or ""
                _persist_assistant(
                    db,
                    current_user,
                    agent_name,
                    thread_id,
                    bridge_msg,
                    company_id=company_id,
                )
                # J7: los pasos de la cadena (ocultos) los registran el orquestador y la ruta. Aqui se
                # conserva la fila VISIBLE del turno que ve el cliente en su panel. Si la accion se
                # ejecuto via aprobacion, ya existe la fila visible approval_executed: no se duplica.
                if not (bridge.get("executed") and bridge.get("approval_id")):
                    log_chain_step(
                        "ACTUAR", company_id=chain_company, user=current_user, agent=agent_name,
                        action="zeus_chat_turn", action_type="chat_request_processed",
                        description=f"Chat procesado por {agent_name}",
                        status="completed" if bridge.get("success") else "failed",
                        details={
                            "request_type": "chat",
                            "thread_id": thread_id,
                            "executed_action": bool(bridge.get("executed")),
                            "needs_confirmation": bool(bridge.get("needs_confirmation")),
                            "approval_id": bridge.get("approval_id"),
                        },
                        visible_to_client=True,
                    )
                from services import jarvis_evidence as jev

                ev_items = jev.bridge_evidence(db, current_user, company_id, bridge)
                ns_type, ns_text = jev.next_step(db, current_user, company_id, bridge, ev_items)
                return ChatResponse(
                    agent=agent_name,
                    message=bridge_msg,
                    evidence=ev_items or None,
                    next_step=ns_text,
                    next_step_type=ns_type,
                    success=bool(bridge.get("success")),
                    executed_action=bool(bridge.get("executed")),
                    needs_confirmation=bool(bridge.get("needs_confirmation")),
                    execution=bridge.get("execution") if isinstance(bridge.get("execution"), dict) else None,
                    approval_id=bridge.get("approval_id"),
                    needs_clarification=True if bridge.get("needs_clarification") else None,
                    intent=bridge.get("intent"),
                    steps=bridge.get("steps") if isinstance(bridge.get("steps"), list) else None,
                    error=None if bridge.get("success") else bridge.get("message"),
                )

        # Servidor-only (prefijo `_`: no llega al prompt): habilita el espacio "platform" de memoria
        # para superusuarios sin empresa. Se fija aqui, tras build_server_context.
        context["_is_superuser"] = bool(getattr(current_user, "is_superuser", False))

        log_chain_step(
            "ORQUESTAR", company_id=chain_company, user=current_user, agent=agent_name,
            action="route_to_agent", status="success",
            details={"agent": agent_name, "requires_confirmation": False, "thread_id": thread_id},
        )

        # CRÍTICO (Railway / Gunicorn): run_chat es síncrono y largo (LLM). No en el event loop.
        result = await asyncio.to_thread(
            run_chat,
            agent_name,
            thread_id,
            request.message,
            company_id,
            context,
        )

        if result.get("success"):
            # Producción: sanitizar respuesta PERSEO para evitar disclaimers tipo
            # "como IA no puedo crear vídeos" en el mensaje visible al cliente.
            if agent_name == "PERSEO":
                try:
                    from services.workspace_deliverables import normalize_perseo_chat_message

                    result["message"] = normalize_perseo_chat_message(result.get("message", "") or "")
                except Exception:
                    logger.exception("No se pudo normalizar mensaje PERSEO")

            workspace_document_id = None
            try:
                from services.workspace_deliverables import persist_agent_chat_deliverable

                extra_ctx = {
                    k: context[k]
                    for k in ("image_url", "video_url", "pdf_url", "media_url")
                    if context.get(k)
                }
                wd = persist_agent_chat_deliverable(
                    db,
                    current_user,
                    agent_name,
                    result.get("message", "") or "",
                    extra_context=extra_ctx or None,
                )
                if wd is not None:
                    workspace_document_id = wd.id
                    # Vídeo de presentación (slides) en segundo plano si hay imagen de referencia y no hay vídeo adjunto
                    if (
                        agent_name.upper().strip() == "PERSEO"
                        and core_settings.PERSEO_CHAT_AUTO_VIDEO
                    ):
                        img_u = (context.get("image_url") or "").strip()
                        vid_u = (context.get("video_url") or "").strip()
                        if img_u and not vid_u:
                            try:
                                pl = dict(wd.document_payload or {})
                                c = pl.get("content")
                                if isinstance(c, dict):
                                    c["generated_video_status"] = "pending"
                                    c["generated_video_started_at"] = (
                                        datetime.now(timezone.utc).isoformat()
                                    )
                                    pl["content"] = c
                                    wd.document_payload = pl
                                    db.add(wd)
                                    db.commit()
                                from services.perseo_chat_video_job import (
                                    run_perseo_chat_video_generation_safe,
                                )

                                background_tasks.add_task(
                                    run_perseo_chat_video_generation_safe,
                                    wd.id,
                                    current_user.id,
                                )
                            except Exception as vid_sched:
                                logger.warning(
                                    "No se pudo programar vídeo PERSEO chat: %s", vid_sched
                                )
            except Exception as persist_err:
                try:
                    db.rollback()
                except Exception:
                    pass
                logger.exception(
                    "No se pudo persistir entregable workspace tras chat: %s", persist_err
                )

            log_chain_step(
                "ACTUAR", company_id=chain_company, user=current_user, agent=agent_name,
                action="agent_chat", action_type="chat_request_processed",
                description=f"Chat procesado por {agent_name}", status="completed",
                details={"request_type": "chat", "thread_id": thread_id,
                         "workspace_document_id": workspace_document_id},
                visible_to_client=True,
            )
            ok_msg = result.get("message", "Sin respuesta") or ""
            from services import jarvis_evidence as jev

            ev_items: List[dict] = []
            ns_type = ns_text = None
            if workspace_document_id is not None:
                doc_ev = jev.evidence_item(db, current_user, company_id, "document", workspace_document_id)
                if doc_ev is not None:
                    ev_items.append(doc_ev)
                    if jev.is_long_deliverable(ok_msg):
                        # entregable: el chat lleva un resumen breve; el texto completo vive en el workspace
                        ok_msg = jev.brief(ok_msg, agent_name)
                        ns_type = "review_draft"
                        ns_text = f"Revisa el borrador en el workspace de {agent_name} y apruébalo."
            _persist_assistant(
                db,
                current_user,
                agent_name,
                thread_id,
                ok_msg,
                company_id=company_id,
            )
            return ChatResponse(
                agent=agent_name,
                message=ok_msg,
                success=True,
                confidence=result.get("confidence"),
                hitl_required=result.get("hitl_required", False),
                workspace_document_id=workspace_document_id,
                evidence=ev_items or None,
                next_step=ns_text,
                next_step_type=ns_type,
            )
        log_chain_step(
            "ACTUAR", company_id=chain_company, user=current_user, agent=agent_name,
            action="agent_chat", action_type="chat_request_failed",
            description=f"Chat fallido en {agent_name}", status="failed", priority="normal",
            details={"error": str(result.get("error"))[:300], "request_type": "chat",
                     "thread_id": thread_id},
            visible_to_client=True,
        )
        fail_msg = (result.get("message") or "").strip() or (
            result.get("error") or ""
        ).strip() or f"Error: {result.get('error', 'Error desconocido')}"
        _persist_assistant(
            db,
            current_user,
            agent_name,
            thread_id,
            fail_msg,
            company_id=company_id,
        )
        return ChatResponse(
            agent=agent_name,
            message=fail_msg,
            success=False,
            error=result.get("error"),
        )
    except Exception as e:
        print(f"❌ Error en chat con {agent_name}: {e}")
        import traceback
        traceback.print_exc()
        log_chain_step(
            "ACTUAR", company_id=chain_company, user=current_user, agent=agent_name,
            action="agent_chat", action_type="chat_request_exception",
            description=f"Excepción en chat {agent_name}", status="failed", priority="high",
            details={"error": str(e)[:300], "request_type": "chat"},
            visible_to_client=True,
        )
        exc_msg = f"Error interno: {str(e)}"
        _persist_assistant(
            db,
            current_user,
            agent_name,
            thread_id,
            exc_msg,
            company_id=chat_db.resolve_company_id(db, current_user),
        )
        return ChatResponse(
            agent=agent_name,
            message=exc_msg,
            success=False,
            error=str(e),
        )

# J4: communicate/coordinate ejecutan agent.process_request directamente. Autorizacion:
# usuario autenticado CON empresa; THALOS (agente de seguridad) solo para superusuario. No existe
# un mapa agente->modulo contratado por empresa (require_module trabaja por vertical/company_type,
# no por agente), asi que no se filtra por modulo. El frontend no usa estas rutas.
_SUPERUSER_ONLY_AGENTS = frozenset({"THALOS"})


def _norm_agent(name: str) -> str:
    return (name or "").strip().upper().replace("-", " ").replace("_", " ")


def _authorize_agent_call(
    db: Session, user: User, agent_names: List[str], include_origin: Optional[str] = None
) -> Dict[str, Any]:
    """Valida empresa del usuario y agentes; devuelve el contexto base del servidor.

    404 si algun agente no existe, 403 si THALOS sin superusuario, 403 si no hay empresa."""
    company_id = chat_db.resolve_company_id(db, user)
    if company_id is None:
        raise HTTPException(status_code=403, detail="Se requiere una empresa asociada al usuario.")
    names = [_norm_agent(n) for n in agent_names]
    if not names:
        raise HTTPException(status_code=422, detail="Debes indicar al menos un agente.")
    registered = {k for k, v in AGENTS.items() if v is not None and k != "ZEUS CORE"}
    to_check = names + ([_norm_agent(include_origin)] if include_origin else [])
    for n in to_check:
        if n not in registered:
            raise HTTPException(status_code=404, detail="Agente no encontrado.")
    for n in names:
        if n in _SUPERUSER_ONLY_AGENTS and not getattr(user, "is_superuser", False):
            raise HTTPException(status_code=403, detail=f"Solo un superusuario puede dirigirse a {n}.")
    return {"company_id": company_id}


def _server_agent_context(db: Session, user: User, client_context: Optional[dict]) -> Dict[str, Any]:
    ctx = build_server_context(db, user, client_context, "agents")
    ctx["requested_by"] = user.email
    ctx.pop("workflow_id", None)
    from services.zeus_global_context import build_agent_company_context

    ctx["zeus_global_context"] = build_agent_company_context(db, user)
    return ctx


def _log_agent_call(
    user: User, company_id: int, action: str, description: str, details: dict, ok: bool,
    correlation_id: Optional[str] = None,
) -> None:
    """communicate/coordinate: un paso ACTUAR con empresa/usuario explicitos y status real.
    Cada llamada lleva su propio correlation_id (no hay cadena conversacional)."""
    import uuid

    log_chain_step(
        "ACTUAR", company_id=company_id, user=user, agent="ZEUS CORE", action=action,
        action_type=action, description=description, status="completed" if ok else "failed",
        details=details, correlation_id=correlation_id or uuid.uuid4().hex,
        priority="normal" if ok else "high", visible_to_client=True,
    )


@router.post("/agents/communicate")
async def communicate_agents(
    request: AgentCommunicationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(thalos_request_guard),
):
    """Comunicacion entre agentes. Identidad/empresa/control los fija el servidor."""
    await asyncio.to_thread(ensure_agent_stack)
    if zeus is None:
        raise HTTPException(status_code=500, detail="ZEUS CORE no está inicializado")

    base = _authorize_agent_call(db, current_user, [request.to_agent], include_origin=request.from_agent)
    company_id = base["company_id"]
    context = _server_agent_context(db, current_user, request.context)
    from_a, to_a = _norm_agent(request.from_agent), _norm_agent(request.to_agent)
    details = {"from_agent": from_a, "to_agent": to_a, "message": request.message[:500]}
    try:
        result = await asyncio.to_thread(
            zeus.communicate_between_agents,
            from_agent=from_a,
            to_agent=to_a,
            message=request.message,
            context=context,
        )
    except Exception:
        logger.exception("agents_communicate fallo %s -> %s", from_a, to_a)
        _log_agent_call(current_user, company_id, "agents_communicate",
                        f"Comunicación entre agentes {from_a} -> {to_a} fallida",
                        {**details, "error": "exception"}, False)
        raise HTTPException(status_code=500, detail="Error interno al comunicar con el agente.")
    ok = isinstance(result, dict) and result.get("success") is not False and not result.get("error")
    _log_agent_call(current_user, company_id, "agents_communicate",
                    f"Comunicación entre agentes {from_a} -> {to_a}", details, ok)
    return result


MAX_COORDINATE_TASK_CHARS = 4000
_COORDINATE_FAIL_MSG = "El agente no pudo completar la tarea."


async def _coordinate_no_confirmation(step) -> Dict[str, Any]:
    # J9e: coordinate nunca ejecuta ni prepara acciones con consecuencias (solo consultas/analisis).
    return {"status": "failed", "message": "Acción no permitida en la coordinación."}


@router.post("/agents/coordinate")
async def coordinate_agents(
    request: MultiAgentTaskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(thalos_request_guard),
):
    """Coordinacion multi-agente. Identidad/empresa/workflow los fija el servidor.

    J9e: unificada con el ejecutor de planes de JARVIS (`jarvis_plan.execute_plan`, J9b): un paso por
    agente pedido, en el orden recibido; control de modulos por paso (J9a), contexto de servidor sin datos
    personales, un registro J7 por paso con el mismo correlation_id y ninguna accion con consecuencias."""
    from services import jarvis_plan as plan_mod

    await asyncio.to_thread(ensure_agent_stack)

    base = _authorize_agent_call(db, current_user, request.required_agents)
    company_id = base["company_id"]
    task = (request.task_description or "").strip()
    if not task or len(task) > MAX_COORDINATE_TASK_CHARS:
        raise HTTPException(status_code=422, detail=f"task_description debe tener entre 1 y {MAX_COORDINATE_TASK_CHARS} caracteres.")
    agents = list(dict.fromkeys(_norm_agent(a) for a in request.required_agents))  # sin duplicados, en orden
    if len(agents) > plan_mod.MAX_STEPS:
        raise HTTPException(status_code=422, detail=f"Maximo {plan_mod.MAX_STEPS} agentes por coordinacion.")
    context = _server_agent_context(db, current_user, request.context)
    details = {"required_agents": agents, "task_description": task[:500]}
    plan = plan_mod.Plan(
        source="coordinate",
        steps=[plan_mod.PlanStep(n=i, agent=a, objective=task, kind="consulta") for i, a in enumerate(agents, 1)],
    )

    def step_context(step, steps):  # el servidor fija quienes son los demas agentes (nunca el cliente)
        return {"multi_agent_task": True, "other_agents": [s.agent for s in steps if s.agent != step.agent]}

    chain, token = begin_chain()
    try:
        try:
            await plan_mod.execute_plan(
                db, current_user, plan, ctx=context, company_id=company_id,
                thread_id=f"coordinate-{chain.correlation_id[:12]}",
                prepare_confirmation=_coordinate_no_confirmation, step_context=step_context,
            )
        except Exception:
            logger.exception("agents_coordinate fallo %s", agents)
            _log_agent_call(current_user, company_id, "agents_coordinate",
                            "Coordinación multiagente fallida", {**details, "error": "exception"}, False,
                            correlation_id=chain.correlation_id)
            raise HTTPException(status_code=500, detail="Error interno al coordinar agentes.")
        for s in plan.steps:  # nunca se devuelve al cliente el texto de un error interno del agente
            if s.status in ("failed", "skipped"):
                s.reason = s.summary = _COORDINATE_FAIL_MSG
        out = plan_mod.build_response(plan)
        results = {
            s.agent: {
                "success": s.status == "done", "status": s.status, "step": s.n,
                "message": s.text if s.status == "done" else "", "content": s.text if s.status == "done" else "",
                **({} if s.status == "done" else {"error": s.summary}),
            }
            for s in plan.steps
        }
        ok = all(s.status == "done" for s in plan.steps)
        _log_agent_call(current_user, company_id, "agents_coordinate",
                        "Coordinación multiagente ejecutada", details, ok, correlation_id=chain.correlation_id)
        return {
            "success": ok, "task": task, "agents_involved": agents, "results": results,
            "coordinated_by": "ZEUS CORE", "teamflow_execution": None,
            "plan_source": "coordinate", "steps": out["steps"], "message": out["message"],
            "executed": False, "needs_confirmation": False,
        }
    finally:
        end_chain(token)


@router.get("/health")
async def chat_health():
    """Health check para el servicio de chat (no fuerza carga de agentes si aún no se ha usado el stack)."""
    if not _agents_ready:
        return {
            "status": "healthy",
            "agents": {k: "lazy_pending" for k in AGENT_ORDER_KEYS},
        }
    agents_status = {
        name: "initialized" if agent is not None else "error"
        for name, agent in AGENTS.items()
    }
    return {
        "status": "healthy",
        "agents": agents_status,
    }


@router.get("/panel/executions")
async def executions_panel(current_user: User = Depends(get_current_active_user)):
    """Panel de control consolidado de ZEUS CORE.

    H-04: antes respondía 200 SIN token y exponía estado compartido entre tenants
    (`execution_snapshots` en memoria de proceso y qué integraciones están configuradas).
    Ahora exige autenticación y rol de superusuario. El frontend no lo usa.
    """
    if not getattr(current_user, "is_superuser", False):
        raise HTTPException(
            status_code=403,
            detail="Solo un superusuario puede consultar el panel de ejecuciones.",
        )
    await asyncio.to_thread(ensure_agent_stack)
    if zeus is None:
        raise HTTPException(status_code=500, detail="ZEUS CORE no está disponible")
    return {
        "success": True,
        "panel": zeus.get_execution_panel(),
    }

