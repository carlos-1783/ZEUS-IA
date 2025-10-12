import os
import json
import logging
from contextlib import asynccontextmanager
from typing import Callable, Awaitable

from fastapi import FastAPI, Request, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response, FileResponse, JSONResponse, RedirectResponse
from fastapi import status as http_status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.middlewares import setup_middlewares
from app.core.routes import setup_routes
from app.core.docs import setup_docs, set_custom_openapi
from app.core.logging_config import setup_logging

# Configurar logging
logger = setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestor del ciclo de vida de la aplicación.
    
    Args:
        app: Instancia de FastAPI
    """
    # Inicio de la aplicación
    logger.info(f"Iniciando {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info(f"Entorno: {'Desarrollo' if settings.DEBUG else 'Producción'}")
    logger.info(f"Servidor ejecutándose en http://{settings.HOST}:{settings.PORT}")
    
    # Crear directorios necesarios
    os.makedirs(settings.STATIC_DIR, exist_ok=True)
    logger.debug(f"Directorio estático: {os.path.abspath(settings.STATIC_DIR)}")
    
    logger.info("Aplicación iniciada correctamente")
    yield
    
    # Limpieza al cerrar
    logger.info("Deteniendo la aplicación...")

# Configuración de metadatos de la API
api_metadata = {
    "title": settings.PROJECT_NAME,
    "description": """
    # ZEUS-IA API
    
    Bienvenido a la documentación de la API de ZEUS-IA.
    
    ## Autenticación
    
    La mayoría de los endpoints requieren autenticación. Para autenticarse, use el endpoint `/api/v1/auth/login`
    con sus credenciales para obtener un token de acceso.
    
    Incluya el token en el encabezado `Authorization: Bearer <token>` para las solicitudes autenticadas.
    """,
    "version": settings.VERSION,
    "debug": settings.DEBUG,
    "docs_url": "/api/docs" if settings.DEBUG else None,
    "redoc_url": "/api/redoc" if settings.DEBUG else None,
    "openapi_url": "/api/openapi.json" if settings.DEBUG else None,
    "openapi_tags": [
        {
            "name": "auth",
            "description": "Operaciones de autenticación y usuarios"
        },
        {
            "name": "system",
            "description": "Operaciones del sistema"
        },
        {
            "name": "commands",
            "description": "Ejecución de comandos"
        },
        {
            "name": "customers",
            "description": "Gestión de clientes"
        }
    ]
}

# Crear instancia de FastAPI
app = FastAPI(
    **{k: v for k, v in api_metadata.items() if k not in ['debug']},
    lifespan=lifespan,
    redirect_slashes=False  # Deshabilitar redirect automático para healthcheck
)

# Configurar middlewares
setup_middlewares(app)

# Configurar rutas
setup_routes(app)

# Configurar documentación
setup_docs(app)

# Aplicar esquema OpenAPI personalizado
app.openapi = lambda: set_custom_openapi(app)

# Configuración de CORS
# Usar los orígenes de la configuración
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=["*"],
    expose_headers=["*"],
)

# Middleware para asegurar que los encabezados CORS estén presentes
# y manejar correctamente las solicitudes OPTIONS (preflight)
@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    # Handle WebSocket upgrade requests
    if "upgrade" in request.headers.get("connection", "").lower() and \
       request.headers.get("upgrade", "").lower() == "websocket":
        # For WebSocket connections, we need to handle CORS manually
        origin = request.headers.get("origin")
        if origin and origin in settings.BACKEND_CORS_ORIGINS:
            response = await call_next(request)
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Headers"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            return response
        else:
            return Response(
                content=json.dumps({"detail": "Not allowed by CORS"}),
                status_code=403,
                media_type="application/json"
            )
        
    # Handle OPTIONS (preflight) requests
    if request.method == "OPTIONS":
        origin = request.headers.get("origin")
        if origin and origin in settings.BACKEND_CORS_ORIGINS:
            response = Response(
                status_code=200,
                headers={
                    "Access-Control-Allow-Origin": origin,
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With",
                    "Access-Control-Allow-Credentials": "true",
                    "Access-Control-Max-Age": "600"
                }
            )
            return response
    
    # For normal requests, continue with the normal flow
    response = await call_next(request)
    
    # Ensure CORS headers are present for allowed origins
    origin = request.headers.get("origin")
    if origin and origin in settings.BACKEND_CORS_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    
    return response

# Add CSP middleware at the application level
@app.middleware("http")
async def add_csp_header(request: Request, call_next):
    # First, get the response
    response = await call_next(request)
    
    # Only add CSP for HTML responses
    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type:
        return response
    
    # Create a new response with the same content
    from fastapi.responses import HTMLResponse
    from copy import deepcopy
    
    # Get the response content
    if hasattr(response, 'body'):
        content = response.body
    elif hasattr(response, 'body_iterator'):
        content = b''.join([chunk async for chunk in response.body_iterator])
    else:
        content = b''
    
    # Create a new response with the same content and status code
    new_response = HTMLResponse(
        content=content,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.media_type
    )
    
    # Create a very permissive CSP for development
    csp = (
        "default-src * 'unsafe-inline' 'unsafe-eval' data: blob:; "
        "script-src * 'unsafe-inline' 'unsafe-eval' data: blob:; "
        "style-src * 'unsafe-inline' 'unsafe-eval' data: blob:; "
        "img-src * data: blob: 'unsafe-inline' 'unsafe-eval'; "
        "font-src * data: blob: 'unsafe-inline' 'unsafe-eval'; "
        "connect-src * 'unsafe-inline' 'unsafe-eval' data: blob:; "
        "frame-src * 'unsafe-inline' 'unsafe-eval' data: blob:; "
        "media-src * 'unsafe-inline' 'unsafe-eval' data: blob:; "
        "object-src * 'unsafe-inline' 'unsafe-eval' data: blob:; "
        "form-action * 'unsafe-inline' 'unsafe-eval' data: blob:; "
        "base-uri * 'unsafe-inline' 'unsafe-eval' data: blob:; "
        "worker-src * 'unsafe-inline' 'unsafe-eval' data: blob:;"
    )
    
    # Set the CSP header
    new_response.headers["Content-Security-Policy"] = csp
    
    # Remove other CSP headers if they exist
    if "X-Content-Security-Policy" in new_response.headers:
        del new_response.headers["X-Content-Security-Policy"]
    if "X-WebKit-CSP" in new_response.headers:
        del new_response.headers["X-WebKit-CSP"]
    
    return new_response

# Then add other middleware
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

if not settings.DEBUG:
    # NOTA: HTTPSRedirectMiddleware deshabilitado porque Railway hace healthcheck via HTTP interno
    # app.add_middleware(HTTPSRedirectMiddleware)
    # Solo en producción, forzar HTTPS y otras políticas de seguridad
    security_headers = {
        "Strict-Transport-Security": f"max-age={settings.SECURE_HSTS_SECONDS}; includeSubDomains; preload",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Embedder-Policy": "require-corp",
        "Cross-Origin-Resource-Policy": "same-site"
    }

# Health check endpoint
@app.get("/health", include_in_schema=False)
async def health_check():
    return {"status": "ok", "service": "ZEUS-IA", "version": "1.0"}

# Favicon handler
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    favicon_path = os.path.join("static", 'favicon.ico')
    if not os.path.exists(favicon_path):
        with open(favicon_path, 'wb') as f:
            f.write(b'\x00\x00\x01\x00\x01\x00\x10\x10\x00\x00\x01\x00\x20\x00\x68\x04\x00\x00\x16\x00\x00\x00\x28\x00\x00\x00\x10\x00\x00\x00\x20\x00\x00\x00\x01\x00\x20\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')
    return FileResponse(favicon_path, media_type='image/x-icon')

# Configuración de archivos estáticos
static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static"))
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Configuración de Swagger UI usando FastAPI por defecto
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    from fastapi.openapi.docs import get_swagger_ui_html
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="ZEUS-IA - Swagger UI",
        swagger_js_url="/static/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui.css",
        swagger_favicon_url="/static/favicon.ico",
    )

# Configuración de OpenAPI
@app.get("/openapi.json", include_in_schema=False)
async def get_openapi_endpoint():
    return JSONResponse(app.openapi())

# Root redirect to docs
@app.get("/", include_in_schema=False)
async def root():
    """Redirect root to API documentation"""
    return RedirectResponse(
        url="/docs",
        status_code=status.HTTP_308_PERMANENT_REDIRECT
    )

# Swagger UI initialization script
@app.get("/docs/swagger-ui-init.js", include_in_schema=False)
async def swagger_ui_init_js():
    """Serve the Swagger UI initialization script"""
    return FileResponse(
        os.path.join(settings.STATIC_DIR, "swagger-ui-init.js"),
        media_type="application/javascript; charset=utf-8",
        headers={
            "Cache-Control": "public, max-age=86400",
            "Cross-Origin-Resource-Policy": "cross-origin"
        }
    )

from app.core.jwt_auth import get_current_user
from app.db.session import get_db

from fastapi import WebSocket, WebSocketDisconnect, status, HTTPException, Request
from typing import Dict, Optional
import json
import uuid
from contextlib import contextmanager
from sqlalchemy.orm import Session
from app.db.session import SessionLocal

# Almacenar conexiones activas
active_connections: Dict[str, dict] = {}

@contextmanager
def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Allowed WebSocket origins
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000"
]

# WebSocket endpoint

@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = None
):
    client_id = str(uuid.uuid4())
    logger.info(f"New WebSocket connection: {client_id}")
    
    try:
        # Check origin
        origin = websocket.headers.get("origin")
        if origin and origin not in ALLOWED_ORIGINS and not any(
            origin.startswith(prefix) 
            for prefix in ["https://", "http://localhost", "http://127.0.0.1"]
        ):
            logger.warning(f"WebSocket connection from unauthorized origin: {origin}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        # Get token from query parameters if not provided
        if not token:
            token = websocket.query_params.get("token")
            
        if not token:
            logger.error("No token provided")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
            
        # Accept the WebSocket connection only after token validation
        await websocket.accept()
            
        # Authenticate the user
        try:
            # Use direct JWT validation for WebSocket
            from jose import jwt, JWTError
            from app.core.config import settings
            from app.models.user import User
            from app.core.auth import get_user_by_id
            
            # Decode the JWT token directly
            try:
                payload = jwt.decode(
                    token,
                    settings.SECRET_KEY,
                    algorithms=[settings.ALGORITHM],
                    options={
                        "verify_aud": False,
                        "verify_iat": True,
                        "verify_exp": True,
                    }
                )
            except jwt.ExpiredSignatureError:
                logger.warning("Token expirado en WebSocket")
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
            except JWTError as e:
                logger.error(f"Error decodificando el token en WebSocket: {str(e)}")
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
            
            # Verify token type
            if payload.get("type") != "access":
                logger.warning(f"Tipo de token inválido en WebSocket: {payload.get('type')}")
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
            
            # Get user from database
            user_id = payload.get("sub")
            if not user_id:
                logger.warning("Token no contiene 'sub' claim en WebSocket")
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
            
            # Get the user from database
            with get_db_session() as db:
                try:
                    user_id_int = int(user_id)
                    user = get_user_by_id(db, user_id=user_id_int)
                except (ValueError, TypeError):
                    logger.error(f"ID de usuario inválido en WebSocket: {user_id}")
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                    return
                
                if not user:
                    logger.error(f"Usuario no encontrado en WebSocket: {user_id}")
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                    return
                    
                logger.info(f"User authenticated via WebSocket: {user.email}")
                
                # Store the connection
                active_connections[client_id] = {
                    "websocket": websocket,
                    "user_id": user.id,
                    "email": user.email
                }
                
                try:
                    # Main WebSocket loop
                    while True:
                        data = await websocket.receive_text()
                        logger.debug(f"Message from {user.email}: {data}")
                        
                        # Echo the message back
                        await websocket.send_text(f"Echo: {data}")
                        
                except WebSocketDisconnect:
                    logger.info(f"Client disconnected: {client_id}")
                    
        except Exception as e:
            logger.error(f"WebSocket authentication error: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            
    except Exception as e:
        logger.error(f"WebSocket connection error: {str(e)}")
    finally:
        # Clean up the connection when closed
        if client_id in active_connections:
            del active_connections[client_id]
            logger.info(f"WebSocket connection closed for client {client_id}")

if __name__ == "__main__":
    # Importar uvicorn aquí para evitar cargarlo durante las pruebas
    import uvicorn # type: ignore
    
    # Configurar nivel de logging para Uvicorn
    log_level = "debug" if settings.DEBUG else "info"
    
    # Ejecutar la aplicación
    try:
        logger.info(f"Iniciando servidor Uvicorn en {settings.HOST}:{settings.PORT}")
        uvicorn.run(
            "app.main:app",
            host=settings.HOST,
            port=settings.PORT,
            reload=settings.DEBUG,
            workers=1 if settings.DEBUG else 4,
            log_level=log_level,
            proxy_headers=True,
            forwarded_allow_ips="*" if settings.DEBUG else settings.TRUSTED_HOSTS,
        )
    except Exception as e:
        logger.critical(f"Error al iniciar el servidor: {e}", exc_info=True)
        raise