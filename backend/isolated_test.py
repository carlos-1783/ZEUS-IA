"""
Prueba aislada que no depende de la estructura de la aplicación principal.
Este archivo puede ejecutarse directamente para verificar la funcionalidad básica.
"""
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Crear una aplicación FastAPI mínima para pruebas
app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello, World!"}

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "TestApp", "version": "1.0.0"}

def test_root():
    """Prueba el endpoint raíz"""
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"message": "Hello, World!"}

def test_health():
    """Prueba el endpoint de salud"""
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "TestApp"
        assert data["version"] == "1.0.0"

if __name__ == "__main__":
    # Ejecutar las pruebas directamente
    test_root()
    test_health()
    print("¡Todas las pruebas pasaron exitosamente!")
