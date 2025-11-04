"""
📧 Email Service - SendGrid Integration
Automatiza respuestas por correo electrónico
"""
import os
from typing import Optional, Dict, Any, List
from app.core.config import settings

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
        """Verificar si el servicio está configurado"""
        return self.client is not None
    
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
        if not self.is_configured():
            return {
                "success": False,
                "error": "Email service not configured. Set SENDGRID_API_KEY"
            }
        
        try:
            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(to_email),
                subject=subject,
                html_content=Content(content_type, content)
            )
            
            # Agregar CC y BCC si existen
            if cc:
                for cc_email in cc:
                    message.add_cc(cc_email)
            
            if bcc:
                for bcc_email in bcc:
                    message.add_bcc(bcc_email)
            
            # Enviar
            response = self.client.send(message)
            
            return {
                "success": True,
                "status_code": response.status_code,
                "to": to_email,
                "subject": subject
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
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
            "configured": self.is_configured(),
            "provider": "SendGrid",
            "from_email": self.from_email if self.is_configured() else None,
            "from_name": self.from_name if self.is_configured() else None
        }


# Instancia global
email_service = EmailService()

