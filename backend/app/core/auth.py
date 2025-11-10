from datetime import timedelta
from typing import Optional, Dict, Any, List

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
import logging

from app.core.config import settings
from app.core.security import verify_password
from app.db.base import get_db
from app.models.user import User
from app.schemas.user import TokenPayload

# Configurar logging
logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

def get_user(db: Session, email: str) -> Optional[User]:
    try:
        return db.query(User).filter(User.email == email).first()
    except Exception as e:
        logger.error(f"Error fetching user {email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener el usuario"
        )

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return get_user(db, email)


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """
    Get a user by their ID.
    
    Args:
        db: Database session
        user_id: The ID of the user to retrieve
        
    Returns:
        User object if found, None otherwise
    """
    try:
        return db.query(User).filter(User.id == user_id).first()
    except Exception as e:
        logger.error(f"Error fetching user with ID {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener el usuario por ID"
        )


def resolve_user_scopes(user: User, existing_scopes: Optional[List[str]] = None) -> List[str]:
    """
    Determine effective scopes for a user.
    Priority:
      1. Scopes already embedded in the token (existing_scopes)
      2. Superusers retain wildcard access ["*"]
      3. Mapping defined in settings.DEFAULT_SCOPE_MAP keyed by email
    """
    if existing_scopes:
        return existing_scopes

    if getattr(user, "is_superuser", False):
        return ["*"]

    scope_map = settings.DEFAULT_SCOPE_MAP or {}
    return scope_map.get(user.email.lower(), [])

def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    print(f"Intentando autenticar: {email}")
    user = get_user(db, email=email)
    print(f"Usuario encontrado: {user}")
    try:
        if not user:
            logger.warning(f"Intento de inicio de sesión fallido para el usuario: {email}")
            return None
        if not verify_password(password, user.hashed_password):
            logger.warning(f"Contraseña incorrecta para el usuario: {email}")
            return None
        return user
    except Exception as e:
        logger.error(f"Error en autenticación para {email}: {str(e)}")
        return None

async def get_current_user_from_token(
    token: str,
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Get the current user from a JWT token.
    
    Args:
        token: JWT token
        db: Database session
        
    Returns:
        User if authenticated, None otherwise
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Decode the JWT token
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        
        # Validate the token data
        token_data = TokenPayload(**payload)
        if token_data is None or token_data.sub is None:
            raise credentials_exception
            
        # Get the user from the database
        user = get_user(db, email=token_data.sub)
        if user is None:
            raise credentials_exception
            
        return user
        
    except JWTError as e:
        logger.error(f"JWT Error: {str(e)}")
        raise credentials_exception
    except Exception as e:
        logger.error(f"Error getting user from token: {str(e)}")
        raise credentials_exception

async def get_current_user(
    request: Request = None,
    db: Session = Depends(get_db),
    token: str = None
):
    # Handle WebSocket connections
    if not token and request and hasattr(request, 'url') and 'websocket' in request.url.path:
        # For WebSocket, we'll get the token from the query parameters
        token = request.query_params.get('token')
    elif not token and request:
        # For regular HTTP requests, use the OAuth2 scheme
        token = await oauth2_scheme(request) if hasattr(oauth2_scheme, '__call__') else None

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Limpiar el token por si viene con prefijo 'Bearer '
        if token.startswith('Bearer '):
            token = token[7:].strip()
            
        # Decodificar el token
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
                options={
                    "verify_aud": False,  # Deshabilitar verificación de audiencia si no se usa
                    "verify_iat": True,
                    "verify_exp": True,
                }
            )
        except jwt.ExpiredSignatureError:
            logger.warning("Token expirado")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expirado",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except JWTError as e:
            logger.error(f"Error decodificando el token: {str(e)}")
            raise credentials_exception
            
        # Verificar que el token tenga el tipo correcto
        if payload.get("type") != "access":
            logger.warning(f"Tipo de token inválido: {payload.get('type')}")
            raise credentials_exception
            
        # Obtener el identificador del usuario del token (puede ser ID o email)
        user_identifier = payload.get("sub")
        if not user_identifier:
            logger.warning("Token no contiene 'sub' claim")
            raise credentials_exception
            
        # Intentar obtener el usuario por ID primero (el caso más común)
        user = None
        try:
            user_id = int(user_identifier)
            user = get_user_by_id(db, user_id=user_id)
        except (ValueError, TypeError):
            # Si no es un ID numérico, intentar por email
            user = get_user(db, email=user_identifier)
            
        if user is None:
            logger.warning(f"Usuario no encontrado para el identificador: {user_identifier}")
            raise credentials_exception

        # Resolver scopes efectivos y adjuntarlos al payload
        effective_scopes = resolve_user_scopes(user, payload.get("scopes"))
        payload["scopes"] = effective_scopes
            
        # Agregar información del usuario al request para uso posterior
        request.state.user = user
        request.state.token_payload = payload
        
        return user
        
    except Exception as e:
        logger.error(f"Error inesperado en get_current_user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor al validar el token"
        )

def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        logger.warning(f"Intento de acceso de usuario inactivo: {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo"
        )
    return current_user

def get_current_active_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_superuser:
        logger.warning(f"Intento de acceso no autorizado de usuario no superusuario: {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El usuario no tiene suficientes privilegios"
        )
    return current_user


def require_scopes(required_scopes: List[str]):
    """
    Dependency factory that ensures the authenticated principal owns the required scopes.
    """

    def dependency(
        request: Request,
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        payload = getattr(request.state, "token_payload", {})
        token_scopes = payload.get("scopes", [])

        if "*" in token_scopes or any(scope in token_scopes for scope in required_scopes):
            return current_user

        logger.warning(
            "Acceso denegado por scopes insuficientes. Requeridos=%s | Token=%s",
            required_scopes,
            token_scopes,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient scope",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return dependency
