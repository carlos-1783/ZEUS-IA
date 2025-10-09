from pydantic_settings import BaseSettings
from typing import List, Optional, Union
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

class Settings(BaseSettings):
    # Application
    PROJECT_NAME: str = "ZEUS-IA"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
    
    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    RELOAD: bool = DEBUG
    
    # Static files
    STATIC_URL: str = "/static"
    STATIC_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static")
    
    # Security - Configuración de JWT SEGURA PARA PRODUCCIÓN
    # Clave secreta como string puro - ULTRA SEGURA
    SECRET_KEY: str = os.getenv("SECRET_KEY", "zeus_ia_super_secure_secret_key_2024_production_ultra_strong_256_bits_minimum")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # 30 minutos para mayor seguridad
    
    # Configuración de JWT
    JWT_AUDIENCE: List[str] = ["zeus-ia:auth", "zeus-ia:access", "zeus-ia:websocket"]  # Lista de audiencias válidas
    JWT_ISSUER: str = "zeus-ia-backend"  # Emisor del token
    JWT_ACCESS_TOKEN_TYPE: str = "access"
    JWT_WEBSOCKET_TOKEN_TYPE: str = "websocket"
    
    # Validar clave secreta
    if not SECRET_KEY:
        raise ValueError("La SECRET_KEY no puede estar vacía")
    
    # Token refresh settings
    REFRESH_TOKEN_LENGTH: int = 64
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    REFRESH_TOKEN_GRACE_PERIOD_DAYS: int = 7  # Grace period for token reuse detection
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'zeus.db')}")
    
    # CORS Configuration - SIMPLIFICADO PARA DESARROLLO
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ]
    
    # CORS Settings
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = [
        "GET",
        "POST",
        "PUT",
        "DELETE",
        "PATCH",
        "OPTIONS",
        "HEAD"
    ]
    
    CORS_ALLOW_HEADERS: List[str] = [
        "Accept",
        "Accept-Encoding",
        "Accept-Language",
        "Authorization",
        "Content-Type",
        "Content-Length",
        "DNT",
        "Origin",
        "User-Agent",
        "X-Requested-With",
        "X-CSRF-Token",
        "X-Requested-With",
        "Access-Control-Allow-Origin",
        "Access-Control-Allow-Headers",
        "Access-Control-Allow-Methods",
        "Access-Control-Allow-Credentials",
        "Cache-Control",
        "Pragma",
        "Expires",
        "If-Modified-Since",
        "If-None-Match"
    ]
    
    CORS_EXPOSE_HEADERS: List[str] = [
        "Content-Length",
        "Content-Type",
        "Content-Disposition",
        "Authorization",
        "X-Requested-With",
        "X-Total-Count",
        "X-Pagination-Count",
        "X-Pagination-Page",
        "X-Pagination-Limit"
    ]
    
    CORS_MAX_AGE: int = 600  # 10 minutos para preflight requests
    
    # Security Headers
    SECURE_HSTS_SECONDS: int = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS: bool = True
    SECURE_HSTS_PRELOAD: bool = True
    SECURE_CONTENT_TYPE_NOSNIFF: bool = True
    SECURE_BROWSER_XSS_FILTER: bool = True
    SESSION_COOKIE_SECURE: bool = not DEBUG
    CSRF_COOKIE_SECURE: bool = not DEBUG
    X_FRAME_OPTIONS: str = "DENY"
    
    # Rate Limiting
    RATE_LIMIT: str = "100/minute"
    
    # Email
    SMTP_TLS: bool = True
    SMTP_PORT: Optional[int] = None
    SMTP_HOST: Optional[str] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM_EMAIL: Optional[str] = "noreply@zeus-ia.com"
    EMAILS_FROM_NAME: Optional[str] = "ZEUS-IA"
    
    # First Superuser
    FIRST_SUPERUSER_EMAIL: str = os.getenv("FIRST_SUPERUSER_EMAIL", "admin@zeus-ia.com")
    FIRST_SUPERUSER_PASSWORD: str = os.getenv("FIRST_SUPERUSER_PASSWORD", "changethis")
    
    class Config:
        case_sensitive = True
        # Prevenir que se sobrescriban los valores con variables de entorno
        extra = "ignore"
        env_prefix = "ZEUS_"  # Ahora las variables de entorno deben empezar con ZEUS_ para ser consideradas

def ensure_secret_key_format(secret_key: str) -> str:
    """
    Ensure the secret key is in the correct format for JWT operations.
    
    Args:
        secret_key: The secret key to validate and format
        
    Returns:
        str: The validated and properly formatted secret key
        
    Raises:
        ValueError: If the secret key is invalid
    """
    if not secret_key or not isinstance(secret_key, str):
        raise ValueError("La clave secreta debe ser una cadena no vacía")
    
    # Remove any surrounding whitespace or quotes
    secret_key = secret_key.strip().strip('"\'')
    
    # Log the first and last 5 characters for debugging (without exposing the full key)
    print(f"[SECURITY] Clave original: {secret_key[:5]}... (longitud: {len(secret_key)} caracteres)")
    
    # Ensure the key is a valid hex string if it's meant to be one
    try:
        # If it's a hex string, decode it to bytes and back to string to ensure consistency
        if all(c in '0123456789abcdefABCDEF' for c in secret_key):
            # It's a hex string, ensure it has sufficient length
            if len(secret_key) < 32:  # At least 256 bits
                raise ValueError("La clave secreta debe tener al menos 32 caracteres (256 bits)")
            # Return as is, PyJWT will handle it correctly
            return secret_key
    except Exception as e:
        raise ValueError(f"Formato de clave secreta inválido: {str(e)}")
    
    # If not a hex string, ensure it's a strong enough secret
    if len(secret_key) < 32:  # At least 32 characters for a strong secret
        raise ValueError("La clave secreta debe tener al menos 32 caracteres")
    
    print(f"[SECURITY] Clave final: {secret_key[:5]}... (longitud: {len(secret_key)} caracteres)")
    return secret_key

# Crear instancia de configuración
settings = Settings()

# Validar y asegurar el formato de la clave secreta
try:
    settings.SECRET_KEY = ensure_secret_key_format(settings.SECRET_KEY)
    print(f"[SECURITY] Clave secreta configurada correctamente. Longitud: {len(settings.SECRET_KEY)} caracteres")
    print(f"[SECURITY] Muestra de clave: {settings.SECRET_KEY[:5]}...")
except ValueError as e:
    print(f"[ERROR] Error en la configuración de la clave secreta: {str(e)}")
    raise

# Forzar valores importantes después de la inicialización para asegurar que no sean sobrescritos
settings.ACCESS_TOKEN_EXPIRE_MINUTES = 30  # 30 minutos para mayor seguridad
settings.REFRESH_TOKEN_EXPIRE_DAYS = 7  # 7 días para mayor seguridad

# Forzar la SECRET_KEY para asegurar consistencia - ULTRA SEGURA
settings.SECRET_KEY = "zeus_ia_super_secure_secret_key_2024_production_ultra_strong_256_bits_minimum"
settings.ALGORITHM = "HS256"

# Log de la configuración para depuración
if settings.DEBUG:
    import logging
    logger = logging.getLogger(__name__)
    logger.info("=" * 80)
    logger.info("CONFIGURACIÓN DEL SISTEMA")
    logger.info("=" * 80)
    logger.info(f"SECRET_KEY: {'*' * 10 + settings.SECRET_KEY[-6:] if settings.SECRET_KEY else 'No definida'}")
    logger.info(f"ALGORITHM: {settings.ALGORITHM}")
    logger.info(f"ACCESS_TOKEN_EXPIRE_MINUTES: {settings.ACCESS_TOKEN_EXPIRE_MINUTES} minutos")
    logger.info(f"REFRESH_TOKEN_EXPIRE_DAYS: {settings.REFRESH_TOKEN_EXPIRE_DAYS} días")
    logger.info(f"DEBUG: {settings.DEBUG}")
    logger.info("=" * 80)
