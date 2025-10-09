from fastapi import Request, Response
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.cors import CORSMiddleware
from app.config import settings  # Actualizado para usar el archivo de configuración principal

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware para agregar cabeceras de seguridad HTTP."""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Solo aplicar a respuestas HTML/JS/CSS
        content_type = response.headers.get("content-type", "")
        if not any(x in content_type for x in ["text/html", "application/javascript", "text/css"]):
            return response
            
        # Configuración de cabeceras de seguridad
        security_headers = {
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
            "X-XSS-Protection": "1; mode=block",
            "Content-Security-Policy": "default-src 'self';",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
            "Cross-Origin-Embedder-Policy": "require-corp",
            "Cross-Origin-Opener-Policy": "same-origin",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload"
        }
        
        for header, value in security_headers.items():
            response.headers[header] = value
            
        return response

def setup_middlewares(app):
    """Configura todos los middlewares de la aplicación."""
    
    # CORS Middleware Configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
        expose_headers=settings.CORS_EXPOSE_HEADERS,
        max_age=getattr(settings, 'CORS_MAX_AGE', 600),  # Usar valor por defecto si no existe
    )
    
    # GZip Middleware
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # Security Headers
    app.add_middleware(SecurityHeadersMiddleware)
    
    # Session Middleware
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.SECRET_KEY,
        session_cookie="zeus_session",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    
    # Trusted Host Middleware (solo en producción)
    if not settings.DEBUG:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])  # Reemplazar con dominios reales
    
    return app
