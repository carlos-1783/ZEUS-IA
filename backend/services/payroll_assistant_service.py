"""
📋 Payroll Assistant Service
Genera borradores de nómina - SIN presentación a Seguridad Social, SIN pagos automáticos.
Toda nómina es BORRADOR y requiere validación por asesor laboral.
"""
from __future__ import annotations

import os
import base64
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.payroll_draft import PayrollDraft
from app.models.user import User

logger = logging.getLogger(__name__)

LEGAL_DISCLAIMER = (
    "Documento generado automáticamente por ZEUS-IA. "
    "Cálculo estimado. Requiere validación por asesor laboral colegiado "
    "antes de su emisión oficial o presentación ante organismos públicos."
)

PAYROLL_OUTPUT_DIR = Path(os.getenv("PAYROLL_OUTPUT_DIR", "storage/outputs/payroll_drafts"))
STATUS_BORRADOR = "BORRADOR_GENERADO"


def _estimate_irpf(gross: float) -> float:
    """Estimación simplificada IRPF (España) - tramos aproximados."""
    if gross <= 0:
        return 0.0
    annual = gross * 14  # Pagas
    if annual <= 12450:
        return round(gross * 0.19, 2)
    if annual <= 20200:
        return round(gross * 0.24, 2)
    if annual <= 35200:
        return round(gross * 0.30, 2)
    if annual <= 60000:
        return round(gross * 0.37, 2)
    return round(gross * 0.45, 2)


def _estimate_social_security(gross: float) -> float:
    """Estimación cotización Seguridad Social trabajador (~6.35% bruto)."""
    if gross <= 0:
        return 0.0
    return round(gross * 0.0635, 2)


def calculate_payroll(gross_salary: float) -> Dict[str, float]:
    """Calcula retención IRPF estimada, cotización estimada y neto."""
    irpf = _estimate_irpf(gross_salary)
    ss = _estimate_social_security(gross_salary)
    net = round(gross_salary - irpf - ss, 2)
    return {
        "gross_salary": gross_salary,
        "irpf_estimated": irpf,
        "social_security_estimated": ss,
        "net_salary_estimated": max(0, net),
    }


def _generate_pdf(
    payroll_data: Dict[str, Any],
    company_name: str,
    employee_name: str,
    month: str,
    year: int,
    output_path: Path,
) -> str:
    """Genera PDF con encabezado BORRADOR y disclaimer legal."""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
    except ImportError:
        logger.warning("reportlab no instalado. Generando archivo TXT en su lugar.")
        # Fallback: TXT con el mismo contenido
        txt_path = output_path.with_suffix(".txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("=== BORRADOR - NÓMINA (NO OFICIAL) ===\n\n")
            f.write(f"Empresa: {company_name}\n")
            f.write(f"Empleado: {employee_name}\n")
            f.write(f"Período: {month}/{year}\n\n")
            f.write(f"Salario bruto: {payroll_data.get('gross_salary', 0):.2f} €\n")
            f.write(f"IRPF estimado: {payroll_data.get('irpf_estimated', 0):.2f} €\n")
            f.write(f"Seguridad Social estimada: {payroll_data.get('social_security_estimated', 0):.2f} €\n")
            f.write(f"Salario neto estimado: {payroll_data.get('net_salary_estimated', 0):.2f} €\n\n")
            f.write(f"--- DISCLAIMER LEGAL ---\n{LEGAL_DISCLAIMER}\n")
        return str(txt_path)

    PAYROLL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = output_path.with_suffix(".pdf")
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    width, height = A4

    # Encabezado BORRADOR
    c.setFont("Helvetica-Bold", 16)
    c.setFillColorRGB(0.9, 0.2, 0.2)
    c.drawString(2 * cm, height - 2 * cm, "*** BORRADOR - NO OFICIAL ***")
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 12)
    c.drawString(2 * cm, height - 2.5 * cm, f"Empresa: {company_name}")
    c.drawString(2 * cm, height - 3 * cm, f"Empleado: {employee_name}")
    c.drawString(2 * cm, height - 3.5 * cm, f"Período: {month}/{year}")

    y = height - 5 * cm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(2 * cm, y, "Concepto")
    c.drawString(12 * cm, y, "Importe (€)")
    y -= 0.6 * cm
    c.setFont("Helvetica", 10)
    c.drawString(2 * cm, y, "Salario bruto")
    c.drawString(12 * cm, y, f"{payroll_data.get('gross_salary', 0):.2f}")
    y -= 0.5 * cm
    c.drawString(2 * cm, y, "IRPF (estimado)")
    c.drawString(12 * cm, y, f"-{payroll_data.get('irpf_estimated', 0):.2f}")
    y -= 0.5 * cm
    c.drawString(2 * cm, y, "Seg. Social (estimado)")
    c.drawString(12 * cm, y, f"-{payroll_data.get('social_security_estimated', 0):.2f}")
    y -= 0.7 * cm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(2 * cm, y, "Salario neto estimado")
    c.drawString(12 * cm, y, f"{payroll_data.get('net_salary_estimated', 0):.2f}")
    y -= 1.5 * cm

    # Disclaimer legal
    c.setFont("Helvetica", 8)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    for line in _wrap_text(LEGAL_DISCLAIMER, 80):
        c.drawString(2 * cm, y, line)
        y -= 0.4 * cm
    c.setFillColorRGB(0, 0, 0)
    c.showPage()
    c.save()
    return str(pdf_path)


def _wrap_text(text: str, max_chars: int) -> list:
    """Envolver texto en líneas."""
    words = text.split()
    lines = []
    current = ""
    for w in words:
        if len(current) + len(w) + 1 <= max_chars:
            current = f"{current} {w}".strip() if current else w
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines


def generate_and_persist(
    db: Session,
    company_id: int,
    employee_id: int,
    gross_salary: float,
    month: str,
    year: int,
    company_name: str = "",
    employee_name: str = "",
) -> Tuple[PayrollDraft, str]:
    """
    Calcula nómina, genera PDF con BORRADOR y disclaimer, persiste en BD.
    Retorna (PayrollDraft, pdf_path).
    NO presenta a Seguridad Social. NO ejecuta pagos.
    """
    payroll = calculate_payroll(gross_salary)
    net = payroll["net_salary_estimated"]
    irpf = payroll["irpf_estimated"]
    ss = payroll["social_security_estimated"]

    record = PayrollDraft(
        company_id=company_id,
        employee_id=employee_id,
        gross_salary=gross_salary,
        irpf_estimated=irpf,
        social_security_estimated=ss,
        net_salary_estimated=net,
        month=month,
        year=year,
        status=STATUS_BORRADOR,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    PAYROLL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"payroll_{company_id}_{employee_id}_{year}_{month.replace(' ', '_')}_{record.id}"
    output_path = PAYROLL_OUTPUT_DIR / filename

    pdf_path = _generate_pdf(
        payroll_data=payroll,
        company_name=company_name or f"Empresa {company_id}",
        employee_name=employee_name or f"Empleado {employee_id}",
        month=month,
        year=year,
        output_path=output_path,
    )
    record.pdf_path = pdf_path
    db.add(record)
    db.commit()
    db.refresh(record)

    logger.info(f"[PAYROLL] Borrador generado id={record.id} company={company_id} employee={employee_id}")
    return record, pdf_path


def send_to_labor_advisor(
    to_email: str,
    subject: str,
    body: str,
    pdf_path: str,
) -> Dict[str, Any]:
    """Envía email con PDF adjunto al gestor laboral."""
    from services.email_service import email_service
    from services.activity_logger import ActivityLogger

    if not email_service.is_configured():
        return {"success": False, "error": "Email service not configured"}

    if not os.path.isfile(pdf_path):
        return {"success": False, "error": f"PDF no encontrado: {pdf_path}"}

    try:
        from sendgrid.helpers.mail import Mail, Email, To, Content, Attachment, FileContent, FileName, FileType
    except ImportError:
        return {"success": False, "error": "SendGrid Attachment not available"}

    with open(pdf_path, "rb") as f:
        pdf_data = base64.b64encode(f.read()).decode()

    message = Mail(
        from_email=Email(email_service.from_email, email_service.from_name),
        to_emails=To(to_email),
        subject=subject,
        html_content=Content("text/html", body),
    )
    mime_type = "application/pdf" if pdf_path.lower().endswith(".pdf") else "text/plain"
    attachment = Attachment(
        FileContent(pdf_data),
        FileName(os.path.basename(pdf_path)),
        FileType(mime_type),
    )
    message.add_attachment(attachment)

    try:
        response = email_service.client.send(message)
        result = {"success": True, "status_code": response.status_code}
        ActivityLogger.log_activity(
            agent_name="ZEUS",
            action_type="email_sent",
            action_description=f"Nómina borrador enviada a gestor laboral: {to_email}",
            details={"to": to_email, "subject": subject, "attachment": os.path.basename(pdf_path)},
            status="completed",
            priority="high",
        )
    except Exception as e:
        result = {"success": False, "error": str(e)}
        ActivityLogger.log_activity(
            agent_name="ZEUS",
            action_type="email_error",
            action_description=f"Error enviando nómina a {to_email}: {str(e)}",
            details={"to": to_email, "subject": subject, "error": str(e)},
            status="failed",
            priority="high",
        )
    return result
