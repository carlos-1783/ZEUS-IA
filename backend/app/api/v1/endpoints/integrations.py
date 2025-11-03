"""
🔌 Integrations Endpoints
Endpoints para WhatsApp, Email, Hacienda, Stripe
"""
from fastapi import APIRouter, HTTPException, Request, Header
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from datetime import datetime

# Importar servicios
from services.whatsapp_service import whatsapp_service
from services.email_service import email_service
from services.hacienda_service import hacienda_service
from services.stripe_service import stripe_service

router = APIRouter()

# ============================================================================
# MODELS
# ============================================================================

class WhatsAppMessage(BaseModel):
    to_number: str
    message: str
    media_url: Optional[str] = None

class EmailMessage(BaseModel):
    to_email: EmailStr
    subject: str
    content: str
    content_type: str = "text/html"

class FacturaEmitida(BaseModel):
    numero: str
    fecha: str  # YYYY-MM-DD
    cliente_nif: str
    cliente_nombre: str
    base_imponible: float
    tipo_iva: float
    cuota_iva: float
    total: float

class Modelo303(BaseModel):
    trimestre: int  # 1, 2, 3, 4
    ejercicio: int  # YYYY
    base_imponible_general: float
    cuota_iva_soportado: float
    cuota_iva_repercutido: float

class PaymentIntent(BaseModel):
    amount: float  # euros
    customer_email: EmailStr
    description: str
    metadata: Optional[Dict[str, str]] = None

# ============================================================================
# WHATSAPP ENDPOINTS
# ============================================================================

@router.post("/whatsapp/send")
async def send_whatsapp(message: WhatsAppMessage):
    """Enviar mensaje de WhatsApp"""
    result = await whatsapp_service.send_message(
        to_number=message.to_number,
        message=message.message,
        media_url=message.media_url
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    return result

@router.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    """
    Webhook para recibir mensajes de WhatsApp (Twilio)
    Configurar en Twilio: https://console.twilio.com/us1/develop/sms/settings/whatsapp-sandbox
    """
    form_data = await request.form()
    
    from_number = form_data.get("From", "")
    message_body = form_data.get("Body", "")
    
    if not from_number or not message_body:
        raise HTTPException(status_code=400, detail="Missing required fields")
    
    # Procesar mensaje con agente
    result = await whatsapp_service.process_incoming_message(
        from_number=from_number,
        message_body=message_body,
        agent_name="ZEUS CORE"  # Por defecto, ZEUS responde
    )
    
    return result

@router.get("/whatsapp/status")
async def whatsapp_status():
    """Obtener estado del servicio de WhatsApp"""
    return whatsapp_service.get_status()

# ============================================================================
# EMAIL ENDPOINTS
# ============================================================================

@router.post("/email/send")
async def send_email(message: EmailMessage):
    """Enviar email"""
    result = await email_service.send_email(
        to_email=message.to_email,
        subject=message.subject,
        content=message.content,
        content_type=message.content_type
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    return result

@router.post("/email/webhook")
async def email_webhook(request: Request):
    """
    Webhook para recibir emails (SendGrid Inbound Parse)
    Configurar en SendGrid: https://app.sendgrid.com/settings/parse
    """
    form_data = await request.form()
    
    from_email = form_data.get("from", "")
    subject = form_data.get("subject", "")
    body = form_data.get("text", form_data.get("html", ""))
    
    if not from_email or not body:
        raise HTTPException(status_code=400, detail="Missing required fields")
    
    # Procesar email con agente
    result = await email_service.process_incoming_email(
        from_email=from_email,
        subject=subject,
        body=body,
        agent_name="ZEUS CORE"
    )
    
    return result

@router.get("/email/status")
async def email_status():
    """Obtener estado del servicio de Email"""
    return email_service.get_status()

# ============================================================================
# HACIENDA ENDPOINTS
# ============================================================================

@router.post("/hacienda/factura")
async def enviar_factura(factura: FacturaEmitida):
    """Enviar factura al SII de Hacienda"""
    result = await hacienda_service.enviar_factura_emitida(factura.dict())
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    return result

@router.post("/hacienda/modelo-303")
async def presentar_modelo_303(modelo: Modelo303):
    """Presentar Modelo 303 (IVA trimestral)"""
    result = await hacienda_service.presentar_modelo_303(
        trimestre=modelo.trimestre,
        ejercicio=modelo.ejercicio,
        datos=modelo.dict()
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    return result

@router.get("/hacienda/status")
async def hacienda_status():
    """Obtener estado del servicio de Hacienda"""
    return hacienda_service.get_status()

# ============================================================================
# STRIPE ENDPOINTS
# ============================================================================

@router.post("/stripe/payment-intent")
async def create_payment(payment: PaymentIntent):
    """Crear Payment Intent para procesar pago"""
    result = await stripe_service.create_payment_intent(
        amount=payment.amount,
        customer_email=payment.customer_email,
        description=payment.description,
        metadata=payment.metadata
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    return result

@router.post("/stripe/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None)
):
    """
    Webhook para eventos de Stripe
    Configurar en Stripe: https://dashboard.stripe.com/webhooks
    """
    payload = await request.body()
    
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe signature")
    
    result = await stripe_service.process_webhook(
        payload=payload.decode('utf-8'),
        sig_header=stripe_signature
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result

@router.get("/stripe/status")
async def stripe_status():
    """Obtener estado del servicio de Stripe"""
    return stripe_service.get_status()

# ============================================================================
# STATUS GLOBAL
# ============================================================================

@router.get("/status")
async def integrations_status():
    """Obtener estado de todas las integraciones"""
    return {
        "whatsapp": whatsapp_service.get_status(),
        "email": email_service.get_status(),
        "hacienda": hacienda_service.get_status(),
        "stripe": stripe_service.get_status(),
        "timestamp": datetime.utcnow().isoformat()
    }

