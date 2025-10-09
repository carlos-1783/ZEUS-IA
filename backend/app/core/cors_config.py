"""
Configuración de CORS para ZEUS-IA
"""
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings

def get_cors_middleware():
    """Configurar middleware de CORS"""
    
    # Orígenes permitidos
    allowed_origins = [
        "https://zeusia.app",
        "https://www.zeusia.app",
        "https://api.zeusia.app",
    ]
    
    # Agregar orígenes de desarrollo si está en modo debug
    if settings.DEBUG:
        allowed_origins.extend([
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ])
    
    return CORSMiddleware(
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=[
            "Accept",
            "Accept-Language",
            "Content-Language",
            "Content-Type",
            "Authorization",
            "X-Requested-With",
            "X-CSRFToken",
            "X-API-Key",
        ],
        expose_headers=[
            "Content-Disposition",
            "X-Total-Count",
            "X-Page-Count",
        ],
        max_age=3600,  # Cache preflight por 1 hora
    )
