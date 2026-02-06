"""
⚡ ZEUS Launch Handler
Ejecuta acción real al arranque: crea AgentActivity y envía WhatsApp de confirmación al superusuario.
"""

from __future__ import annotations

import os
import asyncio
from datetime import datetime
from typing import Dict, Any

from app.models.agent_activity import AgentActivity
from services.whatsapp_service import whatsapp_service
from services.activity_logger import ActivityLogger


def handle_zeus_launch_started(activity: AgentActivity) -> Dict[str, Any]:
    """
    Handler para zeus_launch_started: persiste en BD y envía WhatsApp al superusuario.
    """
    payload = activity.details if isinstance(activity.details, dict) else {}
    environment = os.getenv("ENVIRONMENT", os.getenv("RAILWAY_ENVIRONMENT", "production"))
    
    # Obtener teléfono del superusuario desde env var o usar el del payload
    superuser_phone = (
        os.getenv("SUPERUSER_PHONE")
        or payload.get("superuser_phone")
        or os.getenv("ZEUS_ADMIN_PHONE")
    )
    
    whatsapp_sent = False
    whatsapp_message_id = None
    whatsapp_error = None
    
    # Enviar WhatsApp al superusuario si está configurado (llamada async desde handler sync)
    if superuser_phone and whatsapp_service.is_configured():
        try:
            message = "⚡ ZEUS ACTIVADO\n\nLanzamiento operativo iniciado correctamente.\n\nSistema: ZEUS-IA\nEntorno: " + environment
            # Ejecutar async desde función sync usando ThreadPoolExecutor para evitar conflictos con loop existente
            import concurrent.futures
            
            def _run_async_send():
                """Ejecuta send_message en un nuevo loop dentro de un thread separado"""
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(whatsapp_service.send_message(superuser_phone, message))
                finally:
                    new_loop.close()
            
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(_run_async_send)
                result = future.result(timeout=15)
            
            whatsapp_sent = result.get("success", False)
            whatsapp_message_id = result.get("message_sid")
            if not whatsapp_sent:
                whatsapp_error = result.get("error")
        except Exception as e:
            whatsapp_error = str(e)
    
    # Registrar WhatsApp enviado si fue exitoso
    if whatsapp_sent and whatsapp_message_id:
        try:
            ActivityLogger.log_activity(
                agent_name="ZEUS",
                action_type="whatsapp_sent",
                action_description=f"WhatsApp de confirmación enviado a superusuario: {superuser_phone}",
                details={
                    "to": superuser_phone,
                    "message": "ZEUS ACTIVADO. Lanzamiento operativo iniciado correctamente.",
                    "message_sid": whatsapp_message_id,
                    "trigger": "zeus_launch_started",
                },
                metrics={"message_sid": whatsapp_message_id},
                status="completed",
                priority="high"
            )
        except Exception:
            pass
    
    return {
        "status": "executed_internal",
        "details_update": {
            **payload,
            "phase": "launch_started",
            "environment": environment,
            "executed_handler": "ZEUS_LAUNCH_HANDLER",
            "whatsapp_sent": whatsapp_sent,
            "whatsapp_message_id": whatsapp_message_id,
            "whatsapp_error": whatsapp_error,
            "superuser_phone": superuser_phone if superuser_phone else None,
            "timestamp": datetime.utcnow().isoformat(),
        },
        "metrics_update": {
            "executed_handler": "ZEUS_LAUNCH_HANDLER",
            "whatsapp_sent": whatsapp_sent,
        },
        "notes": f"ZEUS launch started. WhatsApp {'enviado' if whatsapp_sent else 'no enviado' if not superuser_phone else 'falló'}.",
        "executed_handler": "ZEUS_LAUNCH_HANDLER",
    }
