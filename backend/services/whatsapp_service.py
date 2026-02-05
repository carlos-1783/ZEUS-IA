"""
🔷 WhatsApp Service - Twilio Integration
Automatiza respuestas a clientes por WhatsApp.
Fuente de verdad: ENV VARS (WHATSAPP_SANDBOX_MODE, ENVIRONMENT).
Si WHATSAPP_SANDBOX_MODE=false y ENVIRONMENT=production → enviar SIEMPRE.
"""
import os
import logging
from typing import Optional, Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    from twilio.rest import Client  # type: ignore[reportMissingImports]
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    Client = None


def _whatsapp_sandbox_mode() -> bool:
    """Única fuente de verdad: env var WHATSAPP_SANDBOX_MODE."""
    return os.getenv("WHATSAPP_SANDBOX_MODE", "false").strip().lower() in ("true", "1", "yes")


def _environment_is_production() -> bool:
    """Entorno de producción."""
    env = os.getenv("ENVIRONMENT", os.getenv("RAILWAY_ENVIRONMENT", "")).strip().lower()
    return env == "production"


def _send_allowed() -> bool:
    """Si WHATSAPP_SANDBOX_MODE=false y ENVIRONMENT=production → enviar SIEMPRE."""
    if _whatsapp_sandbox_mode():
        return False
    if _environment_is_production():
        return True
    return True  # Permitir en no-production si sandbox_mode no está forzado


class WhatsAppService:
    """Servicio para automatización de WhatsApp vía Twilio"""
    
    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.whatsapp_number = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
        
        self.client = None
        if not TWILIO_AVAILABLE:
            print("⚠️ WhatsApp Service: Twilio library not installed (pip install twilio)")
        elif self.account_sid and self.auth_token:
            try:
                self.client = Client(self.account_sid, self.auth_token)
                print("✅ WhatsApp Service inicializado correctamente")
            except Exception as e:
                print(f"⚠️ WhatsApp Service no pudo inicializar: {e}")
        else:
            print("⚠️ WhatsApp Service: Credenciales de Twilio no configuradas")
    
    def is_configured(self) -> bool:
        """Verificar si el servicio está configurado"""
        return self.client is not None
    
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
        if not self.is_configured():
            return {
                "success": False,
                "error": "WhatsApp service not configured. Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN"
            }
        
        try:
            # Formatear número para WhatsApp
            if not to_number.startswith("whatsapp:"):
                to_number = f"whatsapp:{to_number}"
            
            # Preparar parámetros
            message_params = {
                "from_": self.whatsapp_number,
                "to": to_number,
                "body": message
            }
            
            if media_url:
                message_params["media_url"] = [media_url]
            
            # Única fuente de verdad: ENV VARS (no hardcode)
            send_allowed = _send_allowed()
            sandbox_mode = _whatsapp_sandbox_mode()
            env_production = _environment_is_production()
            
            if not send_allowed:
                cause = "WHATSAPP_SANDBOX_MODE=true (env)" if sandbox_mode else "ENVIRONMENT no es production"
                from services.activity_logger import ActivityLogger
                ActivityLogger.log_activity(
                    agent_name="ZEUS",
                    action_type="whatsapp_blocked",
                    action_description=f"Envio WhatsApp bloqueado: {cause}",
                    details={
                        "to": to_number,
                        "whatsapp_number": self.whatsapp_number,
                        "reason": "env_block",
                        "WHATSAPP_SANDBOX_MODE": os.getenv("WHATSAPP_SANDBOX_MODE"),
                        "ENVIRONMENT": os.getenv("ENVIRONMENT"),
                        "message_preview": message[:50] if message else None,
                    },
                    status="blocked",
                    priority="high"
                )
                logger.warning("[WHATSAPP] Bloqueado por env: %s", cause)
                return {
                    "success": False,
                    "error": f"WhatsApp bloqueado: {cause}. Para producción: WHATSAPP_SANDBOX_MODE=false y ENVIRONMENT=production.",
                    "blocked": True,
                    "reason": "env_block",
                    "cause": cause,
                }
            
            logger.info(
                "[WHATSAPP] WHATSAPP_SEND_ALLOWED=true | mode=%s | env=%s | to=%s",
                "sandbox" if sandbox_mode else "production",
                "production" if env_production else os.getenv("ENVIRONMENT", "NOT_SET"),
                to_number,
            )
            
            # Enviar mensaje
            twilio_message = self.client.messages.create(**message_params)
            
            result = {
                "success": True,
                "message_sid": twilio_message.sid,
                "status": twilio_message.status,
                "to": to_number
            }
            
            # ✅ REGISTRAR ACTIVIDAD: WhatsApp enviado directamente
            try:
                from services.activity_logger import ActivityLogger
                ActivityLogger.log_activity(
                    agent_name="ZEUS",
                    action_type="whatsapp_sent",
                    action_description=f"WhatsApp enviado a {to_number}",
                    details={
                        "to": to_number,
                        "message_sid": twilio_message.sid,
                        "status": twilio_message.status,
                        "message_preview": message[:50] if message else None,
                    },
                    metrics={"status": twilio_message.status},
                    status="completed",
                    priority="high"
                )
            except Exception as log_error:
                print(f"[WHATSAPP] Error registrando actividad: {log_error}")
            
            return result
            
        except Exception as e:
            error_result = {
                "success": False,
                "error": str(e)
            }
            
            # ✅ REGISTRAR ERROR: WhatsApp fallido
            try:
                from services.activity_logger import ActivityLogger
                ActivityLogger.log_activity(
                    agent_name="ZEUS",
                    action_type="whatsapp_error",
                    action_description=f"Error enviando WhatsApp a {to_number}: {str(e)}",
                    details={
                        "to": to_number,
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
        """Obtener estado del servicio. sandbox_mode y send_allowed desde ENV VARS."""
        return {
            "configured": self.is_configured(),
            "provider": "Twilio",
            "whatsapp_number": self.whatsapp_number if self.is_configured() else None,
            "sandbox_mode": _whatsapp_sandbox_mode(),
            "send_allowed": _send_allowed(),
            "WHATSAPP_SANDBOX_MODE": os.getenv("WHATSAPP_SANDBOX_MODE"),
            "ENVIRONMENT": os.getenv("ENVIRONMENT", os.getenv("RAILWAY_ENVIRONMENT")),
        }


# Instancia global
whatsapp_service = WhatsAppService()

