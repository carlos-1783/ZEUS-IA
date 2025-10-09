"""
Middleware de seguridad para ZEUS-IA
"""
import time
from typing import Dict, List
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

class SecurityMiddleware:
    """Middleware para aplicar medidas de seguridad"""
    
    def __init__(self):
        self.rate_limit_store: Dict[str, List[float]] = {}
        self.blocked_ips: Dict[str, float] = {}
        
    async def __call__(self, request: Request, call_next):
        """Aplicar middleware de seguridad"""
        
        # 1. Verificar IP bloqueada
        client_ip = self.get_client_ip(request)
        if self.is_ip_blocked(client_ip):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "IP bloqueada temporalmente"}
            )
        
        # 2. Rate limiting
        if not self.check_rate_limit(client_ip, request.url.path):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Demasiadas solicitudes"}
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
                "img-src 'self' data: https:; "
                "connect-src 'self' wss: https:;"
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
    
    def check_rate_limit(self, ip: str, path: str) -> bool:
        """Verificar rate limiting"""
        current_time = time.time()
        window = 60  # 1 minuto
        
        # Límites por endpoint
        limits = {
            "/api/v1/auth/login": 5,  # 5 intentos por minuto
            "/api/v1/auth/register": 3,  # 3 registros por minuto
            "/api/": 100,  # 100 requests por minuto para API
            "/": 200  # 200 requests por minuto para frontend
        }
        
        # Determinar límite
        limit = limits.get("/api/", 100)  # Default
        for endpoint, endpoint_limit in limits.items():
            if path.startswith(endpoint):
                limit = endpoint_limit
                break
        
        # Limpiar requests antiguos
        if ip in self.rate_limit_store:
            self.rate_limit_store[ip] = [
                req_time for req_time in self.rate_limit_store[ip]
                if current_time - req_time < window
            ]
        else:
            self.rate_limit_store[ip] = []
        
        # Verificar límite
        if len(self.rate_limit_store[ip]) >= limit:
            # Bloquear IP si excede límite en endpoints críticos
            if path.startswith("/api/v1/auth/"):
                self.block_ip(ip)
            return False
        
        # Agregar request actual
        self.rate_limit_store[ip].append(current_time)
        return True

# Instancia global del middleware
security_middleware = SecurityMiddleware()
