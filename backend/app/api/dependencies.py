"""
Módulo de dependencias para la autenticación y autorización.
Incluye funciones para proteger los endpoints de la API.
"""
from typing import Annotated, Optional, Dict, Any
from fastapi import Depends, HTTPException, status, Security, Request
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from jose import JWTError

from app.core.jwt_handler import verify_token, JWTTokenError
from app.db.session import get_db
from sqlalchemy.orm import Session
from app.models.user import User

# Configuración de OAuth2 para manejar tokens Bearer
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="api/v1/auth/login",
    auto_error=False,
)

async def get_current_user(
    request: Request,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Dependencia para obtener el usuario actual a partir del token JWT.
    
    Args:
        request: Objeto de solicitud de FastAPI
        token: Token JWT del encabezado de autorización
        db: Sesión de base de datos
        
    Returns:
        dict: Datos del usuario autenticado
        
    Raises:
        HTTPException: Si el token es inválido o el usuario no existe
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se proporcionó un token de autenticación",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        # Verificar y decodificar el token
        payload = verify_token(token)
        
        # Obtener el email del token
        email = payload.get("sub")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido: no se pudo identificar al usuario",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Buscar el usuario en la base de datos
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado",
            )
        
        # Verificar si el usuario está activo
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Usuario inactivo",
            )
        
        # Agregar los datos del usuario al estado de la solicitud
        request.state.user = user
        
        # Devolver los datos del usuario
        return {
            "id": user.id,
            "email": user.email,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser,
            "scopes": payload.get("scopes", []),
        }
        
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Error de autenticación: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Tipos anotados para usar en las dependencias
CurrentUser = Annotated[Dict[str, Any], Depends(get_current_user)]

# Dependencias comunes
async def get_current_active_user(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Dependencia que verifica que el usuario esté autenticado y activo.
    """
    return current_user


async def get_current_admin_user(
    current_user: Dict[str, Any] = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Dependencia que verifica que el usuario sea administrador.
    """
    if not current_user.get("is_superuser", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren privilegios de administrador",
        )
    return current_user


# Tipos anotados para usar en las rutas
CurrentUser = Annotated[Dict[str, Any], Depends(get_current_user)]
ActiveUser = Annotated[Dict[str, Any], Depends(get_current_active_user)]
AdminUser = Annotated[Dict[str, Any], Depends(get_current_admin_user)]
