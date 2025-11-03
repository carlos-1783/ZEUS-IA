"""
💳 Stripe Service - Payment Processing
Automatiza procesamiento de pagos y suscripciones
"""
import os
from typing import Optional, Dict, Any
import stripe
from app.core.config import settings

class StripeService:
    """Servicio para procesamiento de pagos con Stripe"""
    
    def __init__(self):
        self.api_key = os.getenv("STRIPE_API_KEY")
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
        self.currency = os.getenv("STRIPE_CURRENCY", "eur")
        
        if self.api_key:
            stripe.api_key = self.api_key
            print("✅ Stripe Service inicializado correctamente")
        else:
            print("⚠️ Stripe Service: STRIPE_API_KEY no configurada")
    
    def is_configured(self) -> bool:
        """Verificar si el servicio está configurado"""
        return bool(self.api_key)
    
    async def create_payment_intent(
        self,
        amount: float,
        customer_email: str,
        description: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Crear Payment Intent para procesar pago
        
        Args:
            amount: Cantidad en euros (ej: 99.99)
            customer_email: Email del cliente
            description: Descripción del pago
            metadata: Metadatos adicionales
            
        Returns:
            Dict con client_secret y payment_intent_id
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "Stripe service not configured. Set STRIPE_API_KEY"
            }
        
        try:
            # Convertir a centavos
            amount_cents = int(amount * 100)
            
            payment_intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=self.currency,
                description=description,
                receipt_email=customer_email,
                metadata=metadata or {}
            )
            
            return {
                "success": True,
                "payment_intent_id": payment_intent.id,
                "client_secret": payment_intent.client_secret,
                "amount": amount,
                "currency": self.currency,
                "status": payment_intent.status
            }
            
        except stripe.error.StripeError as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def create_customer(
        self,
        email: str,
        name: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Crear cliente en Stripe
        
        Args:
            email: Email del cliente
            name: Nombre del cliente
            metadata: Metadatos adicionales
            
        Returns:
            Dict con customer_id
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "Stripe service not configured"
            }
        
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )
            
            return {
                "success": True,
                "customer_id": customer.id,
                "email": email
            }
            
        except stripe.error.StripeError as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        trial_days: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Crear suscripción
        
        Args:
            customer_id: ID del cliente en Stripe
            price_id: ID del precio/plan
            trial_days: Días de prueba gratuita
            
        Returns:
            Dict con subscription_id y status
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "Stripe service not configured"
            }
        
        try:
            subscription_params = {
                "customer": customer_id,
                "items": [{"price": price_id}]
            }
            
            if trial_days:
                subscription_params["trial_period_days"] = trial_days
            
            subscription = stripe.Subscription.create(**subscription_params)
            
            return {
                "success": True,
                "subscription_id": subscription.id,
                "status": subscription.status,
                "current_period_end": subscription.current_period_end
            }
            
        except stripe.error.StripeError as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def process_webhook(
        self,
        payload: str,
        sig_header: str
    ) -> Dict[str, Any]:
        """
        Procesar webhook de Stripe
        
        Args:
            payload: Cuerpo del webhook
            sig_header: Signature header
            
        Returns:
            Dict con evento procesado
        """
        if not self.webhook_secret:
            return {
                "success": False,
                "error": "Webhook secret not configured"
            }
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            # Procesar diferentes tipos de eventos
            event_type = event['type']
            
            if event_type == 'payment_intent.succeeded':
                payment_intent = event['data']['object']
                return {
                    "success": True,
                    "event": "payment_succeeded",
                    "amount": payment_intent['amount'] / 100,
                    "customer_email": payment_intent.get('receipt_email')
                }
            
            elif event_type == 'payment_intent.payment_failed':
                payment_intent = event['data']['object']
                return {
                    "success": True,
                    "event": "payment_failed",
                    "error_message": payment_intent.get('last_payment_error', {}).get('message')
                }
            
            return {
                "success": True,
                "event": event_type,
                "processed": True
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_status(self) -> Dict[str, Any]:
        """Obtener estado del servicio"""
        return {
            "configured": self.is_configured(),
            "provider": "Stripe",
            "currency": self.currency,
            "webhooks_enabled": bool(self.webhook_secret),
            "mode": "test" if self.api_key and self.api_key.startswith("sk_test") else "live"
        }


# Instancia global
stripe_service = StripeService()

