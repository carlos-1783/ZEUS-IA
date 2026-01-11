from datetime import timedelta
from typing import Optional, Dict, Any, List

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from sqlalchemy import func
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
    """
    Get a user by email (case-insensitive, trimmed).
    
    Args:
        db: Database session
        email: User email (will be normalized)
        
    Returns:
        User if found, None otherwise
        
    Raises:
        HTTPException: If there's a database error
    """
    if not email:
        return None
        
    # Normalize email: trim and convert to lowercase for comparison
    email_normalized = email.strip().lower()
    
    try:
        # Try exact match first (case-insensitive comparison)
        user = db.query(User).filter(
            func.lower(User.email) == email_normalized
        ).first()
        
        # Fallback: try direct comparison (for databases that are case-sensitive)
        if not user:
            user = db.query(User).filter(User.email == email.strip()).first()
            
        return user
    except Exception as e:
        logger.error(f"Error fetching user {email}: {str(e)}", exc_info=True)
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
    """
    Authenticate a user by email and password.
    
    Args:
        db: Database session
        email: User email (will be normalized)
        password: Plain text password
        
    Returns:
        User if authentication succeeds, None otherwise
        
    Raises:
        HTTPException: If there's a database error (not authentication failure)
    """
    if not email or not password:
        logger.warning("Intento de autenticación con email o contraseña vacíos")
        return None
    
    # Normalize email
    email_normalized = email.strip().lower()
    logger.info(f"Intento de autenticación para: {email_normalized}")
    
    try:
        # Get user from database (case-insensitive)
        user = get_user(db, email_normalized)
        
        if not user:
            logger.warning(f"Usuario no encontrado en la base de datos: {email_normalized}")
            return None
            
        logger.debug(f"Usuario encontrado: {user.email} (ID: {user.id})")
        
        # Check if user is active (additional safety check)
        if not user.is_active:
            logger.warning(f"Intento de autenticación de usuario inactivo: {user.email}")
            return None
        
        # Verify password
        password_valid = verify_password(password, user.hashed_password)
        if not password_valid:
            logger.warning(f"Contraseña incorrecta para el usuario: {user.email}")
            return None
            
        logger.info(f"✅ Autenticación exitosa para: {user.email} (ID: {user.id})")
        return user
        
    except HTTPException:
        # Re-raise HTTP exceptions (like database errors) as-is
        # These are real errors, not authentication failures
        logger.error(f"Error HTTP durante autenticación para {email_normalized}")
        raise
    except Exception as e:
        # Log the error but don't expose it to the user
        logger.error(
            f"Error inesperado en autenticación para {email_normalized}: {str(e)}", 
            exc_info=True
        )
        # Return None instead of raising to avoid exposing internal errors
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
        # For regular HTTP requests, try OAuth2 scheme first
        try:
            token = await oauth2_scheme(request) if hasattr(oauth2_scheme, '__call__') else None
        except Exception:
            token = None
        
        # If no token in header, check query parameters (for direct downloads)
        if not token and request.query_params.get('token'):
            token = request.query_params.get('token')

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Verificar que hay token
    if not token:
        logger.warning("Token no proporcionado")
        raise credentials_exception
    
    try:
        # Limpiar el token por si viene con prefijo 'Bearer '
        if isinstance(token, str) and token.startswith('Bearer '):
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
            # Token expirado es normal - el frontend maneja el refresh automáticamente
            logger.debug("Token expirado - el cliente debería hacer refresh automático")
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
        if request:
            request.state.user = user
            request.state.token_payload = payload
        
        return user
        
    except HTTPException:
        # Re-lanzar HTTPExceptions (401, 403, etc.) sin modificar
        raise
    except Exception as e:
        logger.error(f"Error inesperado en get_current_user: {str(e)}", exc_info=True)
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
