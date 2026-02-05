from fastapi import APIRouter, WebSocket

from app.api.v1.endpoints import (
    actions,
    auth,
    commands,
    health,
    system,
    customers,
    test,
    zeus_core,
    agents,
    metrics,
    chat,
    integrations,
    google,
    marketing,
    onboarding,
    activities,
    automation_outputs,
    system_status,
    perseo_images,
    teamflow,
    workspaces,
    document_approval,
    tpv,
    admin,
    control_horario,
    webhooks,
)
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

# Chat endpoint (para interactuar con agentes)
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])

# Integrations endpoint (WhatsApp, Email, Hacienda, Stripe)
api_router.include_router(integrations.router, prefix="/integrations", tags=["integrations"])

# Google Workspace integrations (Calendar, Gmail, Drive, Sheets)
api_router.include_router(google.router, prefix="/google", tags=["google-workspace"])

# Marketing Automation (Google Ads, Meta Ads, Analytics)
api_router.include_router(marketing.router, prefix="/marketing", tags=["marketing-automation"])

# Onboarding (creación de cuentas después del pago)
api_router.include_router(onboarding.router, prefix="/onboarding", tags=["onboarding"])

# Document Approval (aprobación de documentos RAFAEL/JUSTICIA)
api_router.include_router(document_approval.router, prefix="/documents", tags=["document-approval"])

# TPV Universal Enterprise
api_router.include_router(tpv.router, prefix="/tpv", tags=["tpv"])

# Control Horario Universal Enterprise
api_router.include_router(control_horario.router, prefix="/control-horario", tags=["control-horario"])

# Admin Panel (solo superusuarios)
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])

# Activities (registro de actividades de agentes)
api_router.include_router(activities.router, prefix="/activities", tags=["activities"])
api_router.include_router(automation_outputs.router, prefix="/automation", tags=["automation"])
api_router.include_router(system_status.router, prefix="/system", tags=["system-status"])
api_router.include_router(perseo_images.router, tags=["perseo-images"])
api_router.include_router(teamflow.router, tags=["teamflow"])
api_router.include_router(actions.router, tags=["actions"])
api_router.include_router(workspaces.router, tags=["workspaces"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
# Log webhooks router registration
import logging
logger = logging.getLogger(__name__)
logger.info(f"[API] Webhooks router registrado: {webhooks.router.prefix if hasattr(webhooks.router, 'prefix') else 'sin prefix'}, rutas: {[r.path for r in webhooks.router.routes]}")

# WebSocket endpoint - CORREGIDO para Railway
@api_router.websocket("/ws/{client_id}")
async def websocket_handler(websocket: WebSocket, client_id: str):
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        await websocket_endpoint(websocket, client_id, db)
    finally:
        db.close()
