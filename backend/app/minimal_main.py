from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel

# Configuración básica
class Settings:
    PROJECT_NAME = "ZEUS-IA API"
    VERSION = "1.0.0"
    DEBUG = True
    HOST = "0.0.0.0"
    PORT = 8001
    STATIC_DIR = "static"
    API_V1_STR = "/api/v1"
    
settings = Settings()

# Crear aplicación FastAPI
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    debug=settings.DEBUG,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
    openapi_url="/api/openapi.json" if settings.DEBUG else None,
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Crear directorio estático si no existe
os.makedirs(settings.STATIC_DIR, exist_ok=True)

# Montar archivos estáticos
app.mount("/static", StaticFiles(directory=settings.STATIC_DIR), name="static")

# Modelo de ejemplo
class TestResponse(BaseModel):
    status: str
    message: str

# Endpoint de prueba simple
@app.get("/api/v1/test", response_model=TestResponse)
async def test_endpoint() -> TestResponse:
    """
    Endpoint de prueba simple sin dependencias.
    """
    return {"status": "success", "message": "¡Endpoint de prueba funcionando!"}

# Endpoint principal
@app.get("/")
async def root():
    return {"message": f"Bienvenido a {settings.PROJECT_NAME} v{settings.VERSION}"}

# Endpoint de salud
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.minimal_main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info" if settings.DEBUG else "warning"
    )
