# ========================================
# NÚCLEO ZEUS-IA - ENDPOINTS DEL SISTEMA
# ========================================

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import logging

from app.core.zeus_agents import zeus_manager, AgentType
from app.core.auth import get_current_active_user
from app.models.user import User
from app.db.base import get_db

router = APIRouter()
logger = logging.getLogger(__name__)

# ========================================
# MODELOS DE DATOS
# ========================================

class ZeusCommand(BaseModel):
    """Modelo para comandos del Núcleo ZEUS"""
    command: str = Field(..., description="Comando del Núcleo ZEUS")
    data: Optional[Dict[str, Any]] = Field(None, description="Datos adicionales para el comando")
    
    class Config:
        json_schema_extra = {
            "example": {
                "command": "ZEUS.ACTIVAR",
                "data": {
                    "user_id": "123",
                    "session_id": "abc456"
                }
            }
        }

class ZeusResponse(BaseModel):
    """Modelo de respuesta del Núcleo ZEUS"""
    status: str
    message: str
    agent: str
    timestamp: str
    animation: Optional[str] = None
    voice: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

# ========================================
# ENDPOINTS DEL NÚCLEO ZEUS
# ========================================

@router.post(
    "/activate",
    response_model=ZeusResponse,
    operation_id="zeus_activate_api_v1",
    summary="Activar Núcleo ZEUS",
    description="Activa todos los agentes del Núcleo ZEUS-IA",
    response_description="Estado de activación del sistema"
)
async def activate_zeus_core(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Activa el Núcleo ZEUS completo con todos sus agentes especializados.
    
    **Agentes activados:**
    - ZEUS: Núcleo principal
    - THALOS: Seguridad y protección
    - JUSTICIA: Ética y cumplimiento
    - RAFAEL: Salud y bienestar
    - ANÁLISIS: Análisis de datos
    - IA: Inteligencia artificial
    """
    try:
        logger.info(f"Activando Núcleo ZEUS para usuario: {current_user.email}")
        
        result = zeus_manager.activate_all_agents()
        
        # Log de activación
        logger.info(f"Núcleo ZEUS activado exitosamente para {current_user.email}")
        
        return ZeusResponse(**result)
        
    except Exception as e:
        logger.error(f"Error activando Núcleo ZEUS: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error activando Núcleo ZEUS: {str(e)}"
        )

@router.post(
    "/execute",
    response_model=ZeusResponse,
    operation_id="zeus_execute_api_v1",
    summary="Ejecutar Comando ZEUS",
    description="Ejecuta un comando específico del Núcleo ZEUS",
    response_description="Resultado de la ejecución del comando"
)
async def execute_zeus_command(
    command_data: ZeusCommand,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Ejecuta un comando específico del Núcleo ZEUS.
    
    **Comandos disponibles:**
    
    **ZEUS (Núcleo principal):**
    - ZEUS.ACTIVAR: Activar sistema completo
    - ZEUS.ANALIZAR: Análisis del sistema
    - ZEUS.EJECUTAR: Ejecutar operación
    - ZEUS.SEGURIDAD: Verificación de seguridad
    - ZEUS.REGLAS: Aplicar reglas
    - ZEUS.BIENESTAR: Verificación de bienestar
    
    **THALOS (Seguridad):**
    - THALOS.PROTEGER: Activar protección
    - THALOS.ESCANEAR: Escaneo de seguridad
    
    **JUSTICIA (Ética):**
    - JUSTICIA.VERIFICAR: Verificación ética
    
    **RAFAEL (Salud):**
    - RAFAEL.SALUD: Verificación de salud
    
    **ANÁLISIS (Datos):**
    - ANALISIS.PROCESAR: Procesar datos
    
    **IA (Inteligencia):**
    - IA.PROCESAR: Procesamiento de IA
    """
    try:
        logger.info(f"Ejecutando comando ZEUS: {command_data.command} para usuario: {current_user.email}")
        
        result = zeus_manager.execute_zeus_command(
            command_data.command,
            command_data.data or {}
        )
        
        # Log del comando
        logger.info(f"Comando ZEUS ejecutado: {command_data.command} - Resultado: {result.get('status')}")
        
        return ZeusResponse(**result)
        
    except Exception as e:
        logger.error(f"Error ejecutando comando ZEUS: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error ejecutando comando: {str(e)}"
        )

@router.get(
    "/status",
    operation_id="zeus_status_api_v1",
    summary="Estado del Núcleo ZEUS",
    description="Obtiene el estado completo del Núcleo ZEUS y todos sus agentes",
    response_description="Estado detallado del sistema"
)
async def get_zeus_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Obtiene el estado completo del Núcleo ZEUS y todos sus agentes.
    
    **Información incluida:**
    - Estado del sistema
    - Estado de cada agente
    - Actividad reciente
    - Logs del sistema
    """
    try:
        logger.info(f"Obteniendo estado ZEUS para usuario: {current_user.email}")
        
        status = zeus_manager.get_system_status()
        
        return {
            "status": "success",
            "message": "Estado del Núcleo ZEUS obtenido correctamente",
            "timestamp": status["timestamp"],
            "data": status
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo estado ZEUS: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo estado: {str(e)}"
        )

@router.get(
    "/agents",
    operation_id="zeus_agents_api_v1",
    summary="Listar Agentes ZEUS",
    description="Lista todos los agentes disponibles del Núcleo ZEUS",
    response_description="Lista de agentes disponibles"
)
async def list_zeus_agents(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Lista todos los agentes disponibles del Núcleo ZEUS.
    
    **Agentes disponibles:**
    - ZEUS: Núcleo principal
    - THALOS: Seguridad y protección
    - JUSTICIA: Ética y cumplimiento
    - RAFAEL: Salud y bienestar
    - ANÁLISIS: Análisis de datos
    - IA: Inteligencia artificial
    """
    try:
        agents_info = []
        
        for agent_type, agent in zeus_manager.agents.items():
            agents_info.append({
                "type": agent_type.value,
                "name": agent.name,
                "description": agent.description,
                "status": agent.status.value,
                "last_activity": agent.last_activity.isoformat() if agent.last_activity else None,
                "logs_count": len(agent.logs)
            })
        
        return {
            "status": "success",
            "message": "Agentes ZEUS listados correctamente",
            "timestamp": zeus_manager.get_system_status()["timestamp"],
            "data": {
                "agents": agents_info,
                "total_agents": len(agents_info)
            }
        }
        
    except Exception as e:
        logger.error(f"Error listando agentes ZEUS: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listando agentes: {str(e)}"
        )

@router.get(
    "/commands",
    operation_id="zeus_commands_api_v1",
    summary="Comandos Disponibles",
    description="Lista todos los comandos disponibles del Núcleo ZEUS",
    response_description="Lista de comandos disponibles"
)
async def list_zeus_commands(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Lista todos los comandos disponibles del Núcleo ZEUS.
    
    **Comandos por agente:**
    - ZEUS: Comandos del núcleo principal
    - THALOS: Comandos de seguridad
    - JUSTICIA: Comandos de ética
    - RAFAEL: Comandos de salud
    - ANÁLISIS: Comandos de análisis
    - IA: Comandos de inteligencia artificial
    """
    try:
        commands = {
            "ZEUS": [
                "ZEUS.ACTIVAR",
                "ZEUS.ANALIZAR", 
                "ZEUS.EJECUTAR",
                "ZEUS.SEGURIDAD",
                "ZEUS.REGLAS",
                "ZEUS.BIENESTAR"
            ],
            "THALOS": [
                "THALOS.PROTEGER",
                "THALOS.ESCANEAR"
            ],
            "JUSTICIA": [
                "JUSTICIA.VERIFICAR"
            ],
            "RAFAEL": [
                "RAFAEL.SALUD"
            ],
            "ANALISIS": [
                "ANALISIS.PROCESAR"
            ],
            "IA": [
                "IA.PROCESAR"
            ]
        }
        
        return {
            "status": "success",
            "message": "Comandos ZEUS listados correctamente",
            "timestamp": zeus_manager.get_system_status()["timestamp"],
            "data": {
                "commands": commands,
                "total_commands": sum(len(cmd_list) for cmd_list in commands.values())
            }
        }
        
    except Exception as e:
        logger.error(f"Error listando comandos ZEUS: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listando comandos: {str(e)}"
        )
