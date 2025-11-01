from fastapi import APIRouter, WebSocket
from fastapi import APIRouter

from app.api.v1.endpoints import auth, commands, health, system, customers, test, zeus_core, agents, metrics
from app.api.v1.endpoints.websocket import websocket_endpoint

api_router = APIRouter()

# Health check endpoint is mounted directly at /api/v1/health
api_router.include_router(health.router, tags=["health"])

# Other endpoints with their respective prefixes
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(commands.router, prefix="/commands", tags=["commands"])
api_router.include_router(system.router, prefix="/system", tags=["system"])

# CRM endpoints
api_router.include_router(customers.router, prefix="/customers", tags=["customers"])

# Test endpoints
api_router.include_router(test.router, prefix="/test", tags=["test"])

# Núcleo ZEUS endpoints
api_router.include_router(zeus_core.router, prefix="/zeus", tags=["zeus-core"])

# Agents & Metrics endpoints (para dashboard)
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(metrics.router, prefix="/metrics", tags=["metrics"])

# WebSocket endpoint - CORREGIDO para Railway
@api_router.websocket("/ws/{client_id}")
async def websocket_handler(websocket: WebSocket, client_id: str):
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        await websocket_endpoint(websocket, client_id, db)
    finally:
        db.close()
