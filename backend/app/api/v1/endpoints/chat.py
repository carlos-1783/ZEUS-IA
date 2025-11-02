"""
Endpoint para chat con agentes IA
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
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

router = APIRouter()

# Instancias de agentes
try:
    zeus = ZeusCore()
    perseo = Perseo()
    rafael = Rafael()
    thalos = Thalos()
    justicia = Justicia()
    
    # Registrar agentes en ZEUS
    zeus.register_agent(perseo)
    zeus.register_agent(rafael)
    zeus.register_agent(thalos)
    zeus.register_agent(justicia)
    
    print("✅ Todos los agentes inicializados correctamente")
except Exception as e:
    print(f"❌ Error inicializando agentes: {e}")
    zeus = perseo = rafael = thalos = justicia = None

# Mapeo de agentes
AGENTS = {
    "ZEUS CORE": zeus,
    "PERSEO": perseo,
    "RAFAEL": rafael,
    "THALOS": thalos,
    "JUSTICIA": justicia
}

class ChatRequest(BaseModel):
    message: str
    context: Optional[dict] = None

class ChatResponse(BaseModel):
    agent: str
    message: str
    success: bool
    confidence: Optional[float] = None
    hitl_required: Optional[bool] = None
    error: Optional[str] = None

@router.post("/{agent_name}/chat", response_model=ChatResponse)
async def chat_with_agent(agent_name: str, request: ChatRequest):
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
        # Procesar solicitud
        context = request.context or {}
        context["user_message"] = request.message
        
        # Obtener respuesta del agente
        result = agent.process_request(context)
        
        # Extraer respuesta
        if result.get("success"):
            return ChatResponse(
                agent=agent_name,
                message=result.get("content", result.get("response", "Sin respuesta")),
                success=True,
                confidence=result.get("confidence"),
                hitl_required=result.get("human_approval_required", False)
            )
        else:
            return ChatResponse(
                agent=agent_name,
                message=f"Error: {result.get('error', 'Error desconocido')}",
                success=False,
                error=result.get("error")
            )
            
    except Exception as e:
        print(f"❌ Error en chat con {agent_name}: {e}")
        import traceback
        traceback.print_exc()
        
        return ChatResponse(
            agent=agent_name,
            message=f"Error interno: {str(e)}",
            success=False,
            error=str(e)
        )

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

