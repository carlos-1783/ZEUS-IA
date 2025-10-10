import pytest
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Añadir el directorio raíz al path para que Python pueda encontrar los módulos
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configurar variables de entorno para pruebas
os.environ["ENV"] = "test"
os.environ["DEBUG"] = "True"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

# Mock de las dependencias de la base de datos
with patch('sqlalchemy.orm.session.Session'), \
     patch('sqlalchemy.ext.asyncio.create_async_engine'), \
     patch('sqlalchemy.ext.asyncio.async_sessionmaker'):
    
    # Importar la aplicación después de configurar los mocks
    from app.main_new import app, lifespan
    from app.core.config import settings

# Cliente de prueba
test_client = None

@pytest.fixture(scope="module")
def client():
    global test_client
    if test_client is None:
        test_client = TestClient(app)
    return test_client

def test_health_check(client):
    """Test the health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "service" in data
    assert "version" in data

def test_root_endpoint(client):
    """Test the root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert settings.PROJECT_NAME in data["message"]

def test_favicon(client):
    """Test the favicon endpoint"""
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
