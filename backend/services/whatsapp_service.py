"""
🔷 WhatsApp Service - Twilio Integration

Credenciales: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN y TWILIO_WHATSAPP_NUMBER (o TWILIO_WHATSAPP_FROM).

TWILIO_WHATSAPP_ENABLED: DESACTIVADO por defecto (Fase 2, auditoria #16). Hay que ponerlo a
true/1/yes de forma explicita para enviar, aunque existan credenciales.

Mensajes entrantes: no se responde automaticamente a remitentes que no se puedan asociar a una
empresa (hoy no existe mapeo numero -> empresa en el modelo de datos), solo se registran.
Logs con PII minimizada: telefono enmascarado y nunca el cuerpo del mensaje.

Twilio 63031: "From" y "To" no pueden ser el mismo identificador; se valida antes de llamar a la API.
"""
import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def _env_flag(name: str, default: bool = True) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def _mask(addr: Optional[str]) -> str:
    """Telefono enmascarado para logs (PII minima)."""
    from services.outbound_consent_v1 import mask_phone

    return mask_phone(addr)


def _whatsapp_canonical(addr: str) -> str:
    """Compara números Twilio WhatsApp sin depender del prefijo whatsapp:."""
    s = (addr or "").strip().lower()
    if s.startswith("whatsapp:"):
        s = s[9:]
    return "".join(c for c in s if c.isdigit() or c == "+")

try:
    from twilio.rest import Client  # type: ignore[reportMissingImports]
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    Client = None


class WhatsAppService:
    """Servicio para automatización de WhatsApp vía Twilio"""
    
    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.whatsapp_enabled = _env_flag("TWILIO_WHATSAPP_ENABLED", default=False)
        # TWILIO_WHATSAPP_FROM o TWILIO_WHATSAPP_NUMBER (número productivo o sandbox)
        self.whatsapp_number = (
            os.getenv("TWILIO_WHATSAPP_FROM")
            or os.getenv("TWILIO_WHATSAPP_NUMBER")
            or "whatsapp:+14155238886"
        )
        self.client = None
        if not TWILIO_AVAILABLE:
            logger.warning("WhatsApp Service: Twilio library not installed (pip install twilio)")
        elif not self.whatsapp_enabled:
            logger.info("WhatsApp Service: TWILIO_WHATSAPP_ENABLED=false, sending disabled")
        elif self.account_sid and self.auth_token:
            try:
                self.client = Client(self.account_sid, self.auth_token)
                logger.info("WhatsApp Service: initialized successfully")
            except Exception as e:
                logger.warning("WhatsApp Service init failed: %s", e)
        else:
            logger.warning("WhatsApp Service: Twilio credentials not configured")
    
    def is_configured(self) -> bool:
        """Cliente Twilio listo y envío WhatsApp permitido por configuración."""
        return bool(self.whatsapp_enabled and self.client is not None)
    
    async def send_message(
        self, 
        to_number: str, 
        message: str,
        media_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enviar mensaje de WhatsApp
        
        Args:
            to_number: Número del destinatario (formato: +34612345678)
            message: Contenido del mensaje
            media_url: URL de imagen/archivo adjunto (opcional)
            
        Returns:
            Dict con status y message_sid
        """
        if not self.whatsapp_enabled:
            return {
                "success": False,
                "error": "WhatsApp desactivado (TWILIO_WHATSAPP_ENABLED=false). Actívalo cuando Twilio/WhatsApp estén listos.",
            }
        if not self.is_configured():
            return {
                "success": False,
                "error": "WhatsApp service not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and TWILIO_WHATSAPP_NUMBER (or TWILIO_WHATSAPP_FROM)"
            }
        
        try:
            if not to_number.startswith("whatsapp:"):
                to_number = f"whatsapp:{to_number}"

            if _whatsapp_canonical(self.whatsapp_number) == _whatsapp_canonical(to_number):
                err = (
                    "Twilio 63031: el remitente (From) y el destino (To) no pueden ser el mismo número. "
                    "TWILIO_WHATSAPP_FROM debe ser el número de Twilio/sandbox; el cliente va en To."
                )
                logger.warning("[WHATSAPP] %s", err)
                return {"success": False, "error": err, "twilio_error_code": "63031"}
            
            message_params = {
                "from_": self.whatsapp_number,
                "to": to_number,
                "body": message
            }
            if media_url:
                message_params["media_url"] = [media_url]
            
            # Envío real: solo depende de credenciales (is_configured). Sin candados.
            twilio_message = self.client.messages.create(**message_params)
            
            result = {
                "success": True,
                "message_sid": twilio_message.sid,
                "status": twilio_message.status,
                "to": to_number
            }
            
            try:
                from services.activity_logger import ActivityLogger
                ActivityLogger.log_activity(
                    agent_name="ZEUS",
                    action_type="whatsapp_sent",
                    action_description=f"WhatsApp enviado a {_mask(to_number)}",
                    details={
                        "to_masked": _mask(to_number),
                        "from": self.whatsapp_number,
                        "message_sid": twilio_message.sid,
                        "status": twilio_message.status,
                        "body_chars": len(message or ""),
                    },
                    metrics={"status": twilio_message.status},
                    status="completed",
                    priority="high"
                )
            except Exception as log_error:
                logger.warning("[WHATSAPP] Error registrando actividad: %s", log_error)
            
            return result
            
        except Exception as e:
            error_result = {
                "success": False,
                "error": str(e)
            }
            try:
                from services.activity_logger import ActivityLogger
                ActivityLogger.log_activity(
                    agent_name="ZEUS",
                    action_type="whatsapp_send_error",
                    action_description=f"Error enviando WhatsApp a {_mask(to_number)}: {type(e).__name__}",
                    details={
                        "to_masked": _mask(to_number),
                        "from": self.whatsapp_number,
                        "error": str(e)[:300],
                    },
                    status="failed",
                    priority="high"
                )
            except Exception as log_error:
                logger.warning("[WHATSAPP] Error registrando fallo de envio: %s", log_error)
            return error_result
    
    async def process_incoming_message(
        self,
        from_number: str,
        message_body: str,
        agent_name: str = "ZEUS CORE",
        to_number: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Registrar un mensaje entrante. NO responde automaticamente si el mensaje no se puede
        asociar a una empresa (no hay mapeo numero -> empresa): antes respondia con el LLM a
        cualquier remitente, sin tenant, y con un texto fijo de relleno si el agente no daba
        contenido. Ahora solo se registra (telefono enmascarado, sin cuerpo).

        Hoy NO existe en el modelo de datos un mapeo numero de WhatsApp -> empresa (todas las
        empresas comparten el numero de Twilio de la plataforma), asi que ningun entrante se puede
        asociar a una empresa y ninguno recibe respuesta automatica. Cuando exista ese mapeo, la
        respuesta por empresa se implementa aqui (con contenido real del agente, nunca relleno)."""
        from services.activity_logger import ActivityLogger

        ActivityLogger.log_activity(
            agent_name=agent_name,
            action_type="whatsapp_inbound_unrouted",
            action_description="WhatsApp entrante sin empresa asociada: no se responde automaticamente",
            details={
                "from_masked": _mask(from_number),
                "to": to_number,
                "body_chars": len(message_body or ""),
                "auto_reply": False,
                "reason": "sin_empresa_asociada",
            },
            status="blocked",
            priority="normal",
        )
        logger.info("[WHATSAPP] entrante sin empresa asociada de %s: sin respuesta automatica", _mask(from_number))
        return {
            "success": True,
            "processed": False,
            "auto_reply": False,
            "reason": "sin_empresa_asociada",
        }

    def get_status(self) -> Dict[str, Any]:
        """Estado del servicio. Envío permitido si configured=True (credenciales + enabled)."""
        return {
            "enabled": self.whatsapp_enabled,
            "configured": self.is_configured(),
            "provider": "Twilio",
            "whatsapp_number": self.whatsapp_number if self.is_configured() else None,
        }


# Instancia global
whatsapp_service = WhatsAppService()

