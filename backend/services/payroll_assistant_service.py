"""
📋 Payroll Assistant Service
Genera borradores de nómina - SIN presentación a Seguridad Social, SIN pagos automáticos.
Toda nómina es BORRADOR y requiere validación por asesor laboral.
"""
from __future__ import annotations

import os
import io
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


def _render_document(
    payroll_data: Dict[str, Any],
    company_name: str,
    employee_name: str,
    month: str,
    year: int,
) -> Tuple[bytes, str, str]:
    """Genera el borrador EN MEMORIA (nunca a disco: Railway no persiste ficheros).

    Devuelve (bytes, extension, mime). Sin reportlab, TXT con el mismo contenido."""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
    except ImportError:
        logger.warning("reportlab no instalado. Generando borrador TXT en su lugar.")
        lines = [
            "=== BORRADOR - NÓMINA (NO OFICIAL) ===",
            "",
            f"Empresa: {company_name}",
            f"Empleado: {employee_name}",
            f"Período: {month}/{year}",
            "",
            f"Salario bruto: {payroll_data.get('gross_salary', 0):.2f} €",
            f"IRPF estimado: {payroll_data.get('irpf_estimated', 0):.2f} €",
            f"Seguridad Social estimada: {payroll_data.get('social_security_estimated', 0):.2f} €",
            f"Salario neto estimado: {payroll_data.get('net_salary_estimated', 0):.2f} €",
            "",
            "--- DISCLAIMER LEGAL ---",
            LEGAL_DISCLAIMER,
            "",
        ]
        return "\n".join(lines).encode("utf-8"), "txt", "text/plain"

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
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
    return buf.getvalue(), "pdf", "application/pdf"


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


def _names_for(db: Session, owner_user_id: int, employee_id: int) -> Tuple[str, str]:
    owner = db.query(User).filter(User.id == owner_user_id).first()
    emp = db.query(User).filter(User.id == employee_id).first()
    company_name = (
        (owner.company_name or owner.full_name or owner.email) if owner else f"Empresa {owner_user_id}"
    )
    employee_name = (emp.full_name or emp.email) if emp else f"Empleado {employee_id}"
    return company_name, employee_name


def _owner_company_id(db: Session, owner_user_id: int) -> Optional[int]:
    """Empresa real (companies.id) del owner, para el prefijo empresa/{id}/ en R2."""
    from app.models.company import UserCompany

    link = (
        db.query(UserCompany)
        .filter(UserCompany.user_id == owner_user_id)
        .order_by(UserCompany.id.asc())
        .first()
    )
    return int(link.company_id) if link else None


def _record_payroll_data(record: PayrollDraft) -> Dict[str, float]:
    return {
        "gross_salary": float(record.gross_salary or 0),
        "irpf_estimated": float(record.irpf_estimated or 0),
        "social_security_estimated": float(record.social_security_estimated or 0),
        "net_salary_estimated": float(record.net_salary_estimated or 0),
    }


def _draft_filename(record: PayrollDraft, ext: str) -> str:
    month = str(record.month or "").replace(" ", "_")
    return f"nomina_borrador_{record.year}_{month}_{record.id}.{ext}"


def generate_and_persist(
    db: Session,
    company_id: int,
    employee_id: int,
    gross_salary: float,
    month: str,
    year: int,
    company_name: str = "",
    employee_name: str = "",
) -> Tuple[PayrollDraft, Optional[str]]:
    """
    Calcula nómina, persiste el borrador en BD y guarda el documento en R2
    (empresa/{companies.id}/documents/...). Nunca escribe en disco local.
    Retorna (PayrollDraft, referencia "r2:<file_id>" o None si R2 no está configurado;
    en ese caso la descarga lo regenera desde la fila de BD).
    NO presenta a Seguridad Social. NO ejecuta pagos. NO envía nada al empleado.
    """
    payroll = calculate_payroll(gross_salary)
    record = PayrollDraft(
        owner_user_id=company_id,
        employee_id=employee_id,
        gross_salary=gross_salary,
        irpf_estimated=payroll["irpf_estimated"],
        social_security_estimated=payroll["social_security_estimated"],
        net_salary_estimated=payroll["net_salary_estimated"],
        month=month,
        year=year,
        status=STATUS_BORRADOR,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    data, ext, mime = _render_document(
        payroll_data=payroll,
        company_name=company_name or f"Empresa {company_id}",
        employee_name=employee_name or f"Empleado {employee_id}",
        month=month,
        year=year,
    )
    pdf_ref: Optional[str] = None
    from services import object_storage

    storage_cid = _owner_company_id(db, company_id)
    if storage_cid is None:
        logger.warning("[PAYROLL] borrador id=%s sin empresa real: documento no se guarda en R2", record.id)
    elif not object_storage.is_configured():
        logger.warning(
            "[PAYROLL] borrador id=%s: R2 sin configurar (%s); el documento se regenerará desde BD al descargar",
            record.id, ", ".join(object_storage.missing_config()),
        )
    else:
        try:
            row = object_storage.store_file(
                db,
                company_id=storage_cid,
                user_id=company_id,
                category="documents",
                filename=_draft_filename(record, ext),
                content_type=mime,
                data=data,
                agent_name="ZEUS",
            )
            pdf_ref = f"r2:{row.id}"
        except (object_storage.StorageNotConfigured, object_storage.StorageError, ValueError) as exc:
            logger.error("[PAYROLL] borrador id=%s: no se pudo guardar en R2: %s", record.id, exc)
    if pdf_ref:
        record.pdf_path = pdf_ref
        db.add(record)
        db.commit()
        db.refresh(record)

    logger.info(
        "[PAYROLL] Borrador generado id=%s owner_user=%s employee=%s documento=%s",
        record.id, company_id, employee_id, pdf_ref or "regenerable_desde_bd",
    )
    return record, pdf_ref


def draft_document(db: Session, record: PayrollDraft) -> Tuple[bytes, str, str]:
    """Documento del borrador: (bytes, filename, mime).

    1) En R2 (pdf_path = "r2:<file_id>"): se lee de ahí, solo dentro de la empresa del owner.
    2) Legado: ruta local si aún existe en este contenedor.
    3) Si no, se regenera desde la fila de BD (mismos importes, mismo formato)."""
    ref = str(record.pdf_path or "")
    if ref.startswith("r2:"):
        from services import object_storage

        cid = _owner_company_id(db, record.owner_user_id)
        row = object_storage.get_for_companies(db, ref[3:], [cid] if cid else [])
        if row is not None:
            try:
                return object_storage.read_bytes(row), row.original_filename, row.content_type
            except (object_storage.StorageNotConfigured, object_storage.StorageError) as exc:
                logger.error("[PAYROLL] borrador id=%s: lectura R2 falló (%s); se regenera desde BD", record.id, exc)
        else:
            logger.error("[PAYROLL] borrador id=%s: fichero R2 %s no encontrado en su empresa", record.id, ref)
    elif ref and os.path.isfile(ref):
        with open(ref, "rb") as f:
            data = f.read()
        mime = "application/pdf" if ref.lower().endswith(".pdf") else "text/plain"
        return data, os.path.basename(ref), mime

    company_name, employee_name = _names_for(db, record.owner_user_id, record.employee_id)
    data, ext, mime = _render_document(
        _record_payroll_data(record), company_name, employee_name, str(record.month or ""), int(record.year or 0)
    )
    return data, _draft_filename(record, ext), mime


def send_to_labor_advisor(
    to_email: str,
    subject: str,
    body: str,
    attachment: Tuple[bytes, str, str],
) -> Dict[str, Any]:
    """Envía email con el borrador adjunto (bytes, filename, mime) al gestor laboral.
    Nunca al empleado ni a organismos (Seguridad Social / AEAT)."""
    from services.email_service import email_service
    from services.activity_logger import ActivityLogger

    if not email_service.is_configured():
        return {"success": False, "error": "Email service not configured"}

    data, att_name, mime_type = attachment
    if not data:
        return {"success": False, "error": "Borrador sin contenido"}

    try:
        from sendgrid.helpers.mail import Mail, Email, To, Content, Attachment, FileContent, FileName, FileType
    except ImportError:
        return {"success": False, "error": "SendGrid Attachment not available"}

    pdf_data = base64.b64encode(data).decode()

    message = Mail(
        from_email=Email(email_service.from_email, email_service.from_name),
        to_emails=To(to_email),
        subject=subject,
        html_content=Content("text/html", body),
    )
    message.add_attachment(Attachment(
        FileContent(pdf_data),
        FileName(att_name),
        FileType(mime_type),
    ))

    try:
        response = email_service.client.send(message)
        result = {"success": True, "status_code": response.status_code}
        ActivityLogger.log_activity(
            agent_name="ZEUS",
            action_type="email_sent",
            action_description=f"Nómina borrador enviada a gestor laboral: {to_email}",
            details={"to": to_email, "subject": subject, "attachment": att_name},
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
