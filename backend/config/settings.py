"""
⚡ ZEUS-IA Configuration Settings ⚡
Configuración centralizada del sistema
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Configuración de la aplicación"""
    
    # =============================================================================
    # OPENAI API
    # =============================================================================
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    # 0 = inferir del nombre del modelo (p. ej. gpt-4o-mini → 128k; gpt-4 legacy → 8k)
    OPENAI_CONTEXT_LIMIT: int = int(os.getenv("OPENAI_CONTEXT_LIMIT", "0"))
    OPENAI_MAX_TOKENS: int = int(os.getenv("OPENAI_MAX_TOKENS", "2000"))
    OPENAI_TEMPERATURE: float = float(os.getenv("OPENAI_TEMPERATURE", "0.3"))
    # Timeout por petición al API OpenAI (segundos). Chat + contexto largo puede superar 60s.
    OPENAI_TIMEOUT_SEC: float = float(os.getenv("OPENAI_TIMEOUT_SEC", "120") or "120")
    
    # =============================================================================
    # DATABASE
    # =============================================================================
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./zeus_ia.db")
    
    # =============================================================================
    # REDIS
    # =============================================================================
    REDIS_URL: str = os.getenv("REDIS_URL", "")
    
    # =============================================================================
    # APPLICATION
    # =============================================================================
    APP_ENV: str = os.getenv("APP_ENV", "development")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key")
    
    # =============================================================================
    # CORS
    # =============================================================================
    ALLOWED_ORIGINS: str = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://localhost:3000,https://zeus-ia-production-16d8.up.railway.app"
    )
    
    # =============================================================================
    # NOTIFICATIONS
    # =============================================================================
    SENDGRID_API_KEY: Optional[str] = os.getenv("SENDGRID_API_KEY")
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@zeus-ia.com")
    SLACK_WEBHOOK_URL: Optional[str] = os.getenv("SLACK_WEBHOOK_URL")
    
    # =============================================================================
    # AGENTS CONFIG
    # =============================================================================
    HITL_ENABLED: bool = os.getenv("HITL_ENABLED", "true").lower() == "true"
    AUDIT_LOGS_ENABLED: bool = os.getenv("AUDIT_LOGS_ENABLED", "true").lower() == "true"
    ROLLBACK_ENABLED: bool = os.getenv("ROLLBACK_ENABLED", "true").lower() == "true"
    SHADOW_MODE: bool = os.getenv("SHADOW_MODE", "false").lower() == "true"
    
    # =============================================================================
    # LIMITS & SAFEGUARDS
    # =============================================================================
    MAX_REQUESTS_PER_MINUTE: int = int(os.getenv("MAX_REQUESTS_PER_MINUTE", "60"))
    MAX_OPENAI_COST_PER_DAY: float = float(os.getenv("MAX_OPENAI_COST_PER_DAY", "20.0"))
    # Máx. mensajes user+assistant en buffer por hilo (evita prompts gigantes en BD)
    AGENT_SHORT_TERM_MAX_MESSAGES: int = int(os.getenv("AGENT_SHORT_TERM_MAX_MESSAGES", "36"))
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignorar variables extra del .env


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Global settings instance
settings = get_settings()


def resolved_openai_context_limit(model: Optional[str] = None) -> int:
    """
    Tokens de contexto total del modelo (prompt + completion).
    OPENAI_CONTEXT_LIMIT > 0 fuerza un valor fijo (útil en Railway si el nombre del modelo no coincide).
    """
    s = get_settings()
    if getattr(s, "OPENAI_CONTEXT_LIMIT", 0) and s.OPENAI_CONTEXT_LIMIT > 0:
        return s.OPENAI_CONTEXT_LIMIT
    m = (model or s.OPENAI_MODEL or "").lower()
    if "gpt-3.5" in m:
        return 16384
    if "gpt-4o" in m or "gpt-4.1" in m:
        return 128000
    if "gpt-4" in m and any(
        x in m for x in ("turbo", "0125", "1106", "preview")
    ):
        return 128000
    if "gpt-4" in m:
        return 8192
    return 16384


# Validación al inicio
def validate_settings():
    """Validar configuración crítica"""
    errors = []
    
    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "your-api-key-here":
        errors.append("[X] OPENAI_API_KEY no configurada")
    
    if not settings.DATABASE_URL:
        errors.append("[!] DATABASE_URL no configurada (usarás SQLite local)")
    
    if errors:
        print("\nZEUS-IA Configuration Issues:")
        for error in errors:
            print(f"  {error}")
        print()
    
    return len(errors) == 0


# Validar al importar
if __name__ != "__main__":
    validate_settings()

