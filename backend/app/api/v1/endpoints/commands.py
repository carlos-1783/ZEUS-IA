from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Response, Body, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import Dict, Optional, Any, List
import json
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import logging

from app.core.config import settings
from app.core.security import verify_password
from app.db.base import get_db
from app.models.user import User
from app.core.state_manager import state_manager

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mapeo de módulos por empresa
EMPRESA_MODULOS = {
    "per-seo": {
        "crm": True,
        "per-seo": True,
        "facturacion": True,
        "marketing": True
    },
    "thalos": {
        "crm": True,
        "thalos": True,
        "inventario": True
    }
}

class CommandData(BaseModel):
    command: str = Field(..., description="The command to execute")

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.email == username).first()
    if user is None:
        raise credentials_exception
    return user

@router.get(
    "/status",
    operation_id="commands_status_api_v1",
    summary="Get System Status",
    description="Get the current system status. No authentication required.",
    response_description="Current system status information"
)
async def get_status():
    """
    Obtiene el estado actual del sistema.
    No requiere autenticación para permitir verificación de estado sin credenciales.
    """
    return {
        "status": "operational",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }

@router.post(
    "/execute",
    operation_id="commands_execute_api_v1",
    summary="Execute Command",
    description="Execute a system command. Requires authentication.",
    response_description="Command execution result"
)
async def execute_command(
    command_data: CommandData,
    current_user: User = Depends(get_current_user)
):
    """
    Ejecuta un comando y devuelve una respuesta.
    Requiere autenticación.
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Received command: {command_data.command} from user: {current_user.email}")
    
    try:
        command = command_data.command.strip()
        logger.info(f"Processing command: {command} from user: {current_user.email}")
        
        # Get current state
        state = state_manager.get_state()
        
        # Process the command
        if command.lower() == "estás en casa":
            logger.info("Activating default company (PER-SEO)")
            # Activate the default company
            state["empresa_actual"] = "PER-SEO"
            state["empresa_activada"] = True
            state["modulos_activos"] = ["modulo1", "modulo2"]  # Default modules
            state["ultima_activacion"] = datetime.utcnow().isoformat()
            state_manager.update_state(state)
            
            return {
                "status": "success",
                "message": "Sistema activado correctamente para PER-SEO",
                "data": state
            }
            
        elif command.lower().startswith("activar:"):
            empresa = command.split(":", 1)[1].strip()
            if not empresa:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Debe especificar una empresa para activar"
                )
                
            logger.info(f"Activating company: {empresa}")
            state["empresa_actual"] = empresa
            state["empresa_activada"] = True
            state["modulos_activos"] = [f"modulo_{empresa.lower()}", "comun"]
            state["ultima_activacion"] = datetime.utcnow().isoformat()
            state_manager.update_state(state)
            
            return {
                "status": "success",
                "message": f"Sistema activado correctamente para {empresa}",
                "data": state
            }
            
        elif command.lower() == "estado":
            logger.info("Retrieving system status")
            return {
                "status": "success",
                "data": state
            }
            
        elif command.lower() == "reiniciar" and current_user.is_superuser:
            logger.warning(f"Resetting system state by admin: {current_user.email}")
            state_manager.reset_state()
            return {
                "status": "success",
                "message": "Estado del sistema reiniciado correctamente",
                "data": state_manager.get_state()
            }
            
        # Command not recognized
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Comando no reconocido: {command}"
        )
    except Exception as e:
        logger.error(f"Error in execute_command: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing command: {str(e)}"
        )
    
    try:
        # Comando para activar el sistema (configuración por defecto)
        if command.lower() in ["estás en casa", "estas en casa"]:
            logger.info("Activando sistema con configuración por defecto (PER-SEO)")
            return activate_company("PER-SEO")
            
        # Comando para activar una empresa específica
        elif command.lower().startswith("activar:"):
            empresa = command.split(":")[1].strip().upper()
            logger.info(f"Intentando activar empresa: {empresa}")
            return activate_company(empresa)
                
        # Comando para obtener el estado actual
        elif command.lower() == "estado":
            return {
                "status": "success",
                "data": state_manager.get_state()
            }
            
        # Comando para reiniciar el estado
        elif command.lower() == "reiniciar" and current_user.is_superuser:
            logger.warning(f"Usuario {current_user.email} está reiniciando el estado del sistema")
            state_manager.reset_state()
            return {
                "status": "success",
                "message": "Estado del sistema reiniciado correctamente",
                "data": state_manager.get_state()
            }
            
        # Comando no reconocido
        else:
            return {
                "status": "error",
                "message": "Comando no reconocido",
                "suggestions": [
                    "Estás en casa",
                    "activar: PER-SEO",
                    "activar: THALOS",
                    "estado"
                ]
            }
            
    except Exception as e:
        logger.error(f"Error al procesar el comando: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al procesar el comando: {str(e)}"
        )


@router.post(
    "/activate-company/{empresa}",
    operation_id="commands_activate_company_api_v1",
    summary="Activate Company",
    description="Activate a specific company and update system state.",
    response_description="Activation status"
)
async def activate_company(empresa: str) -> Dict[str, Any]:
    """
    Activa una empresa específica y actualiza el estado del sistema.
    
    Args:
        empresa: Nombre de la empresa a activar (ej: "PER-SEO", "THALOS")
        
    Returns:
        Dict con la respuesta de la operación
    """
    empresa_lower = empresa.lower()
    
    # Verificar si la empresa es válida
    if empresa_lower not in ["per-seo", "thalos"]:
        return {
            "status": "error",
            "message": f"Empresa {empresa} no reconocida. Empresas disponibles: PER-SEO, THALOS"
        }
    
    # Preparar actualización del estado
    update_data = {
        "empresa_actual": empresa,
        "empresa_activada": True,
        "modulos_activos": EMPRESA_MODULOS.get(empresa_lower, {})
    }
    
    # Actualizar el estado
    new_state = state_manager.update_state(update_data)
    
    logger.info(f"Empresa {empresa} activada correctamente")
    return {
        "status": "success",
        "message": f"Empresa {empresa} activada correctamente",
        "data": new_state
    }
