import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.middlewares import setup_middlewares
from app.core.routes import setup_routes
from app.core.docs import setup_docs, set_custom_openapi

# Application lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestor del ciclo de vida de la aplicación.
    
    Args:
        app: Instancia de FastAPI
    """
    # Inicio de la aplicación
    print(f"Iniciando {settings.PROJECT_NAME} v{settings.VERSION}")
    print(f"Entorno: {'Desarrollo' if settings.DEBUG else 'Producción'}")
    print(f"Servidor ejecutándose en http://{settings.HOST}:{settings.PORT}")
    
    # Crear directorios necesarios
    os.makedirs(settings.STATIC_DIR, exist_ok=True)
    
    yield
    
    # Limpieza al cerrar
    print("Deteniendo la aplicación...")

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
    **{k: v for k, v in api_metadata.items() if k != 'debug'},
    lifespan=lifespan
)

# Configurar middlewares
setup_middlewares(app)

# Configurar rutas
setup_routes(app)

# Configurar documentación
setup_docs(app)

# Aplicar esquema OpenAPI personalizado
app.openapi = lambda: set_custom_openapi(app)

# Configuración de manejadores de excepciones
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Maneja las excepciones HTTP."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    """Maneja los errores de validación de peticiones."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "body": exc.body},
    )

# Health check endpoint
@app.get("/health", include_in_schema=False)
async def health_check():
    """Endpoint de verificación de salud."""
    return {
        "status": "ok", 
        "service": settings.PROJECT_NAME, 
        "version": settings.VERSION
    }

# Favicon handler
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Sirve el favicon de la aplicación."""
    favicon_path = os.path.join(settings.STATIC_DIR, 'favicon.ico')
    if not os.path.exists(favicon_path):
        # Crear un favicon vacío si no existe
        with open(favicon_path, 'wb') as f:
            f.write(b'\x00\x00\x01\x00\x01\x00\x10\x10\x00\x00\x01\x00\x20\x00\x68\x04\x00\x00\x16\x00\x00\x00\x28\x00\x00\x00\x10\x00\x00\x00\x20\x00\x00\x00\x01\x00\x20\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')
    return FileResponse(favicon_path, media_type='image/x-icon')

# Root redirect to docs
@app.get("/", include_in_schema=False)
async def root():
    """Redirige la raíz a la documentación de la API."""
    return {"message": f"Bienvenido a {settings.PROJECT_NAME} API. Visite /docs para la documentación."}

# Redirect /docs to /api/docs for easier access
@app.get("/docs", include_in_schema=False)
async def redirect_docs():
    """Redirige /docs a /api/docs."""
    return JSONResponse(
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        headers={"Location": "/api/docs"}
    )

if __name__ == "__main__":
    # Importar uvicorn aquí para evitar cargarlo durante las pruebas
    import uvicorn
    
    # Ejecutar la aplicación
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else 4,
        log_level="info" if settings.DEBUG else "warning",
        proxy_headers=True,
        forwarded_allow_ips="*" if settings.DEBUG else settings.TRUSTED_HOSTS,
    )
