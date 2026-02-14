"""
⚡ ZEUS Automation Readiness Handler
Evalúa madurez para automatización, persiste en BD y notifica al superusuario si READY_FOR_FULL_AUTOMATION.
"""

from __future__ import annotations

import os
import asyncio
import concurrent.futures
from datetime import datetime
from typing import Dict, Any

from app.models.agent_activity import AgentActivity
from app.models.user import User
from app.db.session import SessionLocal
from services.automation_readiness_service import (
    evaluate_and_persist,
    STATUS_READY_FOR_FULL_AUTOMATION,
)
from services.whatsapp_service import whatsapp_service
from services.activity_logger import ActivityLogger


def handle_automation_readiness_evaluate(activity: AgentActivity) -> Dict[str, Any]:
    """
    Handler para automation_readiness_evaluate: calcula score, persiste en BD y notifica por WhatsApp si READY.
    """
    payload = activity.details if isinstance(activity.details, dict) else {}
    user_email = (activity.user_email or "").strip()

    session = SessionLocal()
    try:
        # Resolver company_id (user_id)
        company_id = payload.get("company_id")
        if company_id is None and user_email:
            user = session.query(User).filter(User.email == user_email).first()
            if user:
                company_id = user.id
        if company_id is None:
            # Fallback: superusuario como company por defecto
            superuser = session.query(User).filter(User.is_superuser == True).first()
            company_id = superuser.id if superuser else 1

        # Datos de evaluación
        eval_data = {
            "leads_last_30_days": payload.get("leads_last_30_days", 0),
            "avg_response_time_hours": payload.get("avg_response_time_hours", 24),
            "active_channels": payload.get("active_channels", 0),
            "monthly_revenue_estimate": payload.get("monthly_revenue_estimate", 0),
            "has_defined_offer": payload.get("has_defined_offer", False),
            "has_sales_process": payload.get("has_sales_process", False),
            "team_size": payload.get("team_size", 0),
        }

        record = evaluate_and_persist(session, int(company_id), eval_data)

        whatsapp_sent = False
        whatsapp_message_id = None
        whatsapp_error = None

        # Si status READY_FOR_FULL_AUTOMATION → notificar por WhatsApp al superusuario
        if record.status == STATUS_READY_FOR_FULL_AUTOMATION:
            superuser_phone = (
                os.getenv("SUPERUSER_PHONE")
                or payload.get("superuser_phone")
                or os.getenv("ZEUS_ADMIN_PHONE")
            )
            if superuser_phone and whatsapp_service.is_configured():
                try:
                    message = (
                        f"⚡ ZEUS AUTOMATION READINESS\n\n"
                        f"Estado: {record.status}\n"
                        f"Score: {record.score}/100\n"
                        f"Empresa/Usuario: {company_id}\n\n"
                        f"La empresa está lista para automatización completa."
                    )

                    def _run_async_send():
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            return new_loop.run_until_complete(
                                whatsapp_service.send_message(superuser_phone, message)
                            )
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

        # Registrar AgentActivity automation_readiness_evaluated
        try:
            ActivityLogger.log_activity(
                agent_name="ZEUS",
                action_type="automation_readiness_evaluated",
                action_description=f"Evaluación automation readiness: score={record.score} status={record.status}",
                details={
                    "company_id": company_id,
                    "score": record.score,
                    "status": record.status,
                    "record_id": record.id,
                    "whatsapp_sent": whatsapp_sent,
                    "executed_handler": "AUTOMATION_READINESS_HANDLER",
                },
                metrics={
                    "score": record.score,
                    "status": record.status,
                    "executed_handler": "AUTOMATION_READINESS_HANDLER",
                },
                user_email=user_email or None,
                status="completed",
                priority="high",
            )
        except Exception:
            pass

        return {
            "status": "executed_internal",
            "details_update": {
                **payload,
                "company_id": company_id,
                "score": record.score,
                "status": record.status,
                "record_id": record.id,
                "evaluated_at": record.evaluated_at.isoformat() if record.evaluated_at else None,
                "executed_handler": "AUTOMATION_READINESS_HANDLER",
                "whatsapp_sent": whatsapp_sent,
                "whatsapp_message_id": whatsapp_message_id,
                "whatsapp_error": whatsapp_error,
                "timestamp": datetime.utcnow().isoformat(),
            },
            "metrics_update": {
                "executed_handler": "AUTOMATION_READINESS_HANDLER",
                "score": record.score,
                "status": record.status,
            },
            "notes": f"Automation readiness evaluado. Score={record.score} status={record.status}. WhatsApp={'enviado' if whatsapp_sent else 'no enviado'}.",
            "executed_handler": "AUTOMATION_READINESS_HANDLER",
        }
    finally:
        session.close()
