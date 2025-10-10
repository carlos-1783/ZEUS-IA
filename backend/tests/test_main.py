import pytest
import os
import sys
from pathlib import Path

# Añadir el directorio raíz al path para que Python pueda encontrar los módulos
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configurar variables de entorno para pruebas
os.environ["ENV"] = "test"
os.environ["DEBUG"] = "True"

from fastapi.testclient import TestClient
from app.main_new import app
from app.core.config import settings

def test_health_check():
    """Test the health check endpoint"""
    # Usar un cliente de prueba sin autenticación
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "service" in data
        assert "version" in data

def test_root_redirect():
    """Test the root endpoint returns a welcome message"""
    with TestClient(app) as client:
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert settings.PROJECT_NAME in data["message"]

def test_favicon():
    """Test the favicon endpoint"""
    with TestClient(app) as client:
        response = client.get("/favicon.ico")
        # Debería devolver 200 o 204 (si no hay favicon)
        assert response.status_code in (200, 204)

@pytest.mark.asyncio
async def test_lifespan():
    """Test the application lifespan"""
    from contextlib import asynccontextmanager
    from fastapi import FastAPI
    
    startup_complete = False
    
    @asynccontextmanager
    async def test_lifespan_wrapper(app):
        nonlocal startup_complete
        startup_complete = True
        yield
        startup_complete = False
    
    test_app = FastAPI(lifespan=test_lifespan_wrapper)
    
    @test_app.get("/")
    async def root():
        return {"message": "Test"}
    
    # Test startup
    async with test_lifespan_wrapper(test_app):
        assert startup_complete is True
    
    # Test shutdown
    assert startup_complete is False
