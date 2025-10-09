import secrets
import string
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union, Tuple

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from itsdangerous import URLSafeTimedSerializer

from app.core.config import settings
from app.models.user import RefreshToken, User
from app.db.session import get_db

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def ensure_secret_key(key: str) -> str:
    """
    Asegura que la clave secreta tenga el formato y longitud correctos para HS256.
    
    Args:
        key: La clave secreta como string
        
    Returns:
        str: La clave como string, lista para usar con PyJWT
    """
    print(f"[SECURITY] Clave original: {key[:5]}... (longitud: {len(key)} caracteres)")
    
    # Si la clave es None o está vacía, generamos una nueva
    if not key:
        import secrets
        key = secrets.token_hex(32)  # 64 caracteres hexadecimales
        print(f"[SECURITY] Se generó una nueva clave secreta: {key[:5]}...")
    
    # Asegurarnos de que la clave tenga al menos 32 caracteres
    if len(key) < 32:
        print(f"[SECURITY] La clave es demasiado corta ({len(key)} < 32), aplicando hash...")
        import hashlib
        key = hashlib.sha256(key.encode('utf-8')).hexdigest()
    
    print(f"[SECURITY] Clave final: {key[:5]}... (longitud: {len(key)} caracteres)")
    return key

# Configuración de la clave secreta
try:
    # Asegurarnos de que la clave secreta sea un string
    SECRET_KEY = ensure_secret_key(settings.SECRET_KEY)
    serializer = URLSafeTimedSerializer(SECRET_KEY)
    print(f"[SECURITY] Clave secreta configurada correctamente. Longitud: {len(SECRET_KEY)} caracteres")
    print(f"[SECURITY] Muestra de clave: {SECRET_KEY[:5]}...")
except Exception as e:
    print(f"[SECURITY] Error al configurar la clave secreta: {str(e)}")
    raise

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Dictionary containing the data to encode in the token
        expires_delta: Optional timedelta for token expiration
        
    Returns:
        str: Encoded JWT token
    """
    print("\n" + "="*80)
    print("[JWT] === INICIO DE CREACIÓN DE TOKEN ===")
    print(f"[JWT] Datos a codificar: {data}")
    
    # Create a copy of the data dictionary
    to_encode = data.copy()
    
    # Calculate expiration time
    now = datetime.utcnow()
    if expires_delta:
        expire = now + expires_delta
    else:
        # Default to 30 days if not specified
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Add standard JWT claims with proper integer timestamps
    to_encode.update({
        "exp": int(expire.timestamp()),  # Convert to Unix timestamp (seconds)
        "iat": int(now.timestamp()),     # Issued at time in seconds
        "nbf": int(now.timestamp()),     # Not Before time in seconds
        "type": "access",
        "iss": settings.JWT_ISSUER,
        "aud": "zeus-ia:auth"  # Audience claim for additional security
    })
    
    # Log token details
    print(f"[JWT] Fecha/hora actual (UTC): {now}")
    print(f"[JWT] Token expira en: {expire} (en {settings.ACCESS_TOKEN_EXPIRE_MINUTES} minutos)")
    print(f"[JWT] Payload final: {to_encode}")
    print(f"[JWT] Usando ALGORITHM: {settings.ALGORITHM}")
    print(f"[JWT] Usando ISSUER: {settings.JWT_ISSUER}")
    
    # Generar el token con la clave secreta como string
    try:
        print("\n[JWT] === GENERANDO TOKEN JWT ===")
        
        # Asegurarse de que la clave sea string
        secret_key_str = str(SECRET_KEY)
        
        print(f"[JWT] Usando clave secreta de {len(secret_key_str)} caracteres")
        print(f"[JWT] Muestra de clave: {secret_key_str[:5]}...")
        
        # Generar el token
        print("\n[JWT] Generando token con los siguientes parámetros:")
        print(f"  - Algoritmo: {settings.ALGORITHM}")
        print(f"  - Issuer (iss): {settings.JWT_ISSUER}")
        print(f"  - Audience (aud): zeus-ia:auth")
        print(f"  - Tiempo de expiración: {settings.ACCESS_TOKEN_EXPIRE_MINUTES} minutos")
        
        # Generar el token JWT
        encoded_jwt = jwt.encode(
            to_encode,
            secret_key_str,
            algorithm=settings.ALGORITHM
        )
        
        # Asegurarse de que el token sea string
        if isinstance(encoded_jwt, bytes):
            encoded_jwt = encoded_jwt.decode('utf-8')
            
        # Verificar que el token generado sea válido
        print("\n[JWT] === VERIFICANDO TOKEN GENERADO ===")
        try:
            # Verificar que podemos decodificar el token con la misma clave
            decoded = jwt.decode(
                encoded_jwt,
                secret_key_str,
                algorithms=[settings.ALGORITHM],
                audience=to_encode.get("aud"),
                issuer=to_encode.get("iss")
            )
            print("[JWT] Token generado y verificado exitosamente")
            return encoded_jwt
            
        except Exception as verify_error:
            print(f"[JWT] ERROR: No se pudo verificar el token generado: {str(verify_error)}")
            raise JWTError(f"Error de verificación del token generado: {str(verify_error)}")
            
    except Exception as e:
        print(f"[JWT] Error al generar el token: {str(e)}")
        print(f"[JWT] Tipo de error: {type(e).__name__}")
        raise

def create_refresh_token() -> str:
    """
    Generate a secure random string to be used as a refresh token.
    
    Returns:
        str: A secure random string
    """
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(64))

def verify_refresh_token(db: Session, token: str) -> Optional[RefreshToken]:
    """
    Verify if a refresh token is valid and return the associated token record.
    
    Args:
        db: Database session
        token: The refresh token to verify
        
    Returns:
        Optional[RefreshToken]: The token record if valid, None otherwise
    """
    if not token:
        return None
        
    db_token = db.query(RefreshToken).filter(
        RefreshToken.token == token,
        RefreshToken.is_active == True,
        RefreshToken.expires_at > datetime.utcnow()
    ).first()
    
    return db_token

def get_current_user(db: Session, token: str) -> User:
    """
    Obtiene el usuario actual a partir de un token JWT.
    
    Valida el token JWT, verifica su firma, expiración y claims.
    
    Args:
        db: Sesión de base de datos
        token: Token JWT (con o sin prefijo 'Bearer')
        
    Returns:
        User: El usuario autenticado
        
    Raises:
        HTTPException: Si el token es inválido, está expirado o el usuario no existe
    """
    from fastapi import HTTPException, status
    from jose import jwt, JWTError
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Excepción para credenciales inválidas
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Verificar que el token no esté vacío
    if not token:
        logger.warning("Token vacío recibido")
        raise credentials_exception
        
    try:
        # Limpiar el token (eliminar 'Bearer' o 'bearer' si existe, con o sin espacio)
        token = token.strip()
        
        # Si el token comienza con 'Bearer ' o 'bearer ', quitarlo
        if token.lower().startswith('bearer '):
            token = token[7:].lstrip()
            logger.debug("Se eliminó el prefijo 'bearer ' del token")
        # Si el token comienza con 'Bearer' o 'bearer' sin espacio
        elif token.lower().startswith('bearer'):
            token = token[6:].lstrip()
            logger.debug("Se eliminó el prefijo 'bearer' del token")
            
        logger.debug(f"Token recibido (inicio): {token[:20]}... (longitud total: {len(token)} caracteres)")
        
        # Verificar que el token tenga el formato correcto (al menos 3 partes separadas por puntos)
        if len(token.split('.')) != 3:
            logger.error(f"Formato de token inválido. Partes encontradas: {len(token.split('.'))}")
            logger.error(f"Token recibido: {token}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Formato de token inválido. Asegúrate de incluir solo el token JWT después de 'Bearer'.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Decodificar el token
        secret_key_str = str(SECRET_KEY)
        logger.debug(f"Clave secreta para verificación: {secret_key_str[:5]}...")
        
        # Verificar el token con más opciones de depuración
        logger.info("=== INICIO DE VERIFICACIÓN DE TOKEN ===")
        logger.info(f"Algoritmo: {settings.ALGORITHM}")
        logger.info(f"Issuer esperado: {settings.JWT_ISSUER}")
        logger.info(f"Audience esperada: {settings.JWT_AUDIENCE}")
        logger.info(f"Clave secreta (inicio): {secret_key_str[:5]}... (longitud: {len(secret_key_str)})")
        
        # Primero intentamos decodificar sin verificar para ver el contenido
        try:
            unverified_payload = jwt.get_unverified_claims(token)
            logger.info("Contenido del token (sin verificar):")
            for k, v in unverified_payload.items():
                logger.info(f"  {k}: {v}")
        except Exception as e:
            logger.warning(f"No se pudo decodificar el token sin verificar: {str(e)}")
        
        # Ahora intentamos la verificación completa
        try:
            payload = jwt.decode(
                token,
                secret_key_str,
                algorithms=[settings.ALGORITHM],
                audience=settings.JWT_AUDIENCE,
                issuer=settings.JWT_ISSUER,
                options={
                    "verify_signature": True,
                    "verify_aud": True,
                    "verify_iss": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_iat": True
                }
            )
            logger.info("Token verificado exitosamente")
            logger.debug(f"Payload del token: {payload}")
            
        except JWTError as e:
            logger.error("=== ERROR AL VERIFICAR TOKEN ===")
            logger.error(f"Tipo de error: {type(e).__name__}")
            logger.error(f"Mensaje: {str(e)}")
            
            # Información detallada según el tipo de error
            if "Signature verification failed" in str(e):
                logger.error("ERROR: La firma del token no es válida")
                logger.error("Posibles causas:")
                logger.error("1. La clave secreta usada para verificar no coincide con la usada para firmar")
                logger.error("2. El token ha sido modificado después de ser firmado")
                logger.error(f"3. El algoritmo de firma ({settings.ALGORITHM}) no es el correcto")
                logger.error("4. La clave secreta contiene caracteres especiales que no se están manejando correctamente")
                
                # Verificar si el token está expirado
                try:
                    jwt.decode(token, secret_key_str, algorithms=[settings.ALGORITHM], options={"verify_signature": False})
                    logger.error("El token NO está expirado, el problema es específicamente con la firma")
                except Exception as inner_e:
                    logger.error(f"Error adicional al verificar expiración: {str(inner_e)}")
            
            # Log adicional para diagnóstico
            logger.error("=== INFORMACIÓN DE DIAGNÓSTICO ===")
            logger.error(f"Longitud del token: {len(token)} caracteres")
            logger.error(f"Inicio del token: {token[:20]}...")
            logger.error(f"Fin del token: ...{token[-20:] if len(token) > 20 else ''}")
            logger.error(f"Clave secreta actual (inicio): {secret_key_str[:5]}...")
            logger.error(f"Longitud de la clave: {len(secret_key_str)} caracteres")
            
            # Crear un nuevo token de prueba con la misma clave para comparar
            try:
                test_token = jwt.encode(
                    {"test": "test"},
                    secret_key_str,
                    algorithm=settings.ALGORITHM
                )
                logger.info("Se pudo generar un nuevo token con éxito usando la clave actual")
            except Exception as test_e:
                logger.error(f"Error al generar token de prueba: {str(test_e)}")
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Error de autenticación: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        # Verify audience - accept both 'zeus-ia:auth' and 'zeus-ia:access' for backward compatibility
        token_audience = payload.get("aud")
        valid_audiences = ["zeus-ia:auth", "zeus-ia:access", "zeus-ia:websocket"]
        
        # Check if token_audience is a string or list and validate accordingly
        if isinstance(token_audience, str):
            if token_audience not in valid_audiences:
                error_msg = f"Invalid token audience: {token_audience}"
                print(f"[JWT] {error_msg}")
                print(f"[JWT] Valid audiences: {valid_audiences}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={"error": "Invalid token audience", "valid_audiences": valid_audiences},
                    headers={"WWW-Authenticate": "Bearer"},
                )
        elif isinstance(token_audience, list):
            if not any(aud in valid_audiences for aud in token_audience):
                error_msg = f"No valid audience found in: {token_audience}"
                print(f"[JWT] {error_msg}")
                print(f"[JWT] Valid audiences: {valid_audiences}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={"error": "No valid audience found", "valid_audiences": valid_audiences},
                    headers={"WWW-Authenticate": "Bearer"},
                )
        else:
            error_msg = f"Invalid audience type: {type(token_audience)}"
            print(f"[JWT] {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "Invalid audience type"},
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        # Obtener el email del token
        email: str = payload.get("sub")
        if email is None:
            logger.warning("Token sin campo 'sub' (email)")
            raise credentials_exception
            
        # Buscar el usuario en la base de datos
        logger.info(f"Buscando usuario en la base de datos: {email}")
        user = db.query(User).filter(User.email == email).first()
        
        if user is None:
            logger.warning(f"Usuario no encontrado: {email}")
            raise credentials_exception
            
        logger.info(f"Usuario autenticado correctamente: {email}")
        return user
        
    except JWTError as e:
        logger.error(f"Error de JWT: {str(e)}")
        raise credentials_exception
    except Exception as e:
        logger.error(f"Error inesperado en get_current_user: {str(e)}")
        raise credentials_exception
        # 7. Decodificar y verificar el token JWT
        try:
            # Log de depuración detallado
            logger.debug("="*80)
            logger.debug("[JWT] INICIO DE VERIFICACIÓN DE TOKEN")
            logger.debug(f"[JWT] Algoritmo: {settings.ALGORITHM}")
            logger.debug(f"[JWT] Clave secreta (inicio): {secret_key_str[:10]}... (longitud: {len(secret_key_str)})")
            logger.debug(f"[JWT] Clave secreta (fin): ...{secret_key_str[-10:]} (longitud: {len(secret_key_str)})")
            logger.debug(f"[JWT] Token (inicio): {token[:50]}...")
            logger.debug(f"[JWT] Token (fin): ...{token[-50:]}")
            logger.debug(f"[JWT] Longitud del token: {len(token)} caracteres")
            
            # Primero, intentar decodificar sin verificar la firma para diagnóstico
            try:
                unverified = jwt.get_unverified_claims(token)
                logger.debug(f"[JWT] Claims sin verificar: {unverified}")
            except Exception as e:
                logger.error(f"[JWT] Error al decodificar sin verificar: {str(e)}")
            
            # Decodificar el token con verificación de firma (configuración mínima)
            payload = jwt.decode(
                token,
                secret_key_str,
                algorithms=[settings.ALGORITHM],
                options={
                    "verify_signature": True,
                    "verify_aud": False,
                    "verify_iss": False,  # Desactivar temporalmente
                    "verify_sub": False,  # Desactivar temporalmente
                    "verify_iat": False,  # Desactivar temporalmente
                    "verify_exp": False,  # Desactivar temporalmente
                    "verify_nbf": False,
                }
            )
            
            logger.debug("Token JWT verificado correctamente")
            
            # 8. Validar claims requeridos
            if not payload.get("sub"):
                logger.warning("Token sin claim 'sub' (subject)")
                raise credentials_exception
                
            # 9. Verificar tipo de token (access/refresh)
            if payload.get("type") != "access":
                logger.warning(f"Tipo de token inválido: {payload.get('type')}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Tipo de token inválido"
                )
                
            # 10. Obtener el usuario de la base de datos
            user = db.query(User).filter(
                User.email == payload["sub"],
                User.is_active == True
            ).first()
            
            if not user:
                logger.warning(f"Usuario no encontrado o inactivo: {payload['sub']}")
                raise credentials_exception
                
            # 11. Verificar versión del token (para invalidación global)
            if hasattr(user, 'token_version') and payload.get('jti') != user.token_version:
                logger.warning("Token inválido (versión no coincide)")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Sesión expirada. Por favor, inicie sesión nuevamente."
                )
                
            return user
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token expirado")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expirado. Por favor, inicie sesión nuevamente.",
                headers={"WWW-Authenticate": "Bearer error=\"invalid_token\", error_description=\"Token expired\""}
            )
            
        except jwt.JWTClaimsError as e:
            logger.warning(f"Error en los claims del token: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido. Por favor, inicie sesión nuevamente.",
                headers={"WWW-Authenticate": "Bearer error=\"invalid_token\", error_description=\"Invalid token claims\""}
            )
            
        except JWTError as e:
            logger.error(f"Error al verificar el token: {str(e)}")
            raise credentials_exception
            
        except Exception as e:
            logger.error(f"Error inesperado al verificar el token: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al procesar la autenticación"
            )
            
    except HTTPException:
        # Re-lanzar excepciones HTTP existentes
        raise
        
    except Exception as e:
        logger.error(f"Error inesperado en get_current_user: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor al procesar la autenticación"
        )
    
    # Si la verificación inicial falla, intentar con la clave en formato string
    try:
        secret_key_str = str(settings.SECRET_KEY)
        payload = jwt.decode(
            token,
            secret_key_str,
            algorithms=[settings.ALGORITHM],
            options={
                "verify_aud": False,
                "verify_iss": bool(settings.JWT_ISSUER),
                "verify_sub": True,
                "verify_iat": True,
                "verify_exp": True,
                "verify_nbf": False,
            },
            issuer=settings.JWT_ISSUER if settings.JWT_ISSUER else None
        )
        logger.debug("Token verificado usando SECRET_KEY como string")
        
        # Validar claims requeridos
        if not payload.get("sub"):
            logger.warning("Token sin claim 'sub' (subject)")
            raise credentials_exception
        
        # Obtener el usuario de la base de datos
        user = db.query(User).filter(
            User.email == payload["sub"],
            User.is_active == True
        ).first()
        
        if not user:
            logger.warning(f"Usuario no encontrado o inactivo: {payload['sub']}")
            raise credentials_exception
            
        return user
        
    except Exception as e:
        logger.error(f"Error al verificar el token con clave alternativa: {str(e)}")
        if "exp" in str(e):
            logger.warning("Token expirado")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expirado. Por favor, inicie sesión nuevamente.",
                headers={"WWW-Authenticate": "Bearer error=\"invalid_token\", error_description=\"Token expired\""}
            )
        raise credentials_exception
        
    except JWTError as e:
        logger.error(f"Error al decodificar el token: {str(e)}")
        if "exp" in str(e):
            logger.warning("Token expirado")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expirado. Por favor, inicie sesión nuevamente.",
                headers={"WWW-Authenticate": "Bearer error=\"invalid_token\", error_description=\"Token expired\""}
            )
        raise credentials_exception

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash.
    
    Args:
        plain_password: The plain text password
        hashed_password: The hashed password to verify against
        
    Returns:
        bool: True if the password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """
    Generate a password hash.
    
    Args:
        password: The password to hash
        
    Returns:
        str: The hashed password
    """
    return pwd_context.hash(password)

def get_current_active_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    """
    Get the current active user from the token.
    
    Args:
        db: Database session
        token: JWT token from the Authorization header
        
    Returns:
        User: The current active user
        
    Raises:
        HTTPException: If the user is not found or inactive
    """
    from fastapi import HTTPException, status
    
    logger.debug("Verificando usuario activo")
    
    # Obtener el usuario actual usando la función get_current_user
    user = get_current_user(db, token)
    
    # Verificar si el usuario está activo
    if not user.is_active:
        logger.warning(f"Intento de acceso de usuario inactivo: {user.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )

    print(f"[AUTH] Usuario autenticado: {user.email}")
    print("="*80 + "\n")
    return user

def generate_tokens(db: Session, user: User) -> Dict[str, str]:
    """
    Generate access and refresh tokens for a user.
    
    Args:
        db: Database session
        user: The user to generate tokens for
        
    Returns:
        Dict[str, str]: Dictionary containing access_token and refresh_token
    """
    # Create access token
    access_token = create_access_token(
        data={"sub": user.email, "user_id": user.id},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    # Create refresh token
    refresh_token = create_refresh_token()
    
    # Store refresh token in database
    db_refresh_token = RefreshToken(
        token=refresh_token,
        user_id=user.id,
        expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        is_active=True
    )
    db.add(db_refresh_token)
    db.commit()
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }