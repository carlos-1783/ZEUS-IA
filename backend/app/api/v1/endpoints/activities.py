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
    days: int = 7
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
        activities = ActivityLogger.get_agent_activities(
            agent_name=agent_name.upper(),
            user_email=user_email,
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
    days: int = 30
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

        metrics = ActivityLogger.get_agent_metrics(
            agent_name=agent_name.upper(),
            user_email=user_email,
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
async def log_activity(activity: ActivityCreate):
    """
    Registrar una nueva actividad de agente
    
    Args:
        activity: Datos de la actividad
        
    Returns:
        Actividad creada
    """
    try:
        result = ActivityLogger.log_activity(
            agent_name=activity.agent_name.upper(),
            action_type=activity.action_type,
            action_description=activity.action_description,
            details=activity.details,
            metrics=activity.metrics,
            user_email=activity.user_email,
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
    days: int = 7
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
        agents = ["ZEUS", "PERSEO", "RAFAEL", "THALOS", "JUSTICIA"]
        
        summary = {}
        
        for agent in agents:
            metrics = ActivityLogger.get_agent_metrics(
                agent_name=agent,
                user_email=user_email,
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

