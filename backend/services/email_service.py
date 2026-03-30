"""
📧 Email Service - SendGrid + Resend (fallback)
Automatiza respuestas por correo electrónico
"""
import asyncio
import logging
import os
from typing import Optional, Dict, Any, List

import requests

logger = logging.getLogger(__name__)

try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, Email, To, Content  # pyright: ignore[reportMissingImports]  # pyright: ignore[reportMissingImports]
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False
    SendGridAPIClient = None
    Mail = Email = To = Content = None
 
class EmailService:
    """Servicio para automatización de email vía SendGrid"""
    
    def __init__(self):
        self.api_key = os.getenv("SENDGRID_API_KEY")
        self.from_email = os.getenv("SENDGRID_FROM_EMAIL", "noreply@zeus-ia.com")
        self.from_name = os.getenv("SENDGRID_FROM_NAME", "ZEUS-IA")
        self.resend_api_key = os.getenv("RESEND_API_KEY")
        # Resend / genérico: EMAIL_FROM o RESEND_FROM_EMAIL (dominio verificado en Resend)
        self.resend_from = os.getenv("EMAIL_FROM") or os.getenv("RESEND_FROM_EMAIL")
        
        self.client = None
        if not SENDGRID_AVAILABLE:
            print("⚠️ Email Service: SendGrid library not installed (pip install sendgrid)")
        elif self.api_key:
            try:
                self.client = SendGridAPIClient(self.api_key)
                print("✅ Email Service inicializado correctamente")
            except Exception as e:
                print(f"⚠️ Email Service no pudo inicializar: {e}")
        else:
            print("⚠️ Email Service: SENDGRID_API_KEY no configurada")
    
    def is_configured(self) -> bool:
        """SendGrid listo para enviar."""
        return self.client is not None

    def is_resend_configured(self) -> bool:
        return bool(self.resend_api_key and self.resend_from)

    def _send_via_resend_sync(
        self,
        to_email: str,
        subject: str,
        content: str,
        content_type: str = "text/html",
    ) -> Dict[str, Any]:
        """POST síncrono a la API de Resend (se ejecuta en thread pool desde async)."""
        payload: Dict[str, Any] = {
            "from": self.resend_from,
            "to": [to_email],
            "subject": subject,
        }
        if content_type == "text/html":
            payload["html"] = content
        else:
            payload["text"] = content
        resp = requests.post(
            "https://api.resend.com/emails",
            json=payload,
            headers={
                "Authorization": f"Bearer {self.resend_api_key}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        if resp.status_code in (200, 201):
            data = resp.json() if resp.text else {}
            return {
                "success": True,
                "status_code": resp.status_code,
                "to": to_email,
                "subject": subject,
                "message_id": data.get("id"),
                "provider": "resend",
            }
        return {
            "success": False,
            "error": f"Resend HTTP {resp.status_code}: {resp.text[:500]}",
            "provider": "resend",
        }
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        content: str,
        content_type: str = "text/html",
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Enviar email
        
        Args:
            to_email: Destinatario
            subject: Asunto
            content: Contenido (HTML o texto plano)
            content_type: "text/html" o "text/plain"
            cc: Lista de CC (opcional)
            bcc: Lista de BCC (opcional)
            
        Returns:
            Dict con status y message_id
        """
        if not self.is_configured() and not self.is_resend_configured():
            return {
                "success": False,
                "error": "Email no configurado: define SENDGRID_API_KEY o RESEND_API_KEY + EMAIL_FROM",
            }

        if self.is_configured():
            try:
                message = Mail(
                    from_email=Email(self.from_email, self.from_name),
                    to_emails=To(to_email),
                    subject=subject,
                    html_content=Content(content_type, content),
                )

                if cc:
                    for cc_email in cc:
                        message.add_cc(cc_email)

                if bcc:
                    for bcc_email in bcc:
                        message.add_bcc(bcc_email)

                response = self.client.send(message)

                message_id = None
                if hasattr(response, "headers") and response.headers:
                    message_id = response.headers.get("X-Message-Id") or response.headers.get("x-message-id")

                result = {
                    "success": True,
                    "status_code": response.status_code,
                    "to": to_email,
                    "subject": subject,
                    "message_id": message_id,
                    "provider": "sendgrid",
                }

                try:
                    from services.activity_logger import ActivityLogger
                    from datetime import datetime

                    ActivityLogger.log_activity(
                        agent_name="ZEUS",
                        action_type="email_sent",
                        action_description=f"Email enviado a {to_email}: {subject}",
                        details={
                            "to": to_email,
                            "subject": subject,
                            "provider": "sendgrid",
                            "status_code": response.status_code,
                            "content_type": content_type,
                            "message_id": message_id,
                            "timestamp": datetime.utcnow().isoformat(),
                            "executed_handler": "SENDGRID_HANDLER",
                        },
                        metrics={
                            "status_code": response.status_code,
                            "executed_handler": "SENDGRID_HANDLER",
                        },
                        status="completed",
                        priority="normal",
                    )
                except Exception as log_error:
                    print(f"[EMAIL] Error registrando actividad: {log_error}")

                return result

            except Exception as e:
                logger.warning("[EMAIL] SendGrid falló, probando Resend si está configurado: %s", e)
                try:
                    from services.activity_logger import ActivityLogger

                    ActivityLogger.log_activity(
                        agent_name="ZEUS",
                        action_type="email_error",
                        action_description=f"Error enviando email a {to_email}: {str(e)}",
                        details={
                            "to": to_email,
                            "subject": subject,
                            "error": str(e),
                            "provider": "sendgrid",
                        },
                        status="failed",
                        priority="high",
                    )
                except Exception:
                    pass

        # Resend: sin SendGrid, o SendGrid falló
        if self.is_resend_configured():
            try:
                result = await asyncio.to_thread(
                    self._send_via_resend_sync,
                    to_email,
                    subject,
                    content,
                    content_type,
                )
                if result.get("success"):
                    return result
                logger.warning("[EMAIL] Resend: %s", result.get("error"))
            except Exception as e:
                logger.warning("[EMAIL] Resend exception: %s", e, exc_info=True)

        return {
            "success": False,
            "error": "No se pudo enviar el email (SendGrid/Resend)",
        }
    
    async def process_incoming_email(
        self,
        from_email: str,
        subject: str,
        body: str,
        agent_name: str = "ZEUS CORE"
    ) -> Dict[str, Any]:
        """
        Procesar email entrante y responder automáticamente
        
        Args:
            from_email: Email del remitente
            subject: Asunto del email
            body: Cuerpo del mensaje
            agent_name: Agente que debe responder
            
        Returns:
            Dict con respuesta del agente
        """
        try:
            # Importar agentes y logger
            from agents.zeus_core import ZeusCore
            from agents.perseo import Perseo
            from agents.rafael import Rafael
            from services.activity_logger import activity_logger
            
            # Mapeo de agentes
            agents_map = {
                "ZEUS CORE": ZeusCore(),
                "PERSEO": Perseo(),
                "RAFAEL": Rafael()
            }
            
            agent = agents_map.get(agent_name, agents_map["ZEUS CORE"])
            
            # Procesar solicitud
            context = {
                "user_message": body,
                "channel": "email",
                "from_email": from_email,
                "subject": subject,
                "priority": "normal"
            }
            
            result = agent.process_request(context)
            
            # Preparar respuesta
            if result.get("success"):
                response_text = result.get("content", result.get("response", "Mensaje procesado"))
                
                # Formatear respuesta en HTML
                html_response = f"""
                <html>
                <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <div style="background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%); padding: 20px; text-align: center;">
                        <h1 style="color: white; margin: 0;">⚡ ZEUS-IA</h1>
                        <p style="color: white; margin: 5px 0;">Respuesta automática de {agent_name}</p>
                    </div>
                    <div style="padding: 30px; background: #f9fafb;">
                        <p style="color: #1f2937;">{response_text.replace(chr(10), '<br>')}</p>
                    </div>
                    <div style="padding: 20px; text-align: center; background: #e5e7eb; font-size: 12px; color: #6b7280;">
                        <p>Este mensaje fue generado automáticamente por ZEUS-IA</p>
                        <p>Si necesitas asistencia personalizada, responde a este email.</p>
                    </div>
                </body>
                </html>
                """
                
                # Enviar respuesta
                send_result = await self.send_email(
                    to_email=from_email,
                    subject=f"Re: {subject}",
                    content=html_response,
                    content_type="text/html"
                )
                
                # ✅ REGISTRAR ACTIVIDAD
                activity_logger.log_activity(
                    agent_name=agent_name,
                    action_type="email_response",
                    action_description=f"Respondido email de {from_email}",
                    details={
                        "from": from_email,
                        "subject": subject,
                        "message": body[:100],  # Primeros 100 caracteres
                        "response": response_text[:100],
                        "channel": "email"
                    },
                    metrics={
                        "response_time": "instant",
                        "email_sent": send_result.get("success", False)
                    },
                    status="completed",
                    priority="normal"
                )
                
                return {
                    "success": True,
                    "agent": agent_name,
                    "response": response_text,
                    "email_status": send_result
                }
            else:
                error_msg = "Lo sentimos, no pudimos procesar tu mensaje en este momento."
                await self.send_email(
                    to_email=from_email,
                    subject=f"Re: {subject}",
                    content=error_msg
                )
                
                # ✅ REGISTRAR ERROR
                activity_logger.log_activity(
                    agent_name=agent_name,
                    action_type="email_error",
                    action_description=f"Error procesando email de {from_email}",
                    details={
                        "from": from_email,
                        "subject": subject,
                        "error": result.get("error", "Unknown")
                    },
                    status="failed",
                    priority="normal"
                )
                
                return {
                    "success": False,
                    "error": result.get("error", "Unknown error")
                }
                
        except Exception as e:
            # ✅ REGISTRAR EXCEPCIÓN
            from services.activity_logger import activity_logger
            activity_logger.log_activity(
                agent_name=agent_name,
                action_type="email_exception",
                action_description=f"Excepción procesando email",
                details={
                    "from": from_email,
                    "subject": subject,
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
        """Obtener estado del servicio"""
        return {
            "configured": self.is_configured() or self.is_resend_configured(),
            "sendgrid": self.is_configured(),
            "resend": self.is_resend_configured(),
            "from_email": self.from_email if self.is_configured() else (self.resend_from if self.is_resend_configured() else None),
            "from_name": self.from_name if self.is_configured() else None,
        }


# Instancia global
email_service = EmailService()

