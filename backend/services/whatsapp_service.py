"""
🔷 WhatsApp Service - Twilio Integration

Credenciales: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN y TWILIO_WHATSAPP_NUMBER (o TWILIO_WHATSAPP_FROM).

TWILIO_WHATSAPP_ENABLED=false (o 0/no) desactiva el envío aunque existan credenciales (útil hasta
activar sandbox o número de WhatsApp Business en Twilio).

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
        self.whatsapp_enabled = _env_flag("TWILIO_WHATSAPP_ENABLED", default=True)
        # TWILIO_WHATSAPP_FROM o TWILIO_WHATSAPP_NUMBER (número productivo o sandbox)
        self.whatsapp_number = (
            os.getenv("TWILIO_WHATSAPP_FROM")
            or os.getenv("TWILIO_WHATSAPP_NUMBER")
            or "whatsapp:+14155238886"
        )
        self.client = None
        if not TWILIO_AVAILABLE:
            print("⚠️ WhatsApp Service: Twilio library not installed (pip install twilio)")
        elif not self.whatsapp_enabled:
            print("ℹ️ WhatsApp Service: TWILIO_WHATSAPP_ENABLED=false — envío desactivado")
        elif self.account_sid and self.auth_token:
            try:
                self.client = Client(self.account_sid, self.auth_token)
                print("✅ WhatsApp Service inicializado correctamente")
            except Exception as e:
                print(f"⚠️ WhatsApp Service no pudo inicializar: {e}")
        else:
            print("⚠️ WhatsApp Service: Credenciales de Twilio no configuradas")
    
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
                    action_description=f"WhatsApp enviado a {to_number}",
                    details={
                        "to": to_number,
                        "from": self.whatsapp_number,
                        "message_sid": twilio_message.sid,
                        "status": twilio_message.status,
                        "body_preview": (message[:100] if message else None),
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
                    action_description=f"Error enviando WhatsApp a {to_number}: {str(e)}",
                    details={
                        "to": to_number,
                        "from": self.whatsapp_number,
                        "error": str(e),
                    },
                    status="failed",
                    priority="high"
                )
            except Exception:
                pass
            return error_result
    
    async def process_incoming_message(
        self, 
        from_number: str, 
        message_body: str,
        agent_name: str = "ZEUS CORE"
    ) -> Dict[str, Any]:
        """
        Procesar mensaje entrante y generar respuesta automática
        
        Args:
            from_number: Número del remitente
            message_body: Contenido del mensaje
            agent_name: Agente que debe responder
            
        Returns:
            Dict con respuesta del agente
        """
        try:
            # Importar agentes y logger
            from agents.zeus_core import ZeusCore
            from agents.perseo import Perseo
            from services.activity_logger import activity_logger
            
            # Mapeo de agentes
            agents_map = {
                "ZEUS CORE": ZeusCore(),
                "PERSEO": Perseo()
            }
            
            agent = agents_map.get(agent_name, agents_map["ZEUS CORE"])
            
            # Procesar solicitud
            context = {
                "user_message": message_body,
                "channel": "whatsapp",
                "from_number": from_number,
                "priority": "high"
            }
            
            result = agent.process_request(context)
            
            # Preparar respuesta
            if result.get("success"):
                response_text = result.get("content", result.get("response", "Mensaje procesado"))
                
                # Enviar respuesta automática
                send_result = await self.send_message(from_number, response_text)
                
                # ✅ REGISTRAR ACTIVIDAD
                activity_logger.log_activity(
                    agent_name=agent_name,
                    action_type="whatsapp_response",
                    action_description=f"Respondido WhatsApp de {from_number}",
                    details={
                        "from": from_number,
                        "message": message_body[:100],  # Primeros 100 caracteres
                        "response": response_text[:100],
                        "channel": "whatsapp"
                    },
                    metrics={
                        "response_time": "instant",
                        "message_sent": send_result.get("success", False)
                    },
                    status="completed",
                    priority="high"
                )
                
                return {
                    "success": True,
                    "agent": agent_name,
                    "response": response_text,
                    "whatsapp_status": send_result
                }
            else:
                error_msg = "Lo siento, tuve un problema procesando tu mensaje."
                await self.send_message(from_number, error_msg)
                
                # ✅ REGISTRAR ERROR
                activity_logger.log_activity(
                    agent_name=agent_name,
                    action_type="whatsapp_error",
                    action_description=f"Error procesando WhatsApp de {from_number}",
                    details={
                        "from": from_number,
                        "message": message_body[:100],
                        "error": result.get("error", "Unknown")
                    },
                    status="failed",
                    priority="high"
                )
                
                return {
                    "success": False,
                    "error": result.get("error", "Unknown error")
                }
                
        except Exception as e:
            error_msg = "Lo siento, ocurrió un error. Por favor intenta más tarde."
            if self.is_configured():
                await self.send_message(from_number, error_msg)
            
            # ✅ REGISTRAR EXCEPCIÓN
            from services.activity_logger import activity_logger
            activity_logger.log_activity(
                agent_name=agent_name,
                action_type="whatsapp_exception",
                action_description=f"Excepción procesando WhatsApp",
                details={
                    "from": from_number,
                    "exception": str(e)
                },
                status="failed",
                priority="critical"
            )
            
            return {
                "success": False,
                "error": str(e)
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

