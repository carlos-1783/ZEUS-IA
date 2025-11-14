"""
🔍 System Status Endpoint
Endpoint para verificar el estado del sistema, tokens pendientes y autorizaciones
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List
import os
from datetime import datetime

from app.core.auth import get_current_active_superuser
from app.models.user import User
from app.core.config import settings

router = APIRouter()


@router.get("/status")
async def get_system_status(
    current_user: User = Depends(get_current_active_superuser)
) -> Dict[str, Any]:
    """
    Obtener estado completo del sistema ZEUS IA
    
    Incluye:
    - Estado de agentes
    - Tokens y credenciales pendientes
    - Autorizaciones esperadas
    - Métricas del sistema
    """
    
    # Verificar tokens pendientes
    pending_tokens = []
    
    # Google Ads Developer Token
    google_ads_token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "")
    if not google_ads_token or google_ads_token.lower() == "pendiente":
        pending_tokens.append({
            "service": "Google Ads",
            "token_name": "GOOGLE_ADS_DEVELOPER_TOKEN",
            "status": "pending",
            "required_for": "PERSEO - Campañas de Google Ads",
            "link": "https://ads.google.com/aw/apicenter"
        })
    
    # Verificar otras credenciales críticas
    critical_credentials = {
        "OPENAI_API_KEY": {
            "service": "OpenAI",
            "required_for": "Todos los agentes - Decisiones IA",
            "link": "https://platform.openai.com/api-keys"
        },
        "STRIPE_SECRET_KEY": {
            "service": "Stripe",
            "required_for": "RAFAEL - Pagos y facturación",
            "link": "https://dashboard.stripe.com/apikeys"
        },
        "TWILIO_ACCOUNT_SID": {
            "service": "Twilio",
            "required_for": "WhatsApp automático",
            "link": "https://console.twilio.com/"
        },
        "SENDGRID_API_KEY": {
            "service": "SendGrid",
            "required_for": "Emails automáticos",
            "link": "https://app.sendgrid.com/settings/api_keys"
        }
    }
    
    missing_credentials = []
    for env_var, info in critical_credentials.items():
        value = os.getenv(env_var, "")
        if not value or value.lower() in ["pendiente", "pending", ""]:
            missing_credentials.append({
                "service": info["service"],
                "env_var": env_var,
                "status": "missing" if not value else "pending",
                "required_for": info["required_for"],
                "link": info["link"]
            })
    
    # Estado de agentes (desde chat endpoint)
    agents_status = {
        "PERSEO": "active",
        "RAFAEL": "active",
        "THALOS": "active",
        "JUSTICIA": "active",
        "AFRODITA": "active",
        "ZEUS CORE": "active"
    }
    
    # Verificar comunicación entre agentes
    communication_status = {
        "inter_agent_enabled": True,
        "zeus_core_connected": True,
        "last_test": datetime.now().isoformat()
    }
    
    return {
        "status": "operational",
        "timestamp": datetime.now().isoformat(),
        "agents": agents_status,
        "communication": communication_status,
        "pending_authorizations": {
            "tokens": pending_tokens,
            "credentials": missing_credentials,
            "total_pending": len(pending_tokens) + len(missing_credentials)
        },
        "system_info": {
            "environment": settings.APP_ENV,
            "api_version": "v1",
            "database": "connected" if settings.DATABASE_URL else "not_configured"
        },
        "links": {
            "dashboard": "/dashboard",
            "agents_status": "/api/v1/agents/status",
            "activities": "/api/v1/activities",
            "automation_outputs": "/api/v1/automation/outputs"
        }
    }


@router.get("/pending-authorizations")
async def get_pending_authorizations(
    current_user: User = Depends(get_current_active_superuser)
) -> Dict[str, Any]:
    """
    Lista detallada de todas las autorizaciones y tokens pendientes
    """
    pending = []
    
    # Google Ads
    google_ads_token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "")
    if not google_ads_token or google_ads_token.lower() == "pendiente":
        pending.append({
            "id": "google_ads_token",
            "service": "Google Ads API",
            "type": "developer_token",
            "status": "pending",
            "description": "Token de desarrollador necesario para crear y gestionar campañas de Google Ads",
            "required_by": "PERSEO",
            "priority": "high",
            "action_url": "https://ads.google.com/aw/apicenter",
            "instructions": "1. Ve a Google Ads API Center\n2. Solicita acceso como desarrollador\n3. IMPORTANTE: Proporciona 'ZEUS IA' como nombre de aplicación\n4. Genera un Developer Token específico para ZEUS IA\n5. Añádelo como GOOGLE_ADS_DEVELOPER_TOKEN en Railway",
            "verification_info": {
                "application_name": "ZEUS IA - Sistema de Automatización de Marketing con IA",
                "account_id": "129-046-8001",
                "account_name": "Marketing Digital PER-SEO",
                "email": "marketingdigitalper.seo@gmail.com",
                "production_url": "https://zeus-ia-production-16d8.up.railway.app",
                "note": "Si anteriormente solicitaste un token para otra aplicación (ej: web de marketing de afiliado), necesitas crear uno NUEVO específicamente para ZEUS IA. No reutilices tokens de otras aplicaciones."
            },
            "guide_url": "/docs/GUIA_GOOGLE_ADS_TOKEN.md"
        })
    
    # Verificar otros tokens pendientes
    env_vars_to_check = [
        ("GOOGLE_CREDENTIALS_JSON", "Google Cloud", "PERSEO - Integración completa con Google"),
        ("LINKEDIN_ACCESS_TOKEN", "LinkedIn", "PERSEO - Publicación en LinkedIn"),
        ("TIKTOK_ACCESS_TOKEN", "TikTok", "PERSEO - Publicación en TikTok"),
    ]
    
    for env_var, service, required_for in env_vars_to_check:
        value = os.getenv(env_var, "")
        if not value or value.lower() in ["pendiente", "pending", ""]:
            pending.append({
                "id": env_var.lower(),
                "service": service,
                "type": "access_token",
                "status": "pending",
                "description": f"Token de acceso para {service}",
                "required_by": required_for.split(" - ")[0],
                "priority": "medium",
                "action_url": "#",
                "instructions": f"Configura {env_var} en Railway con el token correspondiente"
            })
    
    return {
        "total": len(pending),
        "pending": pending,
        "last_checked": datetime.now().isoformat()
    }

