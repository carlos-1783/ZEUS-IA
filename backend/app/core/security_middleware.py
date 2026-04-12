"""Middleware de seguridad para ZEUS-IA."""
import time
from typing import Dict, List, Tuple
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import logging

logger = logging.getLogger(__name__)

class SecurityMiddleware(BaseHTTPMiddleware):
    """Middleware para aplicar medidas de seguridad"""
    
    def __init__(self, app):
        super().__init__(app)
        # key => timestamps dentro de la ventana
        # key combina IP + bucket de endpoint + clase de identidad.
        self.rate_limit_store: Dict[str, List[float]] = {}
        self.blocked_ips: Dict[str, float] = {}
        
    async def dispatch(self, request: Request, call_next):
        """Aplicar middleware de seguridad"""
        
        # 1. Verificar IP bloqueada
        client_ip = self.get_client_ip(request)
        if self.is_ip_blocked(client_ip):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "IP bloqueada temporalmente"}
            )
        
        # 2. Rate limiting
        allowed, retry_after, limit = self.check_rate_limit(request, client_ip, request.url.path)
        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Demasiadas solicitudes",
                    "retry_after_seconds": retry_after,
                    "limit_per_minute": limit,
                },
                headers={"Retry-After": str(max(1, int(retry_after)))},
            )
        
        # 3. Headers de seguridad
        response = await call_next(request)
        
        # Agregar headers de seguridad
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # CSP para endpoints específicos
        if request.url.path.startswith("/api/"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https: blob:; "
                "connect-src 'self' wss: https: blob: data: https://models.readyplayer.me;"
            )
        
        return response
    
    def get_client_ip(self, request: Request) -> str:
        """Obtener IP real del cliente"""
        # Verificar headers de proxy
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
    
    def is_ip_blocked(self, ip: str) -> bool:
        """Verificar si IP está bloqueada"""
        if ip in self.blocked_ips:
            # Verificar si el bloqueo ha expirado (1 hora)
            if time.time() - self.blocked_ips[ip] > 3600:
                del self.blocked_ips[ip]
                return False
            return True
        return False
    
    def block_ip(self, ip: str):
        """Bloquear IP temporalmente"""
        self.blocked_ips[ip] = time.time()
        logger.warning(f"IP bloqueada: {ip}")
    
    def _identity_key(self, request: Request, ip: str) -> str:
        """Separar tráfico autenticado del anónimo para evitar castigar toda una IP."""
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer ") and len(auth) > 20:
            # No persistimos el token completo; solo un prefijo para bucketing.
            return f"{ip}:auth:{auth[7:23]}"
        return f"{ip}:anon"

    def _bucket_and_limit(self, request: Request, path: str) -> Tuple[str, int]:
        """Devuelve bucket lógico y límite por minuto."""
        method = (request.method or "GET").upper()
        is_auth = request.headers.get("Authorization", "").lower().startswith("bearer ")

        # No limitar preflight/CORS
        if method == "OPTIONS":
            return ("preflight", 10_000)

        # No limitar health/static/service-worker para evitar falsos positivos
        if (
            path in ("/health", "/api/v1/health", "/service-worker.js")
            or path.startswith("/api/v1/video/health")
            or path.startswith("/api/video/health")
            or path.startswith("/assets/")
            or path.startswith("/static/")
        ):
            return ("public_static", 10_000)

        # Endpoints con polling frecuente en TPV/paneles
        if path.startswith("/api/v1/tpv/comanda-share/"):
            return ("tpv_comanda_poll", 1200 if is_auth else 300)
        # Escrituras de estado de mesas: en operación real puede haber ráfagas
        # por sincronización multi-dispositivo (barra/sala/comandero).
        if path.startswith("/api/v1/tpv/tables/") and method in ("PATCH", "PUT", "POST"):
            return ("tpv_tables_write", 2400 if is_auth else 300)
        if path.startswith("/api/v1/documents/pending") or path.startswith("/api/v1/document-approval/pending"):
            return ("documents_pending_poll", 600 if is_auth else 180)
        if path.startswith("/api/v1/tpv/tables") and method == "GET":
            return ("tpv_tables_poll", 600 if is_auth else 180)

        # Auth sensible: mantener estricto
        if path.startswith("/api/v1/auth/login"):
            return ("auth_login", 30)
        if path.startswith("/api/v1/auth/register"):
            return ("auth_register", 10)
        if path.startswith("/api/v1/auth/refresh"):
            return ("auth_refresh", 120)

        # Escrituras API: límite moderado
        if path.startswith("/api/") and method in ("POST", "PUT", "PATCH", "DELETE"):
            return ("api_write", 360 if is_auth else 120)

        # API general de lectura
        if path.startswith("/api/"):
            return ("api_read", 900 if is_auth else 240)

        # Frontend general
        return ("frontend", 300)

    def check_rate_limit(self, request: Request, ip: str, path: str) -> Tuple[bool, float, int]:
        """Verificar rate limiting y devolver (allowed, retry_after_seconds, limit)."""
        current_time = time.time()
        window = 60  # 1 minuto
        bucket, limit = self._bucket_and_limit(request, path)
        identity = self._identity_key(request, ip)
        key = f"{identity}:{bucket}"

        # Limpiar requests antiguos
        if key in self.rate_limit_store:
            self.rate_limit_store[key] = [
                req_time for req_time in self.rate_limit_store[key]
                if current_time - req_time < window
            ]
        else:
            self.rate_limit_store[key] = []

        # Verificar límite
        if len(self.rate_limit_store[key]) >= limit:
            oldest = self.rate_limit_store[key][0] if self.rate_limit_store[key] else current_time
            retry_after = max(1.0, window - (current_time - oldest))
            logger.warning(
                "Rate limited request ip=%s bucket=%s method=%s path=%s limit=%s",
                ip,
                bucket,
                request.method,
                path,
                limit,
            )
            # No bloquear IP de forma persistente; solo responder 429 temporal
            return False, retry_after, limit

        # Agregar request actual
        self.rate_limit_store[key].append(current_time)
        return True, 0.0, limit

# No crear instancia global: FastAPI la construye vía app.add_middleware(...)
