"""
Stripe Webhook Handler - Real payment persistence and auto-onboarding
Handles payment_intent.succeeded: persists payment, activates user, triggers onboarding.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, Optional

import stripe
from fastapi import APIRouter, HTTPException, Header, Request, status
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.user import User
from services.activity_logger import ActivityLogger
from services.email_service import email_service
from services.stripe_service import stripe_service
from services.whatsapp_service import whatsapp_service


router = APIRouter(tags=["webhooks"])

# Log router registration
import logging
logger = logging.getLogger(__name__)
logger.info("[WEBHOOKS] Router webhooks inicializado")


@router.get("/stripe")
async def stripe_webhook_health():
    """
    Health check endpoint for Stripe webhook.
    Returns 200 OK if endpoint is accessible.
    """
    return {
        "status": "ok",
        "endpoint": "/api/v1/webhooks/stripe",
        "method": "POST",
        "event": "payment_intent.succeeded"
    }


@router.get("/twilio")
async def twilio_webhook_health():
    """
    Health check endpoint for Twilio webhook.
    Returns 200 OK if endpoint is accessible.
    """
    return {
        "status": "ok",
        "endpoint": "/api/v1/webhooks/twilio",
        "method": "POST",
        "events": ["message.received", "message.sent"],
        "description": "Twilio WhatsApp webhook handler"
    }


def generate_random_password(length: int = 16) -> str:
    """Generate secure random password"""
    import secrets
    import string
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


async def _send_welcome_email_and_log(
    email: str,
    company_name: str,
    full_name: str,
    temp_password: str,
    plan: str,
    db: Session
) -> bool:
    """Send welcome email and log it in DB"""
    plan_names = {
        "startup": "ZEUS STARTUP",
        "growth": "ZEUS GROWTH",
        "business": "ZEUS BUSINESS",
        "enterprise": "ZEUS ENTERPRISE"
    }
    
    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; }}
            .header {{ background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%); padding: 30px; text-align: center; }}
            .header h1 {{ color: white; margin: 0; font-size: 32px; }}
            .content {{ padding: 40px 30px; background: #f9fafb; }}
            .credentials-box {{ background: #1a1f2e; color: white; padding: 20px; border-radius: 10px; margin: 20px 0; }}
            .cta-button {{ display: inline-block; background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%); color: white; padding: 16px 32px; text-decoration: none; border-radius: 8px; font-weight: bold; }}
            .footer {{ padding: 20px; text-align: center; background: #e5e7eb; font-size: 12px; color: #6b7280; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>⚡ Bienvenido a ZEUS-IA</h1>
        </div>
        
        <div class="content">
            <h2>¡Hola {full_name}!</h2>
            
            <p>Gracias por unirte a ZEUS-IA. Tu cuenta para <strong>{company_name}</strong> ha sido creada exitosamente.</p>
            
            <p>Has adquirido el plan <strong>{plan_names.get(plan, plan)}</strong>.</p>
            
            <h3>🔐 Tus credenciales de acceso:</h3>
            
            <div class="credentials-box">
                <p><strong>URL:</strong> https://zeus-ia-production-16d8.up.railway.app/dashboard</p>
                <p><strong>Email:</strong> {email}</p>
                <p><strong>Contraseña temporal:</strong> {temp_password}</p>
            </div>
            
            <p>⚠️ <strong>IMPORTANTE:</strong> Te recomendamos cambiar esta contraseña temporal en tu primer acceso desde Configuración.</p>
            
            <h3>🚀 Próximos pasos:</h3>
            <ol>
                <li>Accede al dashboard con tus credenciales</li>
                <li>Explora los 5 agentes IA disponibles</li>
                <li>Configura tus integraciones (WhatsApp, Email, etc.)</li>
                <li>¡Empieza a automatizar tu empresa!</li>
            </ol>
            
            <p style="text-align: center; margin-top: 30px;">
                <a href="https://zeus-ia-production-16d8.up.railway.app/dashboard" class="cta-button">
                    Acceder al Dashboard →
                </a>
            </p>
            
            <p style="margin-top: 30px;">Si tienes alguna pregunta, responde a este email y nuestro equipo te ayudará.</p>
            
            <p>¡Bienvenido al Olimpo! ⚡</p>
            <p><em>El equipo de ZEUS-IA</em></p>
        </div>
        
        <div class="footer">
            <p>Este email fue enviado por ZEUS-IA</p>
            <p>© 2025 ZEUS-IA. Todos los derechos reservados.</p>
        </div>
    </body>
    </html>
    """
    
    email_sent = False
    if email_service.is_configured():
        result = await email_service.send_email(
            to_email=email,
            subject=f"🎉 Bienvenido a ZEUS-IA - Tus credenciales de acceso",
            content=html_content,
            content_type="text/html"
        )
        email_sent = result.get("success", False)
        
        ActivityLogger.log_activity(
            agent_name="ZEUS",
            action_type="email_sent",
            action_description=f"Email de bienvenida enviado a {email}",
            details={
                "to": email,
                "subject": "Bienvenido a ZEUS-IA",
                "email_sent": email_sent,
                "status_code": result.get("status_code"),
            },
            user_email=email,
            status="completed" if email_sent else "failed",
            priority="high"
        )
    else:
        print(f"\n[WEBHOOK] Email de bienvenida (SendGrid no configurado): {email} / {temp_password}\n")
        email_sent = True
    
    return email_sent


@router.post("/stripe")
async def stripe_webhook_handler(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="Stripe-Signature")
):
    """
    Stripe webhook handler: persists payment, activates user, triggers onboarding.
    Verifies signature using STRIPE_WEBHOOK_SECRET.
    
    Endpoint: POST /api/v1/webhooks/stripe
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[WEBHOOK] Stripe webhook recibido - Method: {request.method}")
    
    payload = await request.body()
    
    if not stripe_signature:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Stripe-Signature header")
    
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="STRIPE_WEBHOOK_SECRET not configured"
        )
    
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, webhook_secret
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid payload: {e}")
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid signature: {e}")
    
    event_type = event.get("type")
    
    if event_type != "payment_intent.succeeded":
        return {"received": True, "event_type": event_type, "processed": False}
    
    payment_intent = event["data"]["object"]
    payment_intent_id = payment_intent.get("id")
    amount = payment_intent.get("amount", 0) / 100
    currency = payment_intent.get("currency", "eur").upper()
    customer_email = payment_intent.get("receipt_email") or payment_intent.get("metadata", {}).get("customer_email")
    metadata = payment_intent.get("metadata", {})
    plan = metadata.get("plan") or metadata.get("plan_type")
    company_name = metadata.get("company_name") or metadata.get("company")
    full_name = metadata.get("full_name") or metadata.get("name") or customer_email.split("@")[0]
    employees = metadata.get("employees")
    stripe_customer_id = payment_intent.get("customer")
    
    if not customer_email:
        ActivityLogger.log_activity(
            agent_name="ZEUS",
            action_type="payment_webhook_error",
            action_description=f"Payment intent {payment_intent_id} sin customer_email",
            details={"payment_intent_id": payment_intent_id, "amount": amount},
            status="failed",
            priority="high"
        )
        return {"received": True, "error": "No customer_email in payment_intent"}
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == customer_email).first()
        is_new_user = user is None
        
        if is_new_user:
            temp_password = generate_random_password()
            user = User(
                email=customer_email,
                full_name=full_name,
                hashed_password=get_password_hash(temp_password),
                is_active=True,
                is_superuser=False,
                company_name=company_name,
                employees=int(employees) if employees else None,
                plan=plan or "startup",
                stripe_customer_id=stripe_customer_id,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            
            email_sent = await _send_welcome_email_and_log(
                email=customer_email,
                company_name=company_name or "Tu Empresa",
                full_name=full_name,
                temp_password=temp_password,
                plan=plan or "startup",
                db=db
            )
        else:
            if stripe_customer_id and not user.stripe_customer_id:
                user.stripe_customer_id = stripe_customer_id
            if plan and not user.plan:
                user.plan = plan
            if company_name and not user.company_name:
                user.company_name = company_name
            if employees and not user.employees:
                user.employees = int(employees)
            user.is_active = True
            db.commit()
            email_sent = True
        
        ActivityLogger.log_activity(
            agent_name="ZEUS",
            action_type="payment_confirmed",
            action_description=f"Pago confirmado: {amount} {currency} - {customer_email}",
            details={
                "payment_intent_id": payment_intent_id,
                "stripe_customer_id": stripe_customer_id,
                "amount": amount,
                "currency": currency,
                "plan": plan or user.plan,
                "is_new_user": is_new_user,
                "user_id": user.id,
                "email_sent": email_sent,
                "executed_handler": "STRIPE_WEBHOOK_HANDLER",
            },
            metrics={
                "amount": amount,
                "currency": currency,
                "executed_handler": "STRIPE_WEBHOOK_HANDLER",
            },
            user_email=customer_email,
            status="completed",
            priority="critical"
        )
        
        return {
            "received": True,
            "event_type": event_type,
            "processed": True,
            "payment_intent_id": payment_intent_id,
            "user_id": user.id,
            "is_new_user": is_new_user,
            "email_sent": email_sent,
        }
    except Exception as e:
        db.rollback()
        ActivityLogger.log_activity(
            agent_name="ZEUS",
            action_type="payment_webhook_error",
            action_description=f"Error procesando pago {payment_intent_id}: {str(e)}",
            details={
                "payment_intent_id": payment_intent_id,
                "error": str(e),
            },
            status="failed",
            priority="critical"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing webhook: {str(e)}"
        )
    finally:
        db.close()


@router.post("/twilio")
async def twilio_webhook_handler(request: Request):
    """
    Twilio webhook handler: receives WhatsApp messages, persists and processes.
    Endpoint: POST /api/v1/webhooks/twilio
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[WEBHOOK] Twilio webhook recibido - Method: {request.method}")
    
    try:
        form_data = await request.form()
        
        from_number = form_data.get("From", "").replace("whatsapp:", "")
        to_number = form_data.get("To", "").replace("whatsapp:", "")
        message_body = form_data.get("Body", "")
        message_sid = form_data.get("MessageSid", "")
        account_sid = form_data.get("AccountSid", "")
        num_media = form_data.get("NumMedia", "0")
        
        if not from_number or not message_body:
            ActivityLogger.log_activity(
                agent_name="ZEUS",
                action_type="whatsapp_webhook_error",
                action_description="Twilio webhook sin from_number o message_body",
                details={"form_data_keys": list(form_data.keys())},
                status="failed",
                priority="high"
            )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing From or Body")
        
        # Verificar si Twilio está en sandbox
        is_sandbox = "14155238886" in to_number or "sandbox" in to_number.lower()
        
        # Registrar mensaje recibido
        ActivityLogger.log_activity(
            agent_name="ZEUS",
            action_type="whatsapp_received",
            action_description=f"WhatsApp recibido de {from_number}",
            details={
                "from": from_number,
                "to": to_number,
                "body": message_body[:200],  # Primeros 200 caracteres
                "message_sid": message_sid,
                "account_sid": account_sid,
                "num_media": num_media,
                "is_sandbox": is_sandbox,
                "executed_handler": "TWILIO_WEBHOOK_HANDLER",
            },
            metrics={
                "executed_handler": "TWILIO_WEBHOOK_HANDLER",
                "is_sandbox": is_sandbox,
            },
            status="completed",
            priority="high"
        )
        
        # Procesar mensaje con agente (si no está en sandbox o si se permite procesar sandbox)
        if is_sandbox:
            logger.warning(f"[WEBHOOK] Mensaje recibido en sandbox de {from_number}")
        
        result = await whatsapp_service.process_incoming_message(
            from_number=from_number,
            message_body=message_body,
            agent_name="ZEUS CORE"
        )
        
        # Registrar respuesta enviada si fue exitosa
        if result.get("success") and result.get("whatsapp_status", {}).get("success"):
            ActivityLogger.log_activity(
                agent_name="ZEUS",
                action_type="whatsapp_sent",
                action_description=f"WhatsApp enviado a {from_number} (respuesta automática)",
                details={
                    "to": from_number,
                    "from": to_number,
                    "response_preview": result.get("response", "")[:100],
                    "message_sid": result.get("whatsapp_status", {}).get("message_sid"),
                    "executed_handler": "TWILIO_WEBHOOK_HANDLER",
                },
                metrics={
                    "executed_handler": "TWILIO_WEBHOOK_HANDLER",
                },
                status="completed",
                priority="high"
            )
        
        return {
            "received": True,
            "processed": True,
            "from": from_number,
            "message_sid": message_sid,
            "agent_response": result.get("success", False),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[WEBHOOK] Error procesando webhook de Twilio: {e}")
        ActivityLogger.log_activity(
            agent_name="ZEUS",
            action_type="whatsapp_webhook_error",
            action_description=f"Error procesando webhook de Twilio: {str(e)}",
            details={
                "error": str(e),
            },
            status="failed",
            priority="critical"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing Twilio webhook: {str(e)}"
        )
