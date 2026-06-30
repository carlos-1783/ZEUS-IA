import logging
import os
import re
from typing import Dict, List, Optional, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()
logger = logging.getLogger("zeus.config")


def _is_railway_deploy() -> bool:
    return bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_SERVICE_NAME"))


def _stabilization_active() -> bool:
    return os.getenv("ZEUS_PRODUCTION_STABILIZATION", "true").lower() in ("true", "1", "yes")


def _production_default_true() -> str:
    """On Railway with stabilization, default critical flags to enabled."""
    if _stabilization_active() and _is_railway_deploy():
        return "true"
    return "false"

# Build Vite en imagen: /app/static con ZEUS_APP_ROOT=/app (Dockerfile); local sin env → …/backend/static.
_app_root = (os.getenv("ZEUS_APP_ROOT") or "").strip()
if _app_root:
    _PKG_STATIC_DIR = os.path.abspath(os.path.join(_app_root, "static"))
else:
    _PKG_STATIC_DIR = os.path.abspath(
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static")
    )
# Volumen persistente (p. ej. Railway /data/static): subidas, sin index.html del SPA.
_MAX_STATIC_PATH_LEN = 240
_EMBEDDED_FLAG_RE = re.compile(
    r'[A-Z][A-Z0-9_]*=(?:true|false|1|0|yes|no)\b',
    re.IGNORECASE,
)
_STD_STATIC_RE = re.compile(r"/(?:app/)?data/static\b")
_PATH_PREFIX_RE = re.compile(r"^(/[\w./-]+)")


def _sanitize_volatile_static_path(raw: str) -> str:
    """Strip flags accidentally pasted into STATIC_DIR on Railway."""
    s = (raw or "").strip()
    if not s:
        return s
    match = _STD_STATIC_RE.search(s)
    if match:
        cleaned = match.group(0)
        if cleaned != s:
            logger.warning(
                "STATIC_DIR sanitized from %r to %r — remove embedded env text in Railway",
                s[:120],
                cleaned,
            )
        return cleaned
    for marker in ('"', "'", "AFRODITA_", "THALOS_", "JUSTICE_", "ZEUS_", "TEAMFLOW_"):
        if marker in s:
            s = s.split(marker, 1)[0].rstrip("/\"'")
            logger.warning(
                "STATIC_DIR truncated at %r — fix Railway variable (was %r)",
                marker,
                raw[:120],
            )
            break
    return s


def _finalize_static_dir_path(raw: str, *, fallback: Optional[str] = None) -> str:
    """
    Resolve a safe absolute static path. Corrupted Railway values must never crash startup.
    """
    fb = os.path.abspath(fallback or _PKG_STATIC_DIR)
    if not (raw or "").strip():
        return fb

    s = _sanitize_volatile_static_path(raw)
    s = _EMBEDDED_FLAG_RE.sub("", s)
    s = re.sub(r'"+', "", s).strip().strip("\"'")
    if not s:
        logger.error("STATIC_DIR empty after sanitize (was %r) — using %s", raw[:120], fb)
        return fb

    std = _STD_STATIC_RE.search(s)
    if std:
        s = std.group(0)
    elif not os.path.isabs(s):
        prefix = _PATH_PREFIX_RE.match(s)
        if prefix:
            s = prefix.group(1)
        else:
            logger.error("STATIC_DIR not a path (was %r) — using %s", raw[:120], fb)
            return fb

    try:
        resolved = os.path.abspath(s)
    except (OSError, ValueError) as exc:
        logger.error("STATIC_DIR invalid %r (%s) — using %s", raw[:120], exc, fb)
        return fb

    if len(resolved) > _MAX_STATIC_PATH_LEN:
        logger.error(
            "STATIC_DIR path too long (%d chars, was %r) — using %s",
            len(resolved),
            raw[:120],
            fb,
        )
        return fb

    if resolved != os.path.abspath((raw or "").strip()):
        logger.warning(
            "STATIC_DIR resolved %r → %r — set Railway STATIC_DIR/ZEUS_STATIC_DIR to path only (e.g. /data/static)",
            raw[:120],
            resolved,
        )
    return resolved


def _resolve_static_dir_from_env() -> str:
    raw = (os.getenv("ZEUS_STATIC_DIR") or os.getenv("STATIC_DIR") or "").strip()
    if raw:
        return _finalize_static_dir_path(raw)
    return _PKG_STATIC_DIR


_ENV_VOLATILE_STATIC = (os.getenv("ZEUS_STATIC_DIR") or os.getenv("STATIC_DIR") or "").strip()
_RESOLVED_STATIC_DIR = _resolve_static_dir_from_env() if _ENV_VOLATILE_STATIC else _PKG_STATIC_DIR
_SPA_OVERRIDE = (os.getenv("ZEUS_SPA_STATIC_DIR") or "").strip()
if _SPA_OVERRIDE:
    _RESOLVED_SPA_STATIC_DIR = os.path.abspath(_SPA_OVERRIDE)
elif _ENV_VOLATILE_STATIC:
    # STATIC_DIR apunta a volumen: el Vue sigue en la imagen bajo _PKG_STATIC_DIR.
    _RESOLVED_SPA_STATIC_DIR = _PKG_STATIC_DIR
else:
    _RESOLVED_SPA_STATIC_DIR = _RESOLVED_STATIC_DIR


class Settings(BaseSettings):
    # Application
    PROJECT_NAME: str = "ZEUS-IA"
    VERSION: str = "1.0.6"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", os.getenv("RAILWAY_ENVIRONMENT", "production"))
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
    
    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    RELOAD: bool = DEBUG
    
    # STATIC_DIR: subidas y /static (puede ser volumen, p. ej. /data/static).
    # SPA_STATIC_DIR: index.html + assets del build Vite (imagen Docker); si hay volumen, sigue siendo _PKG_STATIC_DIR salvo ZEUS_SPA_STATIC_DIR.
    STATIC_URL: str = "/static"
    STATIC_DIR: str = _RESOLVED_STATIC_DIR
    SPA_STATIC_DIR: str = _RESOLVED_SPA_STATIC_DIR
    # Origen público del API (sin barra final). Subidas: URL absoluta del vídeo/imagen. Ej. https://tu-app.up.railway.app
    PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    PERSEO_IMAGES_ENABLED: bool = os.getenv("PERSEO_IMAGES_ENABLED", "true").lower() in ("true", "1", "yes")
    # Tras chat PERSEO con imagen (sin vídeo adjunto), generar MP4/GIF de presentación en segundo plano
    PERSEO_CHAT_AUTO_VIDEO: bool = os.getenv("PERSEO_CHAT_AUTO_VIDEO", "true").lower() in ("true", "1", "yes")
    # Segundos por diapositiva en el MP4/GIF de presentación PERSEO (chat con imagen)
    PERSEO_VIDEO_SECONDS_PER_SLIDE: float = float(os.getenv("PERSEO_VIDEO_SECONDS_PER_SLIDE", "5") or "5")
    # Calidad tipo “presentación pro”: 16:9 (alto = ancho * 9/16). Máx. razonable 4K ancho.
    PERSEO_VIDEO_WIDTH: int = int(os.getenv("PERSEO_VIDEO_WIDTH", "1920") or "1920")
    PERSEO_VIDEO_FPS: int = int(os.getenv("PERSEO_VIDEO_FPS", "24") or "24")
    PERSEO_VIDEO_CROSSFADE_SEC: float = float(os.getenv("PERSEO_VIDEO_CROSSFADE_SEC", "0.45") or "0.45")
    # libx264 CRF (menor = más calidad, ~18–23 típico). No sustituye a un modelo generativo tipo Veo.
    PERSEO_VIDEO_CRF: int = int(os.getenv("PERSEO_VIDEO_CRF", "20") or "20")
    # libx264 preset: veryfast/ultrafast ahorra CPU y RAM en Railway; "slow" solo con mucho recurso.
    PERSEO_FFMPEG_PRESET: str = os.getenv("PERSEO_FFMPEG_PRESET", "veryfast").strip() or "veryfast"
    # Tiempo máximo (s) para la generación MP4/GIF en el job en background (evita pending infinito).
    PERSEO_VIDEO_JOB_TIMEOUT_SEC: float = float(os.getenv("PERSEO_VIDEO_JOB_TIMEOUT_SEC", "240") or "240")
    # Control horario: si true y hay user_companies pero 0 filas en company_employees, roster vacío (sin demo en front).
    # Si false, el roster BD se usa igualmente cuando exista al menos un empleado en BD para las empresas del usuario.
    CONTROL_HORARIO_DB_EMPLOYEES: bool = False
    # Control horario inteligente (geofencing opcional, ratios TPV, alertas)
    CONTROL_HORARIO_OFFICE_LAT: str = os.getenv("CONTROL_HORARIO_OFFICE_LAT", "").strip()
    CONTROL_HORARIO_OFFICE_LON: str = os.getenv("CONTROL_HORARIO_OFFICE_LON", "").strip()
    CONTROL_HORARIO_OFFICE_RADIUS_M: str = os.getenv("CONTROL_HORARIO_OFFICE_RADIUS_M", "").strip()
    CONTROL_HORARIO_FAIL_IF_OUTSIDE_ZONE: bool = os.getenv(
        "CONTROL_HORARIO_FAIL_IF_OUTSIDE_ZONE", "false"
    ).lower() in ("true", "1", "yes")
    CONTROL_HORARIO_ALERT_GRACE_MINUTES: int = int(os.getenv("CONTROL_HORARIO_ALERT_GRACE_MINUTES", "15") or "15")
    CONTROL_HORARIO_TPV_HIGH_RATIO: float = float(os.getenv("CONTROL_HORARIO_TPV_HIGH_RATIO", "1.35") or "1.35")
    CONTROL_HORARIO_TPV_LOW_RATIO: float = float(os.getenv("CONTROL_HORARIO_TPV_LOW_RATIO", "0.65") or "0.65")
    SMART_TIME_CONTROL_LOG_AFRODITA: bool = os.getenv(
        "SMART_TIME_CONTROL_LOG_AFRODITA", "true"
    ).lower() in ("true", "1", "yes")
    IMAGE_STORAGE: str = os.getenv("IMAGE_STORAGE", "local")
    PERSEO_IMAGE_UPLOAD_DIR: str = os.getenv(
        "PERSEO_IMAGE_UPLOAD_DIR",
        os.path.join(STATIC_DIR, "uploads", "perseo"),
    )
    PERSEO_IMAGE_MAX_BYTES: int = int(os.getenv("PERSEO_IMAGE_MAX_BYTES", str(5 * 1024 * 1024)))

    # PERSEO V2 — cloud storage, transactional engines, queue workers
    PERSEO_V2_ENABLED: bool = os.getenv("PERSEO_V2_ENABLED", "false").lower() in ("true", "1", "yes")
    PERSEO_STORAGE_BACKEND: str = os.getenv("PERSEO_STORAGE_BACKEND", "local").strip().lower()
    AWS_S3_BUCKET: str = os.getenv("AWS_S3_BUCKET", "").strip()
    AWS_S3_REGION: str = os.getenv("AWS_S3_REGION", os.getenv("AWS_REGION", "eu-west-1")).strip()
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "").strip()
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "").strip()
    AWS_S3_PUBLIC_URL_PREFIX: str = os.getenv("AWS_S3_PUBLIC_URL_PREFIX", "").strip().rstrip("/")
    AWS_S3_SIGNED_URL_TTL_SEC: int = int(os.getenv("AWS_S3_SIGNED_URL_TTL_SEC", "3600") or "3600")
    REPLICATE_API_TOKEN: str = os.getenv("REPLICATE_API_TOKEN", "").strip()
    STABILITY_API_KEY: str = os.getenv("STABILITY_API_KEY", "").strip()
    PERSEO_IMAGE_PROVIDER: str = os.getenv("PERSEO_IMAGE_PROVIDER", "replicate").strip().lower()
    PERSEO_AI_MODEL: str = os.getenv("PERSEO_AI_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o")).strip()
    PERSEO_VIDEO_GEN_MAX_SEC: int = int(os.getenv("PERSEO_VIDEO_GEN_MAX_SEC", "10") or "10")
    INSTAGRAM_ACCESS_TOKEN: str = os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()
    INSTAGRAM_BUSINESS_ACCOUNT_ID: str = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "").strip()
    YOUTUBE_ACCESS_TOKEN: str = os.getenv("YOUTUBE_ACCESS_TOKEN", "").strip()
    TIKTOK_ACCESS_TOKEN: str = os.getenv("TIKTOK_ACCESS_TOKEN", "").strip()

    # THALOS v1 — ejecución real detrás de flags (thalos_safe_audit_v1)
    THALOS_ENABLED: bool = os.getenv("THALOS_ENABLED", "true").lower() in ("true", "1", "yes")
    THALOS_WORKER_INTERVAL_SEC: int = int(os.getenv("THALOS_WORKER_INTERVAL_SEC", "30") or "30")
    THALOS_LOG_PATH: str = os.getenv("THALOS_LOG_PATH", "logs/zeus.log").strip()
    THALOS_EXECUTION_ENABLED: bool = os.getenv("THALOS_EXECUTION_ENABLED", "false").lower() in (
        "true",
        "1",
        "yes",
    )
    THALOS_AUTO_BLOCK: bool = os.getenv("THALOS_AUTO_BLOCK", "false").lower() in ("true", "1", "yes")
    THALOS_REAL_MONITORING: bool = os.getenv("THALOS_REAL_MONITORING", "false").lower() in (
        "true",
        "1",
        "yes",
    )
    THALOS_WORKSPACE_WRITE_ENABLED: bool = os.getenv("THALOS_WORKSPACE_WRITE_ENABLED", "true").lower() in (
        "true",
        "1",
        "yes",
    )
    THALOS_REAL_LOGS_ENABLED: bool = os.getenv("THALOS_REAL_LOGS_ENABLED", "false").lower() in (
        "true",
        "1",
        "yes",
    )
    THALOS_BACKUP_ENABLED: bool = os.getenv("THALOS_BACKUP_ENABLED", "false").lower() in (
        "true",
        "1",
        "yes",
    )

    # afrodita_control_layer_v1 — missing env → false (see config/afrodita_flags_v1.py)
    AFRODITA_EXECUTION_ENABLED: bool = os.getenv(
        "AFRODITA_EXECUTION_ENABLED", _production_default_true()
    ).lower() in (
        "true",
        "1",
        "yes",
    )
    AFRODITA_READ_ONLY_MODE: bool = os.getenv("AFRODITA_READ_ONLY_MODE", "false").lower() in (
        "true",
        "1",
        "yes",
    )
    AFRODITA_USE_REAL_EMPLOYEES: bool = os.getenv("AFRODITA_USE_REAL_EMPLOYEES", "true").lower() in (
        "true",
        "1",
        "yes",
    )
    AFRODITA_USE_REAL_CHECKINS: bool = os.getenv("AFRODITA_USE_REAL_CHECKINS", "true").lower() in (
        "true",
        "1",
        "yes",
    )
    AFRODITA_USE_REAL_SCHEDULES: bool = os.getenv("AFRODITA_USE_REAL_SCHEDULES", "true").lower() in (
        "true",
        "1",
        "yes",
    )
    AFRODITA_WORKSPACE_ENABLED: bool = os.getenv("AFRODITA_WORKSPACE_ENABLED", "true").lower() in (
        "true",
        "1",
        "yes",
    )

    # afrodita_ops_control_layer_v1
    AFRODITA_OPS_ENABLED: bool = os.getenv(
        "AFRODITA_OPS_ENABLED", _production_default_true()
    ).lower() in (
        "true",
        "1",
        "yes",
    )
    AFRODITA_OPS_READ_ONLY: bool = os.getenv("AFRODITA_OPS_READ_ONLY", "false").lower() in (
        "true",
        "1",
        "yes",
    )
    AFRODITA_USE_TPV: bool = os.getenv("AFRODITA_USE_TPV", "true").lower() in ("true", "1", "yes")
    AFRODITA_USE_ERP: bool = os.getenv("AFRODITA_USE_ERP", "true").lower() in ("true", "1", "yes")
    AFRODITA_ENABLE_STOCK_SYNC: bool = os.getenv("AFRODITA_ENABLE_STOCK_SYNC", "false").lower() in (
        "true",
        "1",
        "yes",
    )
    AFRODITA_ENABLE_ROUTE_ENGINE: bool = os.getenv("AFRODITA_ENABLE_ROUTE_ENGINE", "false").lower() in (
        "true",
        "1",
        "yes",
    )

    # JUSTICIA v1 — auditoría real + documentos legales en BD
    JUSTICE_ENABLED: bool = os.getenv("JUSTICE_ENABLED", "true").lower() in ("true", "1", "yes")
    JUSTICE_REAL_AUDIT_ENABLED: bool = os.getenv("JUSTICE_REAL_AUDIT_ENABLED", "true").lower() in (
        "true",
        "1",
        "yes",
    )
    JUSTICE_READ_ONLY_MODE: bool = os.getenv("JUSTICE_READ_ONLY_MODE", "true").lower() in (
        "true",
        "1",
        "yes",
    )

    # TeamFlow — cross-agent orchestration with DB persistence
    TEAMFLOW_ENABLED: bool = os.getenv("TEAMFLOW_ENABLED", "true").lower() in ("true", "1", "yes")
    TEAMFLOW_STRICT_AUDIT: bool = os.getenv("TEAMFLOW_STRICT_AUDIT", "true").lower() in ("true", "1", "yes")
    ZEUS_AGENT_ENABLED: bool = os.getenv("ZEUS_AGENT_ENABLED", "true").lower() in ("true", "1", "yes")

    # zeus_total_system_closure_v1
    ZEUS_TOTAL_SYSTEM_CLOSURE_ENABLED: bool = os.getenv(
        "ZEUS_TOTAL_SYSTEM_CLOSURE_ENABLED", "false"
    ).lower() in ("true", "1", "yes")
    ZEUS_CORE_GUARD_ENFORCE: bool = os.getenv("ZEUS_CORE_GUARD_ENFORCE", "false").lower() in (
        "true",
        "1",
        "yes",
    )
    
    # Security - Configuración de JWT SEGURA PARA PRODUCCIÓN
    # IMPORTANTE: En producción, SIEMPRE usar variables de entorno para SECRET_KEY
    # El valor por defecto es solo para desarrollo local
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev_default_secret_key_change_in_production_1b6ed3a2f7c62ea379032ddd1fa9b19b")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))  # 30 minutos por defecto
    
    # Configuración de JWT
    JWT_AUDIENCE: List[str] = ["zeus-ia:auth", "zeus-ia:access", "zeus-ia:websocket"]  # Lista de audiencias válidas
    JWT_ISSUER: str = "zeus-ia-backend"  # Emisor del token
    JWT_ACCESS_TOKEN_TYPE: str = "access"
    JWT_WEBSOCKET_TOKEN_TYPE: str = "websocket"
    
    # Validar clave secreta
    if not SECRET_KEY:
        raise ValueError("La SECRET_KEY no puede estar vacía")
    _env = os.getenv("ENVIRONMENT", os.getenv("RAILWAY_ENVIRONMENT", "production")).lower()
    # No bloquear arranque en producción por compatibilidad operativa.
    # Se mantiene la advertencia para que se corrija en variables de entorno.
    if _env == "production" and "dev_default_secret" in (SECRET_KEY or ""):
        logger.warning(
            "[SECURITY] SECRET_KEY de desarrollo detectada en producción. "
            "Configurar SECRET_KEY segura en variables de entorno de Railway."
        )
    
    # Token refresh settings
    REFRESH_TOKEN_SECRET: str = os.getenv("REFRESH_TOKEN_SECRET", "dev_default_refresh_secret_934ce6750fb8c844e26972be922326cbd0ff924c")
    REFRESH_TOKEN_LENGTH: int = 64
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))  # 7 días por defecto
    REFRESH_TOKEN_GRACE_PERIOD_DAYS: int = 7  # Grace period for token reuse detection
    
    # Jornada laboral (empleado): cierre automático por inactividad en API TPV
    WORK_SESSION_IDLE_MINUTES: int = int(os.getenv("WORK_SESSION_IDLE_MINUTES", "30"))
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'zeus.db')}")
    
    # Frontend URL (para enlaces en emails, p. ej. reset password)
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")

    # CORS Configuration - SIMPLIFICADO PARA DESARROLLO
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://zeus-ia-production-16d8.up.railway.app",
        "https://zeus-ia.com",
        "https://app.zeus-ia.com",
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

    # Scopes / permisos
    DEFAULT_SCOPE_MAP: Dict[str, List[str]] = {
        "marketingdigitalper.seo@gmail.com": [
            "marketing:read",
            "marketing:write",
            "tax:read",
            "tax:write",
            "legal:read",
            "legal:write",
            "hr:read",
            "hr:write",
        ]
    }
    
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

    @field_validator("STATIC_DIR", mode="before")
    @classmethod
    def _validate_static_dir(cls, value: object) -> str:
        if value is None or str(value).strip() == "":
            return _resolve_static_dir_from_env()
        return _finalize_static_dir_path(str(value))

    @field_validator("SPA_STATIC_DIR", mode="before")
    @classmethod
    def _validate_spa_static_dir(cls, value: object) -> str:
        if value is None or str(value).strip() == "":
            return _PKG_STATIC_DIR
        raw = str(value)
        if _EMBEDDED_FLAG_RE.search(raw) or any(
            m in raw for m in ("AFRODITA_", "THALOS_", "JUSTICE_", "TEAMFLOW_")
        ):
            logger.warning("SPA_STATIC_DIR corrupted (%r) — using packaged static", raw[:120])
            return _PKG_STATIC_DIR
        try:
            resolved = os.path.abspath(raw.strip().strip("'\""))
            if len(resolved) > _MAX_STATIC_PATH_LEN:
                return _PKG_STATIC_DIR
            return resolved
        except (OSError, ValueError):
            return _PKG_STATIC_DIR

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
    logger.debug("[SECURITY] Clave original: %s... (longitud: %s caracteres)", secret_key[:5], len(secret_key))
    
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
    
    logger.debug("[SECURITY] Clave final: %s... (longitud: %s caracteres)", secret_key[:5], len(secret_key))
    return secret_key

# Crear instancia de configuración
settings = Settings()
settings.STATIC_DIR = _finalize_static_dir_path(settings.STATIC_DIR)
settings.SPA_STATIC_DIR = _finalize_static_dir_path(
    settings.SPA_STATIC_DIR,
    fallback=_PKG_STATIC_DIR,
)


def ensure_static_root_ready() -> str:
    """
    Create upload directories without crashing gunicorn on corrupted STATIC_DIR.
    Mutates settings.STATIC_DIR when falling back.
    """
    root = _finalize_static_dir_path(settings.STATIC_DIR)
    if root != settings.STATIC_DIR:
        settings.STATIC_DIR = root
    try:
        os.makedirs(root, exist_ok=True)
        for sub in ("images", "videos", "documents", "media"):
            os.makedirs(os.path.join(root, "uploads", sub), exist_ok=True)
    except OSError as exc:
        logger.error(
            "Cannot create STATIC_DIR %r (%s) — falling back to %s",
            root,
            exc,
            _PKG_STATIC_DIR,
        )
        root = _PKG_STATIC_DIR
        settings.STATIC_DIR = root
        os.makedirs(root, exist_ok=True)
        for sub in ("images", "videos", "documents", "media"):
            os.makedirs(os.path.join(root, "uploads", sub), exist_ok=True)
    return root


def _spa_index_exists(path: str) -> bool:
    try:
        return os.path.isfile(os.path.join(os.path.abspath(path), "index.html"))
    except OSError:
        return False


# Railway: si ZEUS_SPA_STATIC_DIR apunta al volumen (sin index) o Pydantic dejó SPA mal, usar el dist empaquetado.
if not _spa_index_exists(settings.SPA_STATIC_DIR) and _spa_index_exists(_PKG_STATIC_DIR):
    logger.warning(
        "SPA_STATIC_DIR=%s no contiene index.html; usando build empaquetado %s",
        settings.SPA_STATIC_DIR,
        _PKG_STATIC_DIR,
    )
    settings.SPA_STATIC_DIR = _PKG_STATIC_DIR

# Extender dinámicamente orígenes CORS si existen variables adicionales
extra_cors = os.getenv("ZEUS_ADDITIONAL_CORS_ORIGINS")
if extra_cors:
    extras = [origin.strip() for origin in extra_cors.split(",") if origin.strip()]
    settings.BACKEND_CORS_ORIGINS = list(dict.fromkeys(settings.BACKEND_CORS_ORIGINS + extras))

# ZEUS_LOCAL_CORS_FIX_001: En desarrollo local, garantizar orígenes localhost para preflight
# Solo aplica cuando NO estamos en Railway (evita tocar producción)
_is_railway = bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_SERVICE_NAME"))
_env_dev = (os.getenv("ENVIRONMENT", "").lower() == "development" or os.getenv("DEBUG", "").lower() in ("true", "1", "t"))
if _env_dev and not _is_railway:
    _local_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
    _combined = list(dict.fromkeys(_local_origins + list(settings.BACKEND_CORS_ORIGINS)))
    settings.BACKEND_CORS_ORIGINS = _combined
    logger.info("[CORS] Modo desarrollo local: orígenes localhost garantizados para preflight (sin afectar Railway)")

# Validar y asegurar el formato de la clave secreta
try:
    settings.SECRET_KEY = ensure_secret_key_format(settings.SECRET_KEY)
    logger.info("[SECURITY] Clave secreta configurada correctamente. Longitud: %s caracteres", len(settings.SECRET_KEY))
    logger.debug("[SECURITY] Muestra de clave: %s...", settings.SECRET_KEY[:5])
except ValueError as e:
    logger.error("Error en la configuración de la clave secreta: %s", str(e))
    raise

# NOTA IMPORTANTE: Las claves SECRET_KEY deben ser configuradas en variables de entorno
# NO usar valores hardcodeados en producción. Estos son valores por defecto solo para desarrollo.
# En Railway/Vercel, configurar las variables de entorno según RAILWAY_VARIABLES_ZEUS_PRODUCTION.txt

# Los valores finales se obtienen de las variables de entorno o usan los defaults
# settings.ACCESS_TOKEN_EXPIRE_MINUTES ya está configurado en la clase Settings (línea 29)
# settings.REFRESH_TOKEN_EXPIRE_DAYS ya está configurado en la clase Settings (línea 43)
# settings.SECRET_KEY ya está configurado y validado en ensure_secret_key_format()
# settings.ALGORITHM ya está configurado en la clase Settings (línea 28)

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
