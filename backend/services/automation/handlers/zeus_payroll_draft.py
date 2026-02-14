"""
⚡ ZEUS Payroll Draft Handler
Genera borradores de nómina, PDF con BORRADOR y disclaimer, envía al gestor laboral.
SIN presentación a Seguridad Social. SIN pagos automáticos.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, Any

from app.models.agent_activity import AgentActivity
from app.models.user import User
from app.db.session import SessionLocal
from services.payroll_assistant_service import (
    generate_and_persist,
    send_to_labor_advisor,
)
from services.activity_logger import ActivityLogger


def handle_payroll_draft_generate(activity: AgentActivity) -> Dict[str, Any]:
    """
    Handler para payroll_draft_generate: calcula nómina, genera PDF BORRADOR, envía al gestor laboral.
    NO presenta a Seguridad Social. NO ejecuta pagos.
    """
    payload = activity.details if isinstance(activity.details, dict) else {}
    user_email = (activity.user_email or "").strip()

    session = SessionLocal()
    try:
        company_id = payload.get("company_id")
        employee_id = payload.get("employee_id")
        gross_salary = float(payload.get("gross_salary", 0) or 0)
        month = str(payload.get("month", datetime.utcnow().strftime("%B")))
        year = int(payload.get("year", datetime.utcnow().year))

        if gross_salary <= 0:
            return {
                "status": "failed",
                "details_update": {**payload, "error": "gross_salary must be > 0"},
                "notes": "Salario bruto inválido.",
                "executed_handler": "PAYROLL_DRAFT_HANDLER",
            }

        # Resolver company_id y employee si faltan
        if not company_id or not employee_id:
            user = session.query(User).filter(User.email == user_email).first()
            if not user:
                superuser = session.query(User).filter(User.is_superuser == True).first()
                user = superuser
            if user:
                company_id = company_id or user.id
                employee_id = employee_id or user.id

        if not company_id or not employee_id:
            return {
                "status": "failed",
                "details_update": {**payload, "error": "company_id and employee_id required"},
                "notes": "Faltan company_id y employee_id.",
                "executed_handler": "PAYROLL_DRAFT_HANDLER",
            }

        company = session.query(User).filter(User.id == company_id).first()
        employee = session.query(User).filter(User.id == employee_id).first()
        company_name = (company.company_name or company.full_name or company.email) if company else ""
        employee_name = (employee.full_name or employee.email) if employee else ""

        record, pdf_path = generate_and_persist(
            db=session,
            company_id=int(company_id),
            employee_id=int(employee_id),
            gross_salary=gross_salary,
            month=month,
            year=year,
            company_name=company_name,
            employee_name=employee_name,
        )

        # Obtener email gestor laboral (email_gestor_laboral o email_gestor_fiscal como fallback)
        advisor_email = None
        if company:
            advisor_email = getattr(company, "email_gestor_laboral", None) or company.email_gestor_fiscal
        advisor_email = advisor_email or payload.get("email_gestor_laboral")

        email_sent = False
        email_error = None
        if advisor_email:
            subject = f"[BORRADOR] Nómina {month}/{year} - {employee_name or employee_id}"
            body = (
                f"<p>Se adjunta borrador de nómina para revisión.</p>"
                f"<p><strong>Empresa:</strong> {company_name}</p>"
                f"<p><strong>Empleado:</strong> {employee_name}</p>"
                f"<p><strong>Período:</strong> {month}/{year}</p>"
                f"<p><strong>Bruto:</strong> {record.gross_salary:.2f} € | "
                f"<strong>Neto estimado:</strong> {record.net_salary_estimated:.2f} €</p>"
                f"<p><em>Documento BORRADOR. Requiere validación por asesor laboral.</em></p>"
            )
            email_result = send_to_labor_advisor(
                to_email=advisor_email,
                subject=subject,
                body=body,
                pdf_path=pdf_path,
            )
            email_sent = email_result.get("success", False)
            if not email_sent:
                email_error = email_result.get("error")

        # Registrar AgentActivity payroll_draft_generated
        ActivityLogger.log_activity(
            agent_name="ZEUS",
            action_type="payroll_draft_generated",
            action_description=f"Borrador nómina generado: {employee_name or employee_id} {month}/{year}",
            details={
                "company_id": company_id,
                "employee_id": employee_id,
                "record_id": record.id,
                "gross_salary": record.gross_salary,
                "net_salary_estimated": record.net_salary_estimated,
                "pdf_path": pdf_path,
                "email_sent": email_sent,
                "advisor_email": advisor_email,
                "executed_handler": "PAYROLL_DRAFT_HANDLER",
            },
            metrics={"record_id": record.id, "executed_handler": "PAYROLL_DRAFT_HANDLER"},
            user_email=user_email or None,
            status="completed",
            priority="high",
        )

        return {
            "status": "executed_internal",
            "details_update": {
                **payload,
                "record_id": record.id,
                "company_id": company_id,
                "employee_id": employee_id,
                "gross_salary": record.gross_salary,
                "net_salary_estimated": record.net_salary_estimated,
                "pdf_path": pdf_path,
                "email_sent": email_sent,
                "email_error": email_error,
                "advisor_email": advisor_email,
                "executed_handler": "PAYROLL_DRAFT_HANDLER",
                "timestamp": datetime.utcnow().isoformat(),
            },
            "metrics_update": {
                "executed_handler": "PAYROLL_DRAFT_HANDLER",
                "record_id": record.id,
            },
            "notes": f"Borrador nómina generado. Email {'enviado' if email_sent else 'no enviado'}.",
            "executed_handler": "PAYROLL_DRAFT_HANDLER",
        }
    finally:
        session.close()
