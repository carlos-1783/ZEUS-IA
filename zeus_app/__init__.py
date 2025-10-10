from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import os

# Router para la API v1
api_router = APIRouter(prefix="/api/v1")

# Endpoint de prueba raíz
@api_router.get("/")
async def read_root():
    return {"message": "¡Bienvenido a la API de ZEUS-IA!"}

# Endpoint de salud
@api_router.get("/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}

# Configuración de la aplicación
@api_router.get("/config")
async def get_config():
    return {
        "app_name": "ZEUS-IA",
        "version": "1.0.0",
        "environment": os.getenv("ENV", "development"),
        "features": ["authentication", "dashboard", "analytics"]
    }

# Endpoint de autenticación
@api_router.post("/auth/login")
async def login():
    return {"token": "dummy_token", "user": {"id": 1, "username": "admin"}}

# Endpoint del dashboard
@api_router.get("/dashboard")
async def get_dashboard():
    return {
        "stats": {
            "total_sales": 15200,
            "conversion_rate": 0.42,
            "active_users": 128,
            "revenue_growth": 0.17
        },
        "recent_activity": [
            {"id": 1, "action": "nueva_venta", "amount": 124.50, "timestamp": "2025-06-12T10:30:00"},
            {"id": 2, "action": "usuario_registrado", "username": "nuevo_usuario", "timestamp": "2025-06-12T10:15:00"}
        ]
    }
