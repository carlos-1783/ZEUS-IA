from fastapi import APIRouter, WebSocket

from app.api.v1.endpoints import (
    actions,
    auth,
    commands,
    health,
    system,
    customers,
    crm,
    crm_import,
    office_mode,
    company,
    test,
    zeus_core,
    agents,
    metrics,
    analytics,
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
    workspace as workspace_deliverables,
    upload as upload_media,
    document_approval,
    tpv,
    admin,
    control_horario,
    checkin,
    cashflow,
    invoices,
    scan,
    thalos_v1,
    afrodita_v1,
    afrodita_rrhh_v1,
    afrodita_ops_v1,
    justicia_v1,
    products,
    zeus_closure_v1,
    zeus_core_v2,
    webhooks,
    payroll,
    rafael_fiscal,
    expenses,
    public as public_site,
    user_settings,
    user_account,
)
from app.api.v1.endpoints.websocket import websocket_endpoint

api_router = APIRouter()

# Health check endpoint is mounted directly at /api/v1/health
api_router.include_router(health.router, tags=["health"])

# Other endpoints with their respective prefixes
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(user_settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(user_account.router, prefix="/user", tags=["user-account"])
api_router.include_router(user_account.router, prefix="", tags=["api-keys"])
api_router.include_router(commands.router, prefix="/commands", tags=["commands"])
api_router.include_router(system.router, prefix="/system", tags=["system"])

# CRM endpoints
api_router.include_router(customers.router, prefix="/customers", tags=["customers"])
api_router.include_router(crm.router, prefix="/crm", tags=["crm-office"])
api_router.include_router(crm_import.router, prefix="/crm/import", tags=["crm-import"])
api_router.include_router(office_mode.router, prefix="/office", tags=["office-mode"])
api_router.include_router(company.router, prefix="/company", tags=["company"])

# Test endpoints
api_router.include_router(test.router, prefix="/test", tags=["test"])

# Núcleo ZEUS endpoints
api_router.include_router(zeus_core.router, prefix="/zeus", tags=["zeus-core"])

# Agents & Metrics endpoints (para dashboard)
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])

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

# Workspace (entregables estructurados persistidos)
api_router.include_router(workspace_deliverables.router, prefix="/workspace", tags=["workspace"])

# Subida unificada (imagen / vídeo / PDF)
api_router.include_router(upload_media.router, prefix="/upload", tags=["upload"])

# TPV Universal Enterprise
api_router.include_router(tpv.router, prefix="/tpv", tags=["tpv"])

# Web pública por cliente (/p/{slug}/info, /p/{slug}/reservations)
api_router.include_router(public_site.router, prefix="/p", tags=["public-site"])

# Control Horario Universal Enterprise
api_router.include_router(control_horario.router, prefix="/control-horario", tags=["control-horario"])

# Time & cost engine v1 (fichajes + coste laboral)
api_router.include_router(checkin.router, prefix="/checkin", tags=["checkin"])

# Cashflow ledger (movimientos reales)
api_router.include_router(cashflow.router, prefix="/cashflow", tags=["cashflow"])

# ERP Invoices & payments
api_router.include_router(invoices.router, prefix="/invoices", tags=["invoices"])
api_router.include_router(products.router, prefix="/products", tags=["products"])

# Physical scan flows (QR / NFC / DNI)
api_router.include_router(scan.router, prefix="/scan", tags=["scan"])
api_router.include_router(thalos_v1.router, tags=["thalos-v1"])
api_router.include_router(afrodita_v1.router, tags=["afrodita-v1"])
api_router.include_router(afrodita_rrhh_v1.router, tags=["afrodita-rrhh-v1"])
api_router.include_router(afrodita_ops_v1.router, tags=["afrodita-ops-v1"])
api_router.include_router(justicia_v1.router, tags=["justicia-v1"])
api_router.include_router(zeus_closure_v1.router, tags=["zeus-closure"])

# ZEUS final closure v2
api_router.include_router(zeus_core_v2.router, prefix="/zeus-core", tags=["zeus-core-v2"])

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
api_router.include_router(workspaces.tools_router, tags=["tools"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(payroll.router, tags=["payroll"])
api_router.include_router(rafael_fiscal.router, prefix="/rafael-fiscal", tags=["rafael-fiscal"])
api_router.include_router(expenses.router, prefix="/expenses", tags=["expenses"])
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
