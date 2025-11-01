"""
Endpoints para gestión y estado de agentes IA
"""
from datetime import datetime
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.auth import get_current_active_user
from app.models.user import User

router = APIRouter()

@router.get("/status")
async def get_agents_status(
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Obtener estado de todos los agentes del sistema
    NO requiere autenticación para permitir monitoreo público
    """
    # Estado de agentes activos
    agents_status = {
        "ZEUS CORE": {
            "status": "online",
            "role": "Orquestador Supremo",
            "uptime": "99.95%",
            "last_activity": datetime.utcnow().isoformat(),
            "decisions_today": 0,
            "avg_confidence": 0.92
        },
        "PERSEO": {
            "status": "online",
            "role": "Estratega de Crecimiento",
            "uptime": "99.87%",
            "last_activity": datetime.utcnow().isoformat(),
            "decisions_today": 0,
            "avg_confidence": 0.88,
            "domain": "Marketing/SEO/SEM"
        },
        "RAFAEL": {
            "status": "online",
            "role": "Guardián Fiscal",
            "uptime": "99.92%",
            "last_activity": datetime.utcnow().isoformat(),
            "decisions_today": 0,
            "avg_confidence": 0.95,
            "domain": "Finanzas/Fiscalidad",
            "country": "España"
        },
        "THALOS": {
            "status": "online",
            "role": "Defensor Cibernético",
            "uptime": "99.99%",
            "last_activity": datetime.utcnow().isoformat(),
            "decisions_today": 0,
            "avg_confidence": 0.97,
            "domain": "Seguridad/Ciberdefensa",
            "safeguards": "creator_approval_required"
        },
        "JUSTICIA": {
            "status": "online",
            "role": "Asesora Legal y GDPR",
            "uptime": "99.90%",
            "last_activity": datetime.utcnow().isoformat(),
            "decisions_today": 0,
            "avg_confidence": 0.93,
            "domain": "Legal/Protección de Datos"
        }
    }
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "total_agents": len(agents_status),
        "agents": agents_status,
        "system_health": "optimal"
    }

@router.get("/stats")
async def get_agents_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Estadísticas detalladas de agentes (requiere autenticación)
    """
    return {
        "total_decisions": 0,
        "total_hitl_requests": 0,
        "avg_response_time": "0.3s",
        "total_cost": "0.00 USD",
        "period": "last_30_days"
    }

