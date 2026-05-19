"""Ejecutores por módulo (handlers de acciones ZEUS)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.agent_activity import AgentActivity
from app.models.erp import TPVSale
from app.models.user import User
from app.schemas.zeus_action import ZeusAction
from app.schemas.zeus_task import ZeusExecutionResult, ZeusExecutionStepResult, ZeusTaskObject
from services.activity_logger import ActivityLogger
from services.email_service import email_service
import services.crm_office_service as crm_svc

logger = logging.getLogger(__name__)

MAX_EMAILS_PER_RUN = 200

AGENT_CRM = "crm_agent"
AGENT_PERSEO = "perseo_agent"
AGENT_TPV = "tpv_agent"
AGENT_HR = "hr_agent"
AGENT_ANALYTICS = "analytics_agent"
AGENT_ACTIVITY = "activity_log"


def _sales_since(action: ZeusAction) -> datetime:
    if action.payload.get("period") == "today":
        now = datetime.now(timezone.utc)
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    days = int(action.payload.get("days") or 7)
    return datetime.now(timezone.utc) - timedelta(days=days)


def _context_customers(action: ZeusAction) -> Dict[str, Any]:
    gc = action.payload.get("_zeus_context") or {}
    return gc.get("active_customers") or {}


def log_central(
    *,
    user: User,
    action_type: str,
    description: str,
    details: Optional[Dict[str, Any]] = None,
    metrics: Optional[Dict[str, Any]] = None,
    agent_name: str = "ZEUS CORE",
    status: str = "completed",
) -> None:
    try:
        ActivityLogger.log_activity(
            agent_name=agent_name,
            action_type=action_type,
            action_description=description[:500],
            details={**(details or {}), "user_id": user.id, "orchestrator": True},
            metrics=metrics,
            user_email=user.email,
            status=status,
            priority="normal",
            visible_to_client=True,
        )
    except Exception:
        logger.exception("log_central failed action_type=%s", action_type)


def execute_list_customers(db: Session, user: User, action: ZeusAction) -> ZeusExecutionResult:
    customers = crm_svc.list_customers(db, user)
    with_email = sum(1 for c in customers if c.email)
    with_phone = sum(1 for c in customers if c.phone)
    msg = (
        f"Tienes {len(customers)} cliente(s) en CRM: "
        f"{with_email} con email, {with_phone} con teléfono."
    )
    log_central(
        user=user,
        action_type="crm_customers_summary",
        description="Consulta de clientes desde orquestador",
        details={"total": len(customers), "company_id": action.company_id},
        metrics={"total": len(customers), "with_email": with_email},
    )
    return ZeusExecutionResult(
        success=True,
        intent="list_customers_summary",
        message=msg,
        executed=True,
        metrics={"total": len(customers), "with_email": with_email, "with_phone": with_phone},
        steps=[
            ZeusExecutionStepResult(
                agent=AGENT_CRM,
                step="list_customers",
                success=True,
                detail=str(len(customers)),
            ),
            ZeusExecutionStepResult(agent=AGENT_ACTIVITY, step="log", success=True, detail="ok"),
        ],
    )


def preview_send_campaign(db: Session, user: User, action: ZeusAction) -> Dict[str, Any]:
    task = _action_to_task(action)
    customers = crm_svc.list_customers(db, user)
    with_email = [c for c in customers if c.email and str(c.email).strip()]
    discount = task.discount_percent
    pct = f"{int(discount)}%" if discount else "especial"
    n = len(with_email)
    if n == 0:
        return {
            "message": (
                "No hay clientes con email en tu CRM. Añade correos o importa un archivo antes de enviar."
            ),
            "customer_count": 0,
        }
    cap = min(n, MAX_EMAILS_PER_RUN)
    extra = f" (máximo {MAX_EMAILS_PER_RUN} por envío)" if n > MAX_EMAILS_PER_RUN else ""
    name = task.campaign_name or "Campaña"
    return {
        "message": (
            f"Preparado: «{name}» con oferta {pct} para {n} cliente(s) con email. "
            f"Se enviarán {cap} mensaje(s){extra}. "
            f"Responde «confirmar» para ejecutar."
        ),
        "customer_count": n,
        "will_send": cap,
        "discount_percent": discount,
    }


async def execute_send_campaign(db: Session, user: User, action: ZeusAction) -> ZeusExecutionResult:
    task = _action_to_task(action)
    steps: List[ZeusExecutionStepResult] = []
    campaign_id = str(uuid.uuid4())
    discount = task.discount_percent
    pct_label = f"{int(discount)}%" if discount else "especial"

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
            intent="create_campaign_send",
            message=f"No se pudieron cargar los clientes: {exc}",
            executed=False,
            steps=steps,
        )

    if not recipients:
        return ZeusExecutionResult(
            success=False,
            intent="create_campaign_send",
            message="No hay clientes con email en el CRM. No se envió ningún mensaje.",
            executed=False,
            metrics={"recipients": 0},
            steps=steps,
        )

    steps.append(
        ZeusExecutionStepResult(
            agent=AGENT_CRM,
            step="filter_target",
            success=True,
            detail=f"{len(recipients)} destinatarios",
        )
    )

    subject = f"Oferta {pct_label} — {task.campaign_name or 'Promoción'}"
    body_html = task.message_template or (
        f"<p>Hola,</p><p>Oferta {pct_label} para ti. Contáctanos para más información.</p>"
    )

    log_central(
        user=user,
        action_type="campaign_created",
        description=f"Campaña: {task.campaign_name}",
        details={"campaign_id": campaign_id, "discount_percent": discount},
        metrics={"recipients_planned": len(recipients)},
        agent_name="PERSEO",
        status="in_progress",
    )
    steps.append(
        ZeusExecutionStepResult(
            agent=AGENT_PERSEO, step="campaign_created", success=True, detail=campaign_id
        )
    )

    to_send = recipients[:MAX_EMAILS_PER_RUN]
    sent = failed = 0
    if not email_service.is_configured() and not email_service.is_resend_configured():
        return ZeusExecutionResult(
            success=False,
            intent="create_campaign_send",
            message="Email no configurado (SENDGRID_API_KEY o RESEND_API_KEY).",
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
            logger.exception("send_email %s", rec["email"])

    steps.append(
        ZeusExecutionStepResult(
            agent=AGENT_PERSEO,
            step="message_sent",
            success=sent > 0,
            detail=f"enviados={sent} fallidos={failed}",
            data={"sent": sent, "failed": failed},
        )
    )

    cid = action.company_id or crm_svc.primary_company_id(db, user)
    if cid is not None:
        try:
            crm_svc.log_activity(
                db,
                company_id=cid,
                user_id=user.id,
                customer_id=None,
                record_id=None,
                action="campaign_sent",
                summary=f"Campaña {pct_label} enviada a {sent} cliente(s)",
                payload={"campaign_id": campaign_id, "sent": sent, "failed": failed},
            )
        except Exception:
            logger.exception("crm campaign_sent log")

    if sent > 0:
        log_central(
            user=user,
            action_type="message_sent",
            description=f"Mensajes de campaña enviados: {sent}",
            details={"campaign_id": campaign_id, "sent": sent, "failed": failed},
            metrics={"emails_sent": sent},
            agent_name="PERSEO",
        )
    log_central(
        user=user,
        action_type="campaign_sent",
        description=f"Campaña enviada: {sent} emails",
        details={"campaign_id": campaign_id, "sent": sent, "failed": failed},
        metrics={"emails_sent": sent, "emails_failed": failed},
        agent_name="PERSEO",
        status="completed" if sent else "failed",
    )
    steps.append(
        ZeusExecutionStepResult(agent=AGENT_ACTIVITY, step="campaign_sent", success=sent > 0, detail=str(sent))
    )

    remaining = len(recipients) - len(to_send)
    extra = f" ({remaining} pendientes por límite de {MAX_EMAILS_PER_RUN})" if remaining > 0 else ""
    fail_note = f" {failed} fallidos." if failed else ""
    if sent == 0:
        msg = f"No se pudo enviar la campaña.{fail_note}"
        ok = False
    else:
        msg = f"Se han enviado {sent} mensaje(s) correctamente{extra}.{fail_note}"
        ok = True

    return ZeusExecutionResult(
        success=ok,
        intent="create_campaign_send",
        message=msg,
        executed=True,
        metrics={"campaign_id": campaign_id, "recipients": len(recipients), "sent": sent, "failed": failed},
        steps=steps,
    )


def execute_analytics_summary(db: Session, user: User, action: ZeusAction) -> ZeusExecutionResult:
    days = int(action.payload.get("days") or 30)
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    q = db.query(AgentActivity).filter(
        AgentActivity.created_at >= start_date,
        AgentActivity.created_at <= end_date,
    )
    if not getattr(user, "is_superuser", False):
        q = q.filter(AgentActivity.user_email == user.email)
    activities = q.all()
    total = len(activities)
    completed = sum(1 for a in activities if a.status == "completed")
    rate = (completed / total * 100) if total else 0.0
    msg = (
        f"Resumen últimos {days} días: {total} actividades registradas, "
        f"{completed} completadas ({rate:.0f}% éxito)."
    )
    log_central(
        user=user,
        action_type="analytics_summary",
        description="Resumen analytics desde chat",
        details={"days": days, "total": total},
        metrics={"total_interactions": total, "success_rate": rate},
        agent_name="ZEUS CORE",
    )
    return ZeusExecutionResult(
        success=True,
        intent="analytics_summary",
        message=msg,
        executed=True,
        metrics={"total": total, "completed": completed, "days": days},
        steps=[
            ZeusExecutionStepResult(
                agent=AGENT_ANALYTICS, step="summary", success=True, detail=str(total)
            ),
            ZeusExecutionStepResult(agent=AGENT_ACTIVITY, step="log", success=True, detail="ok"),
        ],
    )


def execute_tpv_sales_summary(db: Session, user: User, action: ZeusAction) -> ZeusExecutionResult:
    days = int(action.payload.get("days") or 7)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    q = db.query(
        func.count(TPVSale.id),
        func.coalesce(func.sum(TPVSale.total), 0),
    ).filter(TPVSale.sale_date >= since)
    if action.company_id is not None:
        q = q.filter(TPVSale.company_id == action.company_id)
    else:
        q = q.filter(TPVSale.user_id == user.id)
    count, total_sum = q.one()
    total_eur = float(total_sum or 0)
    msg = f"TPV últimos {days} días: {count} venta(s), total {total_eur:,.2f} €."
    log_central(
        user=user,
        action_type="sale_summary",
        description="Resumen ventas TPV desde orquestador",
        details={"days": days, "count": count, "total": total_eur},
        metrics={"sales_count": count, "sales_total": total_eur},
        agent_name="RAFAEL",
    )
    return ZeusExecutionResult(
        success=True,
        intent="tpv_sales_summary",
        message=msg,
        executed=True,
        metrics={"sales_count": count, "sales_total": total_eur, "days": days},
        steps=[
            ZeusExecutionStepResult(agent="tpv", step="sales_summary", success=True, detail=str(count)),
            ZeusExecutionStepResult(agent="activity_log", step="log", success=True, detail="ok"),
        ],
    )


def execute_shift_status(db: Session, user: User, action: ZeusAction) -> ZeusExecutionResult:
    from app.models.employee_work_session import EmployeeWorkSession

    ws = (
        db.query(EmployeeWorkSession)
        .filter(
            EmployeeWorkSession.user_id == user.id,
            EmployeeWorkSession.status == "active",
        )
        .order_by(EmployeeWorkSession.id.desc())
        .first()
    )
    if not ws:
        msg = "No tienes un turno/jornada activa en control horario."
        log_central(
            user=user,
            action_type="shift_status",
            description="Consulta turno: sin sesión activa",
            details={"active": False},
            agent_name="AFRODITA",
        )
        return ZeusExecutionResult(
            success=True,
            intent="shift_status",
            message=msg,
            executed=True,
            metrics={"active": False},
            steps=[
                ZeusExecutionStepResult(
                    agent=AGENT_HR, step="status", success=True, detail="inactive"
                ),
            ],
        )
    started = ws.opened_at.isoformat() if ws.opened_at else "—"
    msg = f"Turno activo (código empleado {ws.employee_code or '—'}), iniciado {started}."
    log_central(
        user=user,
        action_type="shift_started",
        description="Consulta turno: activo",
        details={"session_id": ws.id, "employee_code": ws.employee_code},
        agent_name="AFRODITA",
    )
    return ZeusExecutionResult(
        success=True,
        intent="shift_status",
        message=msg,
        executed=True,
        metrics={"active": True, "session_id": ws.id},
        steps=[
            ZeusExecutionStepResult(agent=AGENT_HR, step="status", success=True, detail="active"),
            ZeusExecutionStepResult(agent=AGENT_ACTIVITY, step="log", success=True, detail="ok"),
        ],
    )


def _action_to_task(action: ZeusAction) -> ZeusTaskObject:
    return ZeusTaskObject(
        intent="create_campaign_send",
        action="create_campaign",
        discount_percent=action.payload.get("discount_percent"),
        target=action.payload.get("target") or "all_customers",
        campaign_name=action.payload.get("campaign_name"),
        message_template=action.payload.get("message_template"),
        requires_confirmation=action.requires_confirmation,
        raw_message=action.raw_message,
        confidence=action.confidence,
        metadata=action.payload,
    )
