"""
Endpoint para chat con agentes IA
"""
import logging
import os
import sys
import threading
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db

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

class AgentCommunicationRequest(BaseModel):
    from_agent: str
    to_agent: str
    message: str
    context: Optional[dict] = None

class MultiAgentTaskRequest(BaseModel):
    task_description: str
    required_agents: List[str]
    context: Optional[dict] = None

@router.post("/{agent_name}/chat", response_model=ChatResponse)
async def chat_with_agent(
    agent_name: str,
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Chat con un agente específico
    
    Args:
        agent_name: Nombre del agente (ZEUS CORE, PERSEO, RAFAEL, THALOS, JUSTICIA)
        request: Mensaje y contexto opcional
    
    Returns:
        Respuesta del agente
    """
    ensure_agent_stack()

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
    
    try:
        from services.unified_agent_runtime import run_chat

        context = request.context or {}
        context["user_message"] = request.message
        context.setdefault("user_id", current_user.id)
        context.setdefault("user_email", current_user.email)
        thread_id = request.thread_id or context.get("thread_id") or "main"
        company_id = context.get("company_id") or context.get("user_email")

        result = run_chat(
            agent_name=agent_name,
            thread_id=thread_id,
            message=request.message,
            company_id=company_id,
            context=context,
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
                                    pl["content"] = c
                                    wd.document_payload = pl
                                    db.add(wd)
                                    db.commit()
                                from services.perseo_chat_video_job import (
                                    run_perseo_chat_video_generation,
                                )

                                background_tasks.add_task(
                                    run_perseo_chat_video_generation,
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

            ActivityLogger.log_activity(
                agent_name=agent_name,
                action_type="chat_request_processed",
                action_description=f"Chat procesado por {agent_name}",
                details={
                    "request_type": "chat",
                    "thread_id": thread_id,
                    "user_id": current_user.id,
                    "workspace_document_id": workspace_document_id,
                },
                metrics={"chat_messages": 1},
                user_email=current_user.email,
                status="completed",
                priority="normal",
                visible_to_client=True,
            )
            return ChatResponse(
                agent=agent_name,
                message=result.get("message", "Sin respuesta"),
                success=True,
                confidence=result.get("confidence"),
                hitl_required=result.get("hitl_required", False),
                workspace_document_id=workspace_document_id,
            )
        ActivityLogger.log_activity(
            agent_name=agent_name,
            action_type="chat_request_failed",
            action_description=f"Chat fallido en {agent_name}",
            details={
                "error": result.get("error"),
                "request_type": "chat",
                "thread_id": thread_id,
                "user_id": current_user.id,
            },
            metrics={"chat_failures": 1},
            user_email=current_user.email,
            status="failed",
            priority="normal",
            visible_to_client=True,
        )
        fail_msg = (result.get("message") or "").strip() or (
            result.get("error") or ""
        ).strip() or f"Error: {result.get('error', 'Error desconocido')}"
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
        ActivityLogger.log_activity(
            agent_name=agent_name,
            action_type="chat_request_exception",
            action_description=f"Excepción en chat {agent_name}",
            details={"error": str(e), "request_type": "chat", "user_id": current_user.id},
            metrics={"chat_exceptions": 1},
            user_email=current_user.email,
            status="failed",
            priority="high",
            visible_to_client=True,
        )
        return ChatResponse(
            agent=agent_name,
            message=f"Error interno: {str(e)}",
            success=False,
            error=str(e),
        )

@router.post("/agents/communicate")
async def communicate_agents(request: AgentCommunicationRequest):
    """
    Endpoint para comunicación entre agentes
    
    Args:
        request: Solicitud de comunicación entre agentes
    
    Returns:
        Respuesta del agente destino
    """
    ensure_agent_stack()
    if zeus is None:
        raise HTTPException(
            status_code=500,
            detail="ZEUS CORE no está inicializado"
        )
    
    result = zeus.communicate_between_agents(
        from_agent=request.from_agent,
        to_agent=request.to_agent,
        message=request.message,
        context=request.context or {}
    )
    
    return result

@router.post("/agents/coordinate")
async def coordinate_agents(request: MultiAgentTaskRequest):
    """
    Endpoint para coordinar tareas multi-agente
    
    Args:
        request: Solicitud de coordinación multi-agente
    
    Returns:
        Resultados de todos los agentes
    """
    ensure_agent_stack()
    if zeus is None:
        raise HTTPException(
            status_code=500,
            detail="ZEUS CORE no está inicializado"
        )
    
    result = zeus.coordinate_multi_agent_task(
        task_description=request.task_description,
        required_agents=request.required_agents,
        context=request.context or {}
    )
    
    return result

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
async def executions_panel():
    """Panel de control consolidado de ZEUS CORE."""
    ensure_agent_stack()
    if zeus is None:
        raise HTTPException(status_code=500, detail="ZEUS CORE no está disponible")
    return {
        "success": True,
        "panel": zeus.get_execution_panel(),
    }

