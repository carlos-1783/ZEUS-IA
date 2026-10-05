"""
📊 Agent Activities Endpoints
Endpoints para consultar actividades y métricas de agentes
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.agent_activity import AgentActivity
from app.core.auth import get_current_active_user
from app.models.user import User
from services.activity_logger import ActivityLogger, ensure_tables_initialized, tables_ready

CLIENT_LOG_ORIGIN = "client_log"
EXECUTABLE_STATUSES = frozenset({"pending", "in_progress"})

router = APIRouter()

# ============================================================================
# MODELS
# ============================================================================

class ActivityCreate(BaseModel):
    agent_name: str
    action_type: str
    action_description: str
    details: Optional[Dict[str, Any]] = None
    metrics: Optional[Dict[str, Any]] = None
    user_email: Optional[str] = None
    status: str = "completed"
    priority: str = "normal"

# ============================================================================
# HELPERS
# ============================================================================

def get_db():
    db = SessionLocal()
    try:
        if not tables_ready():
            ensure_tables_initialized()
        yield db
    finally:
        db.close()

# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/{agent_name}")
async def get_agent_activities(
    agent_name: str,
    user_email: Optional[str] = None,
    limit: int = 50,
    days: int = 7,
    current_user: User = Depends(get_current_active_user),
):
    """
    Obtener actividades recientes de un agente
    
    Args:
        agent_name: Nombre del agente (ZEUS, PERSEO, RAFAEL, THALOS, JUSTICIA)
        user_email: Filtrar por usuario específico (opcional)
        limit: Número máximo de resultados
        days: Días hacia atrás
        
    Returns:
        Lista de actividades
    """
    try:
        # Aislamiento multiempresa: usuario normal solo ve su propio email.
        effective_user_email = user_email if getattr(current_user, "is_superuser", False) else current_user.email
        activities = ActivityLogger.get_agent_activities(
            agent_name=agent_name.upper(),
            user_email=effective_user_email,
            limit=limit,
            days=days
        )
        
        return {
            "success": True,
            "agent_name": agent_name.upper(),
            "total_activities": len(activities),
            "activities": [
                {
                    "id": activity.id,
                    "action_type": activity.action_type,
                    "description": activity.action_description,
                    "status": activity.status,
                    "priority": activity.priority,
                    "details": activity.details,
                    "metrics": activity.metrics,
                    "created_at": activity.created_at.isoformat(),
                    "completed_at": activity.completed_at.isoformat() if activity.completed_at else None
                }
                for activity in activities
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener actividades: {str(e)}"
        )

@router.get("/{agent_name}/metrics")
async def get_agent_metrics(
    agent_name: str,
    user_email: Optional[str] = None,
    days: int = 30,
    current_user: User = Depends(get_current_active_user),
):
    """
    Obtener métricas agregadas de un agente
    
    Args:
        agent_name: Nombre del agente
        user_email: Filtrar por usuario (opcional)
        days: Período de tiempo
        
    Returns:
        Métricas del agente
    """
    try:
        if not tables_ready():
            ensure_tables_initialized()
        effective_user_email = user_email if getattr(current_user, "is_superuser", False) else current_user.email

        metrics = ActivityLogger.get_agent_metrics(
            agent_name=agent_name.upper(),
            user_email=effective_user_email,
            days=days
        )
        
        return {
            "success": True,
            **metrics
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener métricas: {str(e)}"
        )

@router.post("/log")
async def log_activity(
    activity: ActivityCreate,
    current_user: User = Depends(get_current_active_user),
):
    """
    Registrar una nueva actividad de agente

    Args:
        activity: Datos de la actividad

    Returns:
        Actividad creada

    Nota de seguridad: el campo `user_email` del payload es libremente
    manipulable por el llamante y no puede usarse como fuente de verdad para
    atribuir la actividad. Un usuario normal solo puede registrar actividad
    a su propio nombre (se ignora cualquier `user_email` distinto en el
    payload); solo un superusuario puede registrar actividad en nombre de
    otro email (uso legítimo: procesos internos/administrativos).

    Nota de seguridad adicional (AUDIT_FIX_THALOS_SHIELD.md, sección 13):
    este endpoint no tenía NINGUNA autenticación antes del fix de arriba, y
    `AgentAutomationExecutor` (services/automation/agent_executor.py) recoge
    en segundo plano cualquier `AgentActivity` con `status in ("pending",
    "in_progress")` y la ejecuta vía `resolve_handler`, incluidos los
    handlers reales de THALOS v1 (`services/automation/handlers/thalos_v1.py`,
    que llaman a `execute_action("detect_suspicious_activity"/"block_user"/...)`
    y a `run_monitoring_cycle`). Sin autenticación, cualquiera (sin cuenta)
    podía encolar una actividad `agent_name="THALOS"`,
    `action_type="detect_suspicious_activity"` (o `"block_user"` con un
    `company_id`/`user_email` de otra empresa) y, en cuanto
    `THALOS_EXECUTION_ENABLED`/`THALOS_AUTO_BLOCK` se activaran, el executor
    en segundo plano la ejecutaría sin ningún control de tenant ni de rol.
    Como defensa en profundidad adicional, los propios handlers de THALOS v1
    (ver `services/automation/handlers/thalos_v1.py`) gatean por superusuario
    la ejecución real — así que incluso si `effective_user_email` permitiera
    a un superusuario spoofear el email en este endpoint, el motor global no
    se dispara para nadie que no sea superusuario en el momento de la
    ejecución real.
    """
    try:
        is_superuser = getattr(current_user, "is_superuser", False)
        effective_user_email = (
            activity.user_email if (is_superuser and activity.user_email) else current_user.email
        )
        # J3c: este endpoint es un LOG, no una cola de ejecucion para clientes. La marca de
        # origen la fija SIEMPRE el servidor (sobrescribe cualquier `_origin` del cliente) y
        # el executor rechaza `client_log`. Ademas, un no superusuario no puede dejar la
        # actividad en un estado ejecutable (pending/in_progress): se registra como "logged".
        # Un superusuario conserva la capacidad de encolar (uso administrativo documentado).
        safe_details = dict(activity.details) if isinstance(activity.details, dict) else {}
        safe_status = activity.status
        if is_superuser:
            safe_details["_origin"] = "superuser_log"
        else:
            safe_details["_origin"] = CLIENT_LOG_ORIGIN
            if (safe_status or "").strip().lower() in EXECUTABLE_STATUSES:
                safe_details["_requested_status"] = safe_status
                safe_status = "logged"
        result = ActivityLogger.log_activity(
            agent_name=activity.agent_name.upper(),
            action_type=activity.action_type,
            action_description=activity.action_description,
            details=safe_details,
            metrics=activity.metrics,
            user_email=effective_user_email,
            status=safe_status,
            priority=activity.priority
        )
        
        if not result:
            raise HTTPException(
                status_code=500,
                detail="Error al crear actividad"
            )
        
        return {
            "success": True,
            "activity_id": result.id,
            "message": "Actividad registrada correctamente"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al registrar actividad: {str(e)}"
        )

@router.get("/all/summary")
async def get_all_agents_summary(
    user_email: Optional[str] = None,
    days: int = 7,
    current_user: User = Depends(get_current_active_user),
):
    """
    Obtener resumen de actividades de todos los agentes
    
    Args:
        user_email: Filtrar por usuario (opcional)
        days: Días hacia atrás
        
    Returns:
        Resumen por agente
    """
    try:
        agents = ["ZEUS", "PERSEO", "RAFAEL", "THALOS", "JUSTICIA", "AFRODITA"]
        effective_user_email = user_email if getattr(current_user, "is_superuser", False) else current_user.email
        
        summary = {}
        
        for agent in agents:
            metrics = ActivityLogger.get_agent_metrics(
                agent_name=agent,
                user_email=effective_user_email,
                days=days
            )
            summary[agent] = metrics
        
        return {
            "success": True,
            "period_days": days,
            "agents": summary
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener resumen: {str(e)}"
        )

