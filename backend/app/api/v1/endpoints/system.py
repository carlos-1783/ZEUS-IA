from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import Dict, Any
import logging

from app.db.session import get_db
from app.models.user import User
from app.core.state_manager import state_manager
from app.core.auth import get_current_active_user as get_current_user

router = APIRouter()

# Configuración de logging
logger = logging.getLogger(__name__)

@router.get(
    "/status",
    response_model=Dict[str, Any],
    operation_id="system_status_api_v1",
    summary="Get System Status",
    description="""
    Obtiene el estado actual del sistema.
    Incluye información sobre la empresa activa, módulos habilitados y estado general.
    
    Requiere autenticación.
    """,
    response_description="Estado actual del sistema"
)
async def get_system_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        logger.info(f"Obteniendo estado del sistema para usuario: {current_user.email}")
        
        # Verificar que el state manager esté inicializado
        if not hasattr(state_manager, 'get_state'):
            logger.error("State manager no inicializado correctamente")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="El state manager no está inicializado correctamente"
            )
        
        # Obtener el estado actual
        state = state_manager.get_state()
        logger.info(f"Estado actual del sistema: {state}")
        
        # Preparar la respuesta
        response_data = {
            "status": "success",
            "data": {
                "sistema_activo": state.get("empresa_activada", False),
                "empresa_actual": state.get("empresa_actual", ""),
                "modulos_activos": state.get("modulos_activos", []),
                "ultima_activacion": state.get("ultima_activacion"),
                "version": state.get("version", "1.0.0"),
                "usuario_actual": {
                    "email": current_user.email,
                    "is_admin": current_user.is_superuser
                }
            }
        }
        logger.info(f"Devolviendo estado del sistema: {response_data}")
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al obtener el estado del sistema: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener el estado del sistema: {str(e)}"
        )
