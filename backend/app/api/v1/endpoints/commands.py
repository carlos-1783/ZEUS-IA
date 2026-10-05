from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Response, Body, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import Dict, Optional, Any, List
import json
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import logging

from app.core.auth import get_current_active_user
from app.core.config import settings
from app.core.security import verify_password
from app.db.session import get_db
from app.models.user import User
from services.thalos_request_guard_v1 import thalos_request_guard
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
    description=(
        "Execute a system command on the (global) system state. Requires authentication, "
        "THALOS request guard and superuser role."
    ),
    response_description="Command execution result"
)
async def execute_command(
    command_data: CommandData,
    current_user: User = Depends(thalos_request_guard),
):
    """
    Ejecuta un comando sobre el estado GLOBAL del sistema (`state_manager`, compartido entre
    empresas). J5b: guard THALOS + usuario activo + solo superusuario (antes bastaba cualquier
    token valido). El frontend no usa este endpoint.
    """
    if not getattr(current_user, "is_superuser", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo un superusuario puede ejecutar comandos sobre el estado global del sistema.",
        )
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
    except HTTPException:
        # 400 "comando no reconocido" / "falta empresa": no convertir en 500.
        raise
    except Exception as e:
        logger.error(f"Error in execute_command: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing command: {str(e)}"
        )


async def activate_company(empresa: str) -> Dict[str, Any]:
    """
    Activa una empresa específica y actualiza el estado del sistema.

    Función auxiliar SIN autenticación propia: la ruta HTTP es `activate_company_endpoint`,
    que exige superusuario (H-04). No llamar a esta función desde código expuesto.
    
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


@router.post(
    "/activate-company/{empresa}",
    operation_id="commands_activate_company_api_v1",
    summary="Activate Company",
    description=(
        "Activate a specific company and update the (global) system state. "
        "Requires authentication and superuser role."
    ),
    response_description="Activation status"
)
async def activate_company_endpoint(
    empresa: str,
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    H-04 (ZEUS_JARVIS_INTERACTION_AUDIT.md): antes este endpoint respondía 200 SIN token y
    mutaba un estado global persistido en `app/data/system_state.json`. Ahora exige usuario
    autenticado y rol de superusuario (el estado es global, no por empresa).
    """
    if not getattr(current_user, "is_superuser", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo un superusuario puede activar una empresa en el estado global.",
        )
    return await activate_company(empresa)
