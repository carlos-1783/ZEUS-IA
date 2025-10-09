"""
Health Check endpoints para monitoreo
"""
from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.config import settings
import psutil
import os

router = APIRouter()

@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check básico"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT
    }

@router.get("/health/detailed")
async def detailed_health_check(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Health check detallado con métricas del sistema"""
    
    # Verificar base de datos
    db_status = "healthy"
    try:
        db.execute("SELECT 1")
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    # Métricas del sistema
    system_metrics = {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage('/').percent,
        "load_average": os.getloadavg() if hasattr(os, 'getloadavg') else None
    }
    
    # Verificar variables de entorno críticas
    env_check = {
        "database_url": "configured" if settings.DATABASE_URL else "missing",
        "secret_key": "configured" if settings.SECRET_KEY else "missing",
        "cors_origins": len(settings.BACKEND_CORS_ORIGINS) if settings.BACKEND_CORS_ORIGINS else 0
    }
    
    return {
        "status": "healthy" if db_status == "healthy" else "unhealthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "database": db_status,
        "system": system_metrics,
        "environment_variables": env_check
    }

@router.get("/health/ready")
async def readiness_check(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Readiness check para Kubernetes/Docker"""
    try:
        # Verificar base de datos
        db.execute("SELECT 1")
        
        # Verificar variables críticas
        if not settings.DATABASE_URL or not settings.SECRET_KEY:
            raise HTTPException(
                status_code=503,
                detail="Service not ready: missing critical configuration"
            )
        
        return {
            "status": "ready",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Service not ready: {str(e)}"
        )

@router.get("/health/live")
async def liveness_check() -> Dict[str, Any]:
    """Liveness check para Kubernetes/Docker"""
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat()
    }