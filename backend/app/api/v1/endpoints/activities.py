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

    Nota de seguridad (AUDIT_FIX_THALOS_SHIELD.md, sección 13): este endpoint
    no tenía NINGUNA autenticación y aceptaba `user_email` arbitrario del
    cliente. `AgentAutomationExecutor` (services/automation/agent_executor.py)
    recoge en segundo plano cualquier `AgentActivity` con `status in
    ("pending", "in_progress")` y la ejecuta vía `resolve_handler`, incluidos
    los handlers reales de THALOS v1
    (`services/automation/handlers/thalos_v1.py`, que llaman a
    `execute_action("detect_suspicious_activity"/"block_user"/...)` y a
    `run_monitoring_cycle` — el mismo motor `scan_logs`/`run_monitor_cycle`
    protegido en el resto de este documento). Sin autenticación ni un
    `user_email` fiable, cualquiera (sin cuenta) podía encolar una actividad
    `agent_name="THALOS"`, `action_type="detect_suspicious_activity"` (o
    `"block_user"` con un `company_id`/`user_email` de otra empresa) y, en
    cuanto `THALOS_EXECUTION_ENABLED`/`THALOS_AUTO_BLOCK` se activaran, el
    executor en segundo plano la ejecutaría sin ningún control de tenant ni de
    rol. Ahora requiere autenticación real y el `user_email` se deriva
    siempre del usuario autenticado (`current_user.email`), ignorando el
    valor que envíe el cliente — mismo patrón de "no confiar en datos de
    autorización del cliente" ya aplicado a `body.company_id` en
    `thalos_v1.py`. Se complementa con el gate de superusuario añadido
    directamente en los handlers de THALOS v1 (ver
    `services/automation/handlers/thalos_v1.py`), para que ni siquiera un
    usuario autenticado no-superusuario pueda disparar el motor global por
    esta vía asíncrona.
    """
    try:
        result = ActivityLogger.log_activity(
            agent_name=activity.agent_name.upper(),
            action_type=activity.action_type,
            action_description=activity.action_description,
            details=activity.details,
            metrics=activity.metrics,
            user_email=current_user.email,
            status=activity.status,
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

