import logging
from fastapi import FastAPI, APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import uvicorn
import sys

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Crear una aplicación FastAPI con información de depuración
app = FastAPI(
    title="Minimal FastAPI Test",
    description="Aplicación de prueba mínima para diagnosticar problemas de enrutamiento",
    version="0.1.0",
    debug=True
)

# Middleware para loggear todas las peticiones
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Request: {request.method} {request.url}")
    logger.info(f"Headers: {request.headers}")
    response = await call_next(request)
    return response

# Crear un router para la API
api_router = APIRouter()

# Modelo de respuesta
class TestResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

# Endpoint de prueba en el router
@api_router.get(
    "/test-minimal", 
    response_model=TestResponse,
    summary="Endpoint de prueba",
    description="Un endpoint mínimo para probar el enrutamiento de FastAPI"
)
async def test_minimal_endpoint():
    logger.info("Test endpoint was called")
    return {
        "success": True,
        "message": "¡Endpoint de prueba funcionando correctamente!",
        "data": {"status": "ok", "test": "valor"}
    }

# Endpoint raíz
@app.get("/", include_in_schema=False)
async def root():
    return {
        "message": "Aplicación de prueba de FastAPI",
        "endpoints": [
            {"path": "/api/v1/test-minimal", "method": "GET", "description": "Endpoint de prueba mínimo"},
            {"path": "/docs", "method": "GET", "description": "Documentación interactiva de la API"},
            {"path": "/openapi.json", "method": "GET", "description": "Esquema OpenAPI"}
        ]
    }

# Incluir el router con prefijo
app.include_router(api_router, prefix="/api/v1")

# Manejador de errores global
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Error no manejado: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": f"Error interno del servidor: {str(exc)}"}
    )

if __name__ == "__main__":
    # Imprimir rutas registradas
    logger.info("Rutas registradas:")
    for route in app.routes:
        logger.info(f"{route.path} - {route.methods}")
    
    # Iniciar el servidor en un puerto diferente
    logger.info("Iniciando servidor en http://0.0.0.0:8005")
    uvicorn.run(
        "minimal_fastapi:app",
        host="0.0.0.0",
        port=8005,
        reload=True,
        log_level="debug"
    )
