"""
Endpoint para chat con agentes IA
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
import sys
import os

# Agregar el directorio raíz al path para importar agentes
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

from agents.zeus_core import ZeusCore
from agents.perseo import Perseo
from agents.rafael import Rafael
from agents.thalos import Thalos
from agents.justicia import Justicia
from agents.afrodita import Afrodita
from services.teamflow_engine import teamflow_engine
from app.core.auth import get_current_active_user
from app.models.user import User
from services.activity_logger import ActivityLogger

router = APIRouter()

# Instancias de agentes
try:
    print("🔄 Inicializando ZEUS CORE...")
    zeus = ZeusCore()
    print("✅ ZEUS CORE OK")
    zeus.set_teamflow_engine(teamflow_engine)
    
    print("🔄 Inicializando PERSEO...")
    perseo = Perseo()
    print("✅ PERSEO OK")
    
    print("🔄 Inicializando RAFAEL...")
    rafael = Rafael()
    print("✅ RAFAEL OK")
    
    print("🔄 Inicializando THALOS...")
    thalos = Thalos()
    print("✅ THALOS OK")
    
    print("🔄 Inicializando JUSTICIA...")
    justicia = Justicia()
    print("✅ JUSTICIA OK")
    
    print("🔄 Inicializando AFRODITA...")
    afrodita = Afrodita()
    print("✅ AFRODITA OK")
    
    # Registrar agentes en ZEUS y establecer referencias para comunicación
    zeus.register_agent(perseo)
    zeus.register_agent(rafael)
    zeus.register_agent(thalos)
    zeus.register_agent(justicia)
    zeus.register_agent(afrodita)
    
    # Establecer referencia a ZEUS CORE en todos los agentes para comunicación entre ellos
    perseo.set_zeus_core_ref(zeus)
    rafael.set_zeus_core_ref(zeus)
    thalos.set_zeus_core_ref(zeus)
    justicia.set_zeus_core_ref(zeus)
    afrodita.set_zeus_core_ref(zeus)
    
    # Asegurar que el plan pre-lanzamiento esté inicializado
    try:
        plan_result = zeus.ensure_prelaunch_plan()
        if plan_result.get("success"):
            print("✅ Plan pre-lanzamiento preparado automáticamente.")
    except Exception as prelaunch_error:
        print(f"⚠️ No se pudo preparar el plan pre-lanzamiento automáticamente: {prelaunch_error}")

    # Conectar TPV service con agentes
    try:
        from services.tpv_service import set_tpv_integrations

        set_tpv_integrations(
            rafael=rafael,
            justicia=justicia,
            afrodita=afrodita,
        )
        print("✅ Integraciones TPV configuradas")
    except Exception as tpv_error:
        print(f"⚠️ Error configurando integraciones TPV: {tpv_error}")

    print("✅ Todos los agentes inicializados correctamente")
except Exception as e:
    print(f"❌ Error inicializando agentes: {e}")
    import traceback
    print("📋 Traceback completo:")
    traceback.print_exc()
    zeus = perseo = rafael = thalos = justicia = afrodita = None

# Mapeo de agentes
AGENTS = {
    "ZEUS CORE": zeus,
    "PERSEO": perseo,
    "RAFAEL": rafael,
    "THALOS": thalos,
    "JUSTICIA": justicia,
    "AFRODITA": afrodita
}

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
    current_user: User = Depends(get_current_active_user),
):
    """
    Chat con un agente específico
    
    Args:
        agent_name: Nombre del agente (ZEUS CORE, PERSEO, RAFAEL, THALOS, JUSTICIA)
        request: Mensaje y contexto opcional
    
    Returns:
        Respuesta del agente
    """
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
            ActivityLogger.log_activity(
                agent_name=agent_name,
                action_type="chat_request_processed",
                action_description=f"Chat procesado por {agent_name}",
                details={
                    "request_type": "chat",
                    "thread_id": thread_id,
                    "user_id": current_user.id,
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
        return ChatResponse(
            agent=agent_name,
            message=result.get("message", f"Error: {result.get('error', 'Error desconocido')}"),
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
    """Health check para el servicio de chat"""
    agents_status = {
        name: "initialized" if agent is not None else "error"
        for name, agent in AGENTS.items()
    }
    
    return {
        "status": "healthy",
        "agents": agents_status
    }


@router.get("/panel/executions")
async def executions_panel():
    """Panel de control consolidado de ZEUS CORE."""
    if zeus is None:
        raise HTTPException(status_code=500, detail="ZEUS CORE no está disponible")
    return {
        "success": True,
        "panel": zeus.get_execution_panel(),
    }

