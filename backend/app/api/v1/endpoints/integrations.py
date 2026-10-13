"""
🔌 Integrations Endpoints
Endpoints para WhatsApp, Email, Hacienda, Stripe
"""
import logging

from fastapi import APIRouter, HTTPException, Request, Header, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from datetime import datetime

# Importar servicios
from services.whatsapp_service import whatsapp_service
from services.email_service import email_service
from services.hacienda_service import HaciendaError, hacienda_service
from services.stripe_service import stripe_service
from services.webhook_signature_v1 import verify_email_inbound_secret, verify_twilio_request
from services.thalos_request_guard_v1 import thalos_request_guard
from app.core.auth import require_scopes
from app.core.auth import get_current_active_superuser
from app.models.user import User
from app.models.company import Company
from app.db.session import get_db
from sqlalchemy.orm import Session
import services.crm_office_service as crm_svc
import services.outbound_consent_v1 as consent_svc
# Tabla de precios oficial (misma fuente de verdad que usa
# /onboarding/create-account al verificar el pago) -- se reutiliza aquí
# para calcular el importe del checkout público en el servidor, nunca
# confiando en un importe que mande el cliente.
from app.api.v1.endpoints.onboarding import PRICING_PLANS

router = APIRouter()
logger = logging.getLogger(__name__)

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


class PublicCheckoutPaymentIntent(BaseModel):
    """Payload del checkout público (cliente nuevo, sin sesión).

    Deliberadamente NO tiene campo `amount`: el importe nunca debe salir
    del cliente para este flujo, se calcula en el servidor a partir de
    `plan` usando PRICING_PLANS. Si el cliente manda un campo `amount` de
    todas formas (compatibilidad con payloads antiguos), se ignora.
    """
    plan: str
    customer_email: EmailStr
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

# ============================================================================
# WHATSAPP ENDPOINTS
# ============================================================================

async def _direct_send(db: Session, user: User, channel: str, recipient: str, send_coro_factory):
    """Envio directo con destinatario legitimo + limite por empresa + registro.

    - Superusuario: envio de plataforma (company_id NULL), a cualquier destinatario.
    - Resto: solo clientes de SU empresa con consentimiento comercial y sin baja, o empleados
      activos de su empresa (403 y registro del bloqueo en otro caso). A los clientes se les
      anade siempre el enlace de baja; sin PUBLIC_BASE_URL no se envia (503).
    - Limite de envios directos por empresa y canal por hora (429), contado en outbound_messages.
    """
    target = consent_svc.resolve_direct_recipient(db, user, channel, recipient)
    company_id = target["company_id"]
    purpose = "platform" if target["kind"] == "platform" else "direct"
    if company_id is not None:
        consent_svc.enforce_company_direct_limit(db, company_id, channel)
    unsubscribe = None
    if target["kind"] == "customer":
        unsubscribe = consent_svc.unsubscribe_url(company_id, target["ref_id"])
        if unsubscribe is None:
            consent_svc.record_outbound(
                db, company_id=company_id, user_id=user.id, channel=channel, purpose=purpose,
                recipient=recipient, status_value="blocked", detail="sin PUBLIC_BASE_URL para el enlace de baja",
                recipient_kind=target["kind"], recipient_ref_id=target["ref_id"],
            )
            raise HTTPException(
                status_code=503,
                detail="No se puede enviar a clientes sin enlace de baja: PUBLIC_BASE_URL no esta configurado.",
            )
    try:
        result = await send_coro_factory(unsubscribe)
    except Exception as exc:
        logger.exception("envio directo %s company_id=%s fallo", channel, company_id)
        result = {"success": False, "error": type(exc).__name__}
    ok = bool(result.get("success"))
    consent_svc.record_outbound(
        db, company_id=company_id, user_id=user.id, channel=channel, purpose=purpose,
        recipient=recipient, status_value="sent" if ok else "failed",
        detail=None if ok else str(result.get("error") or "error del proveedor"),
        recipient_kind=target["kind"], recipient_ref_id=target["ref_id"],
    )
    if not ok:
        raise HTTPException(status_code=502, detail=result.get("error") or "El proveedor no acepto el envio.")
    return result


@router.post("/whatsapp/send", dependencies=[Depends(thalos_request_guard)])
async def send_whatsapp(
    message: WhatsAppMessage,
    current_user: User = Depends(require_scopes(["marketing:write"])),
    db: Session = Depends(get_db),
):
    """Enviar WhatsApp a un cliente (con consentimiento) o empleado de tu empresa."""
    if not whatsapp_service.is_configured():
        raise HTTPException(status_code=503, detail="WhatsApp no configurado (Twilio o TWILIO_WHATSAPP_ENABLED).")
    to_number = consent_svc.normalize_phone(message.to_number)

    async def _send(unsubscribe):
        body = message.message
        if unsubscribe:
            body = f"{body}\n\nPara no recibir mas mensajes: {unsubscribe}"
        return await whatsapp_service.send_message(
            to_number=to_number, message=body, media_url=message.media_url
        )

    return await _direct_send(db, current_user, consent_svc.CHANNEL_WHATSAPP, message.to_number, _send)

@router.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    """
    Webhook para recibir mensajes de WhatsApp (Twilio)
    Configurar en Twilio: https://console.twilio.com/us1/develop/sms/settings/whatsapp-sandbox
    """
    form_data = await request.form()
    verify_twilio_request(request, form_data)  # 403 firma invalida / 503 sin token
    
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
async def whatsapp_status(
    _: User = Depends(require_scopes(["marketing:read"])),
):
    """Obtener estado del servicio de WhatsApp"""
    return whatsapp_service.get_status()

# ============================================================================
# EMAIL ENDPOINTS
# ============================================================================

@router.post("/email/send", dependencies=[Depends(thalos_request_guard)])
async def send_email(
    message: EmailMessage,
    current_user: User = Depends(require_scopes(["marketing:write"])),
    db: Session = Depends(get_db),
):
    """Enviar email a un cliente (con consentimiento) o empleado de tu empresa."""
    if not (email_service.is_configured() or email_service.is_resend_configured() or email_service.is_smtp_configured()):
        raise HTTPException(status_code=503, detail="Email no configurado (SMTP, SENDGRID_API_KEY o RESEND_API_KEY).")

    async def _send(unsubscribe):
        content = message.content
        if unsubscribe:
            company = db.get(Company, crm_svc.primary_company_id(db, current_user))
            name = (getattr(company, "company_name", None) or "este negocio").strip()
            if message.content_type == "text/html":
                content = content + consent_svc.unsubscribe_footer_html(unsubscribe, name)
            else:
                content = f"{content}\n\n--\nPara darte de baja de las comunicaciones de {name}: {unsubscribe}"
        return await email_service.send_email(
            to_email=message.to_email,
            subject=message.subject,
            content=content,
            content_type=message.content_type,
        )

    return await _direct_send(db, current_user, consent_svc.CHANNEL_EMAIL, str(message.to_email), _send)

@router.post("/email/webhook")
async def email_webhook(request: Request):
    """
    Webhook para recibir emails (SendGrid Inbound Parse)
    Configurar en SendGrid: https://app.sendgrid.com/settings/parse
    La URL de destino debe incluir ?secret=<EMAIL_INBOUND_WEBHOOK_SECRET> (SendGrid Inbound
    Parse no firma; no permite cabeceras personalizadas). Tambien se acepta la cabecera X-Inbound-Secret.
    """
    verify_email_inbound_secret(request)  # 403 secreto invalido / 503 sin secreto
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
async def email_status(
    _: User = Depends(require_scopes(["marketing:read"])),
):
    """Obtener estado del servicio de Email"""
    return email_service.get_status()

# ============================================================================
# HACIENDA ENDPOINTS
# ============================================================================

@router.post("/hacienda/factura", dependencies=[Depends(thalos_request_guard)])
async def enviar_factura(
    factura: FacturaEmitida,
    _: User = Depends(require_scopes(["tax:write"])),
):
    """Enviar factura al SII de Hacienda"""
    try:
        return await hacienda_service.enviar_factura_emitida(factura.dict())
    except HaciendaError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

@router.post("/hacienda/modelo-303", dependencies=[Depends(thalos_request_guard)])
async def presentar_modelo_303(
    modelo: Modelo303,
    _: User = Depends(require_scopes(["tax:write"])),
):
    """Presentar Modelo 303 (IVA trimestral)"""
    try:
        return await hacienda_service.presentar_modelo_303(
            trimestre=modelo.trimestre,
            ejercicio=modelo.ejercicio,
            datos=modelo.dict()
        )
    except HaciendaError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

@router.get("/hacienda/status")
async def hacienda_status(
    _: User = Depends(require_scopes(["tax:read"])),
):
    """Obtener estado del servicio de Hacienda"""
    return hacienda_service.get_status()

# ============================================================================
# STRIPE ENDPOINTS
# ============================================================================

@router.post("/stripe/payment-intent", dependencies=[Depends(thalos_request_guard)])
async def create_payment(
    payment: PaymentIntent,
    _: User = Depends(require_scopes(["tax:write"])),
):
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


@router.post("/stripe/checkout/payment-intent")
async def create_checkout_payment_intent(payment: PublicCheckoutPaymentIntent):
    """
    Crear Payment Intent PÚBLICO para el checkout de alta de un cliente
    nuevo (`/checkout/:plan`, ruta sin sesión -- el visitante todavía no
    tiene cuenta ni token, por diseño: paga primero y crea la cuenta
    después con `/onboarding/create-account`).

    Deliberadamente separado del endpoint genérico
    `/stripe/payment-intent` (que exige `tax:write`, pensado para uso
    autenticado, ej. un usuario ya logueado gestionando su facturación) en
    vez de quitarle la autenticación a ese endpoint genérico: así no se
    debilita ninguna protección existente sobre una superficie que puede
    tener otros usos futuros.

    Controles anti-abuso de esta ruta pública:
    - El importe NUNCA se toma del cliente. Se calcula en el servidor a
      partir de `plan`, usando la misma tabla de precios (`PRICING_PLANS`)
      que ya usa `/onboarding/create-account` para validar el pago -- si el
      cliente manda un plan que no existe, 400 sin llamar a Stripe.
    - Pasa por el `SecurityMiddleware` global (rate limiting por IP,
      bucket dedicado y estricto para esta ruta -- ver
      `app/core/security_middleware.py`), igual que el resto del núcleo.
    - No crea ninguna cuenta ni persiste nada en la BD propia -- solo
      genera un PaymentIntent en Stripe. La creación real de la cuenta
      sigue exigiendo, en `/onboarding/create-account`, verificar contra
      la API de Stripe que ese PaymentIntent está `succeeded`.
    """
    plan_config = PRICING_PLANS.get(payment.plan)
    if plan_config is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Plan '{payment.plan}' no válido. "
                f"Planes válidos: {list(PRICING_PLANS.keys())}"
            ),
        )

    # Importe calculado en el servidor -- nunca confiar en un importe
    # enviado por el cliente para este flujo público.
    amount = plan_config["setup_price"] + plan_config["monthly_price"]

    metadata: Dict[str, str] = {}
    for key, value in (payment.metadata or {}).items():
        if value is not None:
            metadata[key] = str(value)
    metadata["plan"] = payment.plan

    description = payment.description or (
        f"{plan_config['name']} - Setup + primera mensualidad (checkout público)"
    )

    result = await stripe_service.create_payment_intent(
        amount=amount,
        customer_email=payment.customer_email,
        description=description,
        metadata=metadata,
    )

    if not result.get("success"):
        logger.error(
            "checkout_payment_intent_failed plan=%s customer_email=%s error=%s",
            payment.plan, payment.customer_email, result.get("error"),
        )
        raise HTTPException(status_code=502, detail=result.get("error"))

    logger.info(
        "checkout_payment_intent_created plan=%s amount=%s customer_email=%s payment_intent_id=%s",
        payment.plan, amount, payment.customer_email, result.get("payment_intent_id"),
    )

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
async def stripe_status(
    _: User = Depends(require_scopes(["tax:read"])),
):
    """Obtener estado del servicio de Stripe"""
    return stripe_service.get_status()

# ============================================================================
# STATUS GLOBAL
# ============================================================================

@router.get("/status")
async def integrations_status(
    _: User = Depends(get_current_active_superuser),
):
    """Obtener estado de todas las integraciones"""
    return {
        "whatsapp": whatsapp_service.get_status(),
        "email": email_service.get_status(),
        "hacienda": hacienda_service.get_status(),
        "stripe": stripe_service.get_status(),
        "timestamp": datetime.utcnow().isoformat()
    }

