"""
Módulo para manejo de autenticación JWT.
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union, List
import jwt
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import logging
from app.core.config import settings
from app.db.session import get_db

# Configure logging
logger = logging.getLogger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def create_jwt_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
    token_type: str = settings.JWT_ACCESS_TOKEN_TYPE
) -> str:
    """
    Crea un nuevo token JWT.
    
    Args:
        data: Datos a incluir en el token
        expires_delta: Tiempo de expiración del token
        token_type: Tipo de token ("access" o "websocket")
        
    Returns:
        str: Token JWT firmado
        
    Raises:
        HTTPException: Si hay un error al generar el token
    """
    try:
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)
            
        # Añadir claims estándar
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "nbf": datetime.utcnow() - timedelta(seconds=5),  # Válido desde 5 segundos atrás
            "iss": settings.JWT_ISSUER,
            # Usar 'zeus-ia:access' para tokens de acceso y 'zeus-ia:websocket' para WebSockets
            "aud": f"zeus-ia:access" if token_type == settings.JWT_ACCESS_TOKEN_TYPE else f"zeus-ia:{token_type}",
            "token_type": token_type
        })
        
        logger.debug(f"Creating token with algorithm: {settings.ALGORITHM}")
        logger.debug(f"Token payload: {to_encode}")
        
        # Codificar el token
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        
        return encoded_jwt
        
    except Exception as e:
        logger.error(f"Error creating JWT token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al generar el token de autenticación: {str(e)}"
        )

def decode_jwt_token(
    token: str, 
    audience: Optional[Union[str, List[str]]] = None,
    require_audience: bool = True
) -> Dict[str, Any]:
    """
    Decodifica y verifica un token JWT.
    
    Args:
        token: Token JWT a verificar
        audience: Audiencia esperada (opcional). Si no se especifica, se usa settings.JWT_AUDIENCE
        require_audience: Si es True, se requiere que el token tenga una audiencia válida
        
    Returns:
        Dict[str, Any]: Payload del token decodificado
        
    Raises:
        HTTPException: Si el token es inválido o ha expirado
    """
    try:
        logger.debug(f"Decoding token with algorithm: {settings.ALGORITHM}")
        logger.debug(f"Token (start): {token[:10]}...{token[-10:] if len(token) > 20 else ''}")
        logger.debug(f"Using secret key: ...{str(settings.SECRET_KEY)[-5:] if settings.SECRET_KEY and len(settings.SECRET_KEY) > 10 else ''}")

        # Decodificar el token sin verificar la firma primero para obtener la audiencia
        try:
            unverified = jwt.decode(token, options={"verify_signature": False})
            token_audience = unverified.get("aud")
            token_issuer = unverified.get("iss")
            logger.debug(f"Token audience: {token_audience}, issuer: {token_issuer}")
        except Exception as e:
            logger.error(f"Error decoding token header: {str(e)}")
            raise jwt.InvalidTokenError("Token malformado")

        # Configurar la audiencia para la validación
        if audience is None:
            audience = settings.JWT_AUDIENCE
        
        # Asegurarse de que la audiencia sea una lista
        if isinstance(audience, str):
            audience = [audience]
            
        # Si el token tiene una audiencia específica, asegurarse de que esté en la lista de audiencias permitidas
        if token_audience and isinstance(token_audience, str):
            if token_audience not in audience:
                audience.append(token_audience)
        
        logger.debug(f"Validating token with audience: {audience}")

        # Verificar y decodificar el token usando PyJWT con todas las validaciones
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
                audience=audience if require_audience else None,
                issuer=settings.JWT_ISSUER,
                options={
                    "verify_signature": True,
                    "verify_aud": require_audience,
                    "verify_iss": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_iat": True
                }
            )
            logger.debug("Token decoded successfully")
            return payload
            
        except jwt.InvalidAudienceError:
            logger.error(f"Audiencia inválida. Esperada: {audience}, recibida: {token_audience}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Audiencia de token inválida",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidIssuerError:
            logger.error(f"Emisor inválido. Esperado: {settings.JWT_ISSUER}, recibido: {token_issuer}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Emisor de token inválido",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
    except jwt.ExpiredSignatureError:
        logger.warning("Token expirado")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        logger.error(f"Token inválido: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token de autenticación inválido: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> Dict[str, Any]:
    """
    Obtiene el usuario actual a partir del token JWT.
    
    Args:
        request: Objeto Request de FastAPI
        db: Sesión de base de datos
        token: Token JWT del encabezado de autorización
        
    Returns:
        Dict[str, Any]: Payload del token si es válido
        
    Raises:
        HTTPException: Si el token es inválido o el usuario no existe
    """
    try:
        logger.debug("Iniciando get_current_user")
        
        # Limpiar y validar el token
        if not token or not isinstance(token, str):
            logger.error("No se proporcionó un token o el token no es una cadena válida")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de autenticación no proporcionado o inválido",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        # Limpiar el token (eliminar prefijo 'Bearer ' si está presente)
        if isinstance(token, bytes):
            token = token.decode('utf-8')
        token = token.replace('Bearer ', '', 1).strip()
        logger.debug(f"Token limpio: {token[:10]}...")

        # Decodificar el token
        try:
            payload = decode_jwt_token(token)
            logger.debug(f"Token decodificado correctamente para el usuario: {payload.get('sub')}")
        except jwt.ExpiredSignatureError:
            logger.warning("Token expirado")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expirado",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError as e:
            logger.error(f"Token inválido: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token de autenticación inválido: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Verificar claims requeridos
        user_id = payload.get("sub")
        if not user_id:
            logger.error("No se encontró el identificador de usuario en el token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Identificador de usuario no encontrado en el token",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        # Asegurarse de que el user_id sea un entero
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            logger.error(f"ID de usuario inválido en el token: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Formato de ID de usuario inválido",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Verificar si el usuario existe en la base de datos
        from app.core.auth import get_current_user_from_token, get_user_by_id
        try:
            user = get_user_by_id(db, user_id)
            if not user:
                logger.error(f"Usuario con ID {user_id} no encontrado en la base de datos")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Usuario no encontrado",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        except Exception as e:
            logger.error(f"Error al buscar el usuario con ID {user_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al buscar el usuario",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Verificar si el usuario está activo
        if not payload.get("is_active", False):
            logger.warning(f"El usuario {user_id} está inactivo")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario inactivo",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Añadir información del usuario al payload
        payload.update({
            "user_id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser
        })

        logger.debug(f"Usuario autenticado correctamente: {user.email} (ID: {user.id})")
        return payload

    except HTTPException as e:
        # Re-lanzar excepciones HTTP
        logger.error(f"Error de autenticación: {str(e.detail)}")
        raise e
    except Exception as e:
        # Registrar errores inesperados
        logger.error(f"Error inesperado en get_current_user: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor al validar la autenticación: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

def create_access_token(
    user_id: str,
    email: str,
    is_active: bool = True,
    is_superuser: bool = False,
    expires_delta: Optional[timedelta] = None,
    scopes: Optional[List[str]] = None,
) -> str:
    """
    Crea un token de acceso JWT para un usuario.

    Args:
        user_id: ID del usuario
        email: Email del usuario
        is_active: Si el usuario está activo
        is_superuser: Si el usuario es administrador
        expires_delta: Tiempo de expiración del token

    Returns:
        str: Token JWT firmado
    """
    if not expires_delta:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # Crear payload con la información del usuario
    data = {
        "sub": str(user_id),  # Usar el ID como subject para consistencia
        "email": email,
        "is_active": is_active,
        "is_superuser": is_superuser,
        "type": "access",  # Añadir tipo de token
        "scopes": scopes or [],
    }

    return create_jwt_token(data, expires_delta)

def create_refresh_token() -> str:
    """
    Crea un token de actualización seguro.

    Returns:
        str: Token de actualización
    """
    import secrets
    import string
    
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(64))
