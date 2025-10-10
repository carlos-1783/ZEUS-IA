from fastapi import FastAPI, Request, status, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse
from contextlib import asynccontextmanager
import time
import logging
import json
from typing import Dict, List, Optional
from fastapi.websockets import WebSocketState
from jose import JWTError, jwt
from app.core.config import settings
from app.core.security import verify_token

from app.core.config import settings
from app.api.v1.api import api_router
from app.core.security import get_password_hash

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Middleware para agregar cabeceras de seguridad
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Procesar la solicitud
        response = await call_next(request)

        # Configuración de cabeceras de seguridad
        security_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': settings.X_FRAME_OPTIONS,
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
            'Cross-Origin-Embedder-Policy': 'require-corp',
            'Cross-Origin-Opener-Policy': 'same-origin',
            'Cross-Origin-Resource-Policy': 'same-site',
            'Strict-Transport-Security': (
                f'max-age={settings.SECURE_HSTS_SECONDS}; includeSubDomains; preload'
                if not settings.DEBUG else ''
            )
        }

        # Content-Security-Policy
        csp_parts = [
            "default-src 'self';",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net;",
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net;",
            "img-src 'self' data: https:;",
            "font-src 'self' data:;",
            "connect-src 'self';",
            "frame-ancestors 'self';",
            "form-action 'self';",
            "base-uri 'self';",
            "object-src 'none';",
            "frame-src 'self';",
            "worker-src 'self' blob:;"
        ]
        security_headers['Content-Security-Policy'] = ' '.join(csp_parts)

        # Control de caché
        if request.url.path.startswith(settings.STATIC_URL):
            security_headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        else:
            security_headers['Cache-Control'] = 'no-store, max-age=0'

        # Aplicar cabeceras
        for header, value in security_headers.items():
            if value:
                response.headers[header] = value

        return response

# Configuración de la aplicación
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Código que se ejecuta al iniciar la aplicación
    logger.info("Iniciando ZEUS-IA...")
    logger.info(f"Entorno: {'Desarrollo' if settings.DEBUG else 'Producción'}")
    
    # Crear usuario admin si no existe
    await create_admin_user()
    
    yield
    
    # Código que se ejecuta al detener la aplicación
    logger.info("Deteniendo ZEUS-IA...")

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logging.info(f"Client {client_id} connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logging.info(f"Client {client_id} disconnected. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: str, client_id: str):
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            if websocket.client_state != WebSocketState.DISCONNECTED:
                try:
                    await websocket.send_text(message)
                except RuntimeError as e:
                    logging.error(f"Error sending message to {client_id}: {e}")
                    self.disconnect(client_id)

manager = ConnectionManager()

# JWT Authentication for WebSocket
async def get_websocket_token(
    websocket: WebSocket,
    token: Optional[str] = None
):
    if token is None:
        # Try to get token from query parameters
        query_params = dict(websocket.query_params)
        token = query_params.get('token')
        
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise WebSocketDisconnect(code=status.WS_1008_POLICY_VIOLATION)
    
    try:
        payload = verify_token(token)
        if payload is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            raise WebSocketDisconnect(code=status.WS_1008_POLICY_VIOLATION)
        return payload
    except JWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise WebSocketDisconnect(code=status.WS_1008_POLICY_VIOLATION)

# Crear instancia de FastAPI
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API de ZEUS-IA - Plataforma de automatización de marketing digital",
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=None,  # Deshabilitar docs por defecto
    redoc_url=None,  # Deshabilitar redoc por defecto
    lifespan=lifespan
)

# Configurar CORS
if settings.BACKEND_CORS_ORIGINS:
    # Convertir la lista de orígenes a una lista de strings
    origins = [str(origin) for origin in settings.BACKEND_CORS_ORIGINS]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=[
            "accept",
            "accept-encoding",
            "authorization",
            "content-type",
            "dnt",
            "origin",
            "user-agent",
            "x-csrftoken",
            "x-requested-with",
            "x-auth-token",
            "access-control-allow-headers",
            "access-control-allow-origin"
        ],
        expose_headers=["content-disposition"],
        max_age=600  # 10 minutos para preflight cache
    )

# Añadir middlewares
app.add_middleware(SecurityHeadersMiddleware)

# Middleware para compresión GZIP
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Redirección HTTPS en producción
if not settings.DEBUG:
    app.add_middleware(HTTPSRedirectMiddleware)

# Incluir rutas de la API
app.include_router(api_router, prefix=settings.API_V1_STR)

# Ruta de verificación de salud
@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.VERSION}

# Ruta raíz
@app.get("/")
async def root():
    return {
        "message": "Bienvenido a la API de ZEUS-IA",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "operational"
    }

# WebSocket endpoint
@app.websocket("/api/v1/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = None
):
    # Authenticate the connection
    try:
        payload = await get_websocket_token(websocket, token)
        client_id = f"client-{payload.get('sub', int(time.time()))}"
        
        await manager.connect(websocket, client_id)
        
        try:
            # Send initial connection confirmation
            await manager.send_personal_message(
                json.dumps({
                    'type': 'connection_established',
                    'data': {
                        'client_id': client_id,
                        'timestamp': int(time.time() * 1000)
                    }
                }),
                client_id
            )
            
            # Main message loop
            while True:
                data = await websocket.receive_text()
                try:
                    message = json.loads(data)
                    
                    # Handle different message types
                    if message.get('type') == 'ping':
                        response = {
                            'type': 'pong',
                            'data': {
                                'timestamp': int(time.time() * 1000),
                                'status': 'connected',
                                'client_id': client_id
                            }
                        }
                        await manager.send_personal_message(json.dumps(response), client_id)
                        
                    # Add more message handlers as needed
                    
                except json.JSONDecodeError:
                    # Handle non-JSON messages
                    response = {
                        'type': 'error',
                        'data': {
                            'message': 'Invalid JSON format',
                            'timestamp': int(time.time() * 1000)
                        }
                    }
                    await manager.send_personal_message(json.dumps(response), client_id)
                    
        except WebSocketDisconnect as e:
            logging.info(f"Client {client_id} disconnected: {e.code}")
            raise
            
    except WebSocketDisconnect as e:
        logging.warning(f"WebSocket connection rejected: {e.code}")
    except Exception as e:
        logging.error(f"WebSocket error: {str(e)}")
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
    finally:
        manager.disconnect(client_id)

# Función para crear usuario admin si no existe
async def create_admin_user():
    from sqlalchemy.orm import Session
    from app.db.session import SessionLocal
    from app.models.user import User
    
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == settings.FIRST_SUPERUSER).first()
        if not admin:
            admin_user = User(
                email=settings.FIRST_SUPERUSER,
                hashed_password=get_password_hash(settings.FIRST_SUPERUSER_PASSWORD),
                is_superuser=True,
                is_active=True,
                full_name="Admin"
            )
            db.add(admin_user)
            db.commit()
            logger.info("Usuario administrador creado exitosamente")
        else:
            logger.info("Usuario administrador ya existe")
    except Exception as e:
        logger.error(f"Error al crear usuario administrador: {str(e)}")
        db.rollback()
    finally:
        db.close()

# Manejo de errores global
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Error no manejado: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Error interno del servidor"},
    )

# Middleware para medir tiempo de respuesta
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response
