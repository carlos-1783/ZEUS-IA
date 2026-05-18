"""
Orquestador TeamFlow: intent → task → ejecución real (CRM, marketing, notificaciones).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.zeus_task import ZeusExecutionResult, ZeusExecutionStepResult, ZeusTaskObject
from services.activity_logger import ActivityLogger
from services.agent_memory_service import load as memory_load, persist_operational_state
from services.email_service import email_service
from services.intent_parser import is_confirmation_message, parse_intent
import services.crm_office_service as crm_svc

logger = logging.getLogger(__name__)

PENDING_TASK_KEY = "pending_zeus_task"
MAX_EMAILS_PER_RUN = 200
AGENT_ZEUS = "ZEUS CORE"


def _company_key(user: User, context: Optional[Dict[str, Any]]) -> str:
    if context and context.get("company_id"):
        return str(context["company_id"])
    return str(user.id)


def _thread_id(context: Optional[Dict[str, Any]]) -> str:
    return str((context or {}).get("thread_id") or "main")


def _get_pending_task(company_id: str, thread_id: str) -> Optional[Dict[str, Any]]:
    mem = memory_load(company_id, AGENT_ZEUS, thread_id)
    artifacts = (mem.get("operational") or {}).get("artifacts") or {}
    pending = artifacts.get(PENDING_TASK_KEY)
    return pending if isinstance(pending, dict) else None


def _set_pending_task(company_id: str, thread_id: str, task: Optional[ZeusTaskObject]) -> None:
    if task is None:
        persist_operational_state(
            company_id,
            AGENT_ZEUS,
            thread_id,
            current_task=None,
            status="idle",
            next_action=None,
            artifacts={},
            blocked=None,
        )
        return
    persist_operational_state(
        company_id,
        AGENT_ZEUS,
        thread_id,
        current_task=task.action,
        status="awaiting_confirmation",
        next_action="Escribe «confirmar» para ejecutar",
        artifacts={PENDING_TASK_KEY: task.model_dump()},
        blocked=None,
    )


async def try_handle_zeus_chat(
    db: Session,
    user: User,
    message: str,
    context: Optional[Dict[str, Any]] = None,
    *,
    force_execute: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Si el mensaje dispara una acción ejecutable, devuelve respuesta estructurada.
    Si no, devuelve None (continuar con LLM).
    """
    company_id = _company_key(user, context)
    thread_id = _thread_id(context)
    ctx = context or {}

    if ctx.get("skip_action_execution"):
        return None

    if is_confirmation_message(message) or force_execute:
        pending = _get_pending_task(company_id, thread_id)
        if pending:
            task = ZeusTaskObject.model_validate(pending)
            if task.intent == "create_campaign_send":
                result = await _execute_create_campaign_send(db, user, task)
                _set_pending_task(company_id, thread_id, None)
                return _to_chat_payload(result)
        if is_confirmation_message(message) and not pending:
            return {
                "handled": True,
                "success": False,
                "message": "No hay ninguna acción pendiente de confirmar. Describe la campaña que quieres lanzar.",
                "executed": False,
            }

    task = parse_intent(message)
    if task.intent == "unknown" or task.confidence < 0.7:
        return None

    if task.intent == "list_customers_summary":
        result = _execute_list_customers(db, user, task)
        return _to_chat_payload(result)

    if task.intent == "create_campaign_send":
        preview = _preview_campaign_send(db, user, task)
        if task.requires_confirmation and not force_execute:
            _set_pending_task(company_id, thread_id, task)
            return {
                "handled": True,
                "success": True,
                "executed": False,
                "needs_confirmation": True,
                "message": preview["message"],
                "execution": preview,
            }
        result = await _execute_create_campaign_send(db, user, task)
        return _to_chat_payload(result)

    return None


def _to_chat_payload(result: ZeusExecutionResult) -> Dict[str, Any]:
    return {
        "handled": True,
        "success": result.success,
        "message": result.message,
        "executed": result.executed,
        "needs_confirmation": result.needs_confirmation,
        "execution": result.model_dump(),
    }


def _preview_campaign_send(db: Session, user: User, task: ZeusTaskObject) -> Dict[str, Any]:
    customers = crm_svc.list_customers(db, user)
    with_email = [c for c in customers if c.email and str(c.email).strip()]
    discount = task.discount_percent
    pct = f"{int(discount)}%" if discount else "especial"
    n = len(with_email)
    if n == 0:
        return {
            "message": (
                "No hay clientes con email en tu CRM. Añade correos en CRM de oficina "
                "o importa un archivo antes de enviar la campaña."
            ),
            "customer_count": 0,
        }
    cap = min(n, MAX_EMAILS_PER_RUN)
    extra = f" (máximo {MAX_EMAILS_PER_RUN} por envío)" if n > MAX_EMAILS_PER_RUN else ""
    return {
        "message": (
            f"Preparado: campaña «{task.campaign_name}» con oferta {pct} para {n} cliente(s) con email. "
            f"Se enviarán {cap} mensaje(s){extra}. "
            f"Responde **confirmar** para ejecutar (no se sobrescriben clientes existentes)."
        ),
        "customer_count": n,
        "will_send": cap,
        "discount_percent": discount,
    }


def _execute_list_customers(db: Session, user: User, task: ZeusTaskObject) -> ZeusExecutionResult:
    customers = crm_svc.list_customers(db, user)
    with_email = sum(1 for c in customers if c.email)
    with_phone = sum(1 for c in customers if c.phone)
    msg = (
        f"Tienes {len(customers)} cliente(s) en CRM: "
        f"{with_email} con email, {with_phone} con teléfono."
    )
    ActivityLogger.log_activity(
        agent_name="ZEUS CORE",
        action_type="crm_customers_summary",
        action_description="Consulta de clientes desde chat",
        details={"total": len(customers), "user_id": user.id},
        user_email=user.email,
        status="completed",
    )
    return ZeusExecutionResult(
        success=True,
        intent=task.intent,
        message=msg,
        executed=True,
        metrics={"total": len(customers), "with_email": with_email},
        steps=[
            ZeusExecutionStepResult(
                agent="crm_agent",
                step="list_customers",
                success=True,
                detail=f"{len(customers)} clientes",
            )
        ],
    )


async def _execute_create_campaign_send(
    db: Session,
    user: User,
    task: ZeusTaskObject,
) -> ZeusExecutionResult:
    steps: List[ZeusExecutionStepResult] = []
    campaign_id = str(uuid.uuid4())
    discount = task.discount_percent
    pct_label = f"{int(discount)}%" if discount else "especial"

    # --- CRM: audiencia ---
    try:
        customers = crm_svc.list_customers(db, user)
        recipients = [
            {"id": c.id, "name": c.name, "email": str(c.email).strip().lower()}
            for c in customers
            if c.email and str(c.email).strip()
        ]
    except Exception as exc:
        logger.exception("crm list_customers")
        return ZeusExecutionResult(
            success=False,
            intent=task.intent,
            message=f"No se pudieron cargar los clientes: {exc}",
            executed=False,
        )

    if not recipients:
        return ZeusExecutionResult(
            success=False,
            intent=task.intent,
            message="No hay clientes con email en el CRM. No se envió ningún mensaje.",
            executed=False,
            metrics={"recipients": 0},
        )

    steps.append(
        ZeusExecutionStepResult(
            agent="crm_agent",
            step="filter_target",
            success=True,
            detail=f"{len(recipients)} destinatarios",
            data={"count": len(recipients)},
        )
    )

    # --- Marketing: campaña en BD (actividad) ---
    subject = f"Oferta {pct_label} — {task.campaign_name or 'Promoción'}"
    body_html = task.message_template or (
        f"<p>Hola,</p><p>Oferta {pct_label} para ti. Contáctanos para más información.</p>"
    )
    try:
        ActivityLogger.log_activity(
            agent_name="PERSEO",
            action_type="campaign_created",
            action_description=f"Campaña CRM: {task.campaign_name}",
            details={
                "campaign_id": campaign_id,
                "discount_percent": discount,
                "target": task.target,
                "subject": subject,
                "user_id": user.id,
            },
            metrics={"recipients_planned": len(recipients)},
            user_email=user.email,
            status="in_progress",
        )
        steps.append(
            ZeusExecutionStepResult(
                agent="marketing_agent",
                step="create_campaign",
                success=True,
                detail=campaign_id,
            )
        )
    except Exception as exc:
        logger.exception("campaign activity log")
        steps.append(
            ZeusExecutionStepResult(
                agent="marketing_agent",
                step="create_campaign",
                success=False,
                detail=str(exc),
            )
        )

    # --- Notificaciones: envío real ---
    to_send = recipients[:MAX_EMAILS_PER_RUN]
    sent = 0
    failed = 0
    if not email_service.is_configured() and not email_service.is_resend_configured():
        return ZeusExecutionResult(
            success=False,
            intent=task.intent,
            message=(
                "Campaña registrada pero el email no está configurado "
                "(SENDGRID_API_KEY o RESEND_API_KEY). Configura el proveedor y vuelve a intentar."
            ),
            executed=False,
            steps=steps,
            metrics={"recipients": len(recipients), "sent": 0},
        )

    for rec in to_send:
        personalized = body_html.replace("Hola,", f"Hola {rec['name']},")
        try:
            out = await email_service.send_email(
                to_email=rec["email"],
                subject=subject,
                content=personalized,
                content_type="text/html",
            )
            if out.get("success"):
                sent += 1
            else:
                failed += 1
        except Exception:
            failed += 1
            logger.exception("send_email to %s", rec["email"])

    steps.append(
        ZeusExecutionStepResult(
            agent="notification_agent",
            step="send_emails",
            success=sent > 0,
            detail=f"enviados={sent} fallidos={failed}",
            data={"sent": sent, "failed": failed},
        )
    )

    # Log actividad CRM + cierre campaña
    company_id = crm_svc.primary_company_id(db, user)
    if company_id is not None:
        try:
            crm_svc.log_activity(
                db,
                company_id=company_id,
                user_id=user.id,
                customer_id=None,
                record_id=None,
                action="campaign_sent",
                summary=f"Campaña {pct_label} enviada a {sent} cliente(s)",
                payload={
                    "campaign_id": campaign_id,
                    "sent": sent,
                    "failed": failed,
                    "discount_percent": discount,
                },
            )
        except Exception:
            logger.exception("crm log_activity campaign_sent")

    try:
        ActivityLogger.log_activity(
            agent_name="PERSEO",
            action_type="campaign_sent",
            action_description=f"Campaña enviada: {sent} emails",
            details={
                "campaign_id": campaign_id,
                "sent": sent,
                "failed": failed,
                "skipped_no_email": len(customers) - len(recipients),
            },
            metrics={"emails_sent": sent, "emails_failed": failed},
            user_email=user.email,
            status="completed" if sent else "failed",
        )
    except Exception:
        logger.exception("campaign_sent activity")

    remaining = len(recipients) - len(to_send)
    extra = f" ({remaining} pendientes por límite de {MAX_EMAILS_PER_RUN}/envío)" if remaining > 0 else ""
    fail_note = f" {failed} fallidos." if failed else ""

    if sent == 0:
        msg = f"No se pudo enviar la campaña a ningún cliente.{fail_note}"
        ok = False
    else:
        msg = (
            f"Oferta {pct_label} creada y enviada a {sent} cliente(s) correctamente"
            f"{extra}.{fail_note}"
        )
        ok = True

    return ZeusExecutionResult(
        success=ok,
        intent=task.intent,
        message=msg,
        executed=True,
        metrics={
            "campaign_id": campaign_id,
            "recipients": len(recipients),
            "sent": sent,
            "failed": failed,
        },
        steps=steps,
    )
