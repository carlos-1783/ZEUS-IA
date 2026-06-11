"""
RAFAEL fiscal engine v2 — facturas PDF y modelo 303 Excel desde datos reales de BD.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import and_
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.company import Company, UserCompany
from app.models.customer import Customer
from app.models.document_approval import DocumentApproval
from app.models.erp import Invoice, InvoiceItem
from app.models.expense import Expense
from app.models.user import User
from services.fiscal_excel_generator import generate_model_303_xlsx_v1
from services.fiscal_pdf_generator import generate_invoice_pdf_v1
from services.zeus_office_mode import require_company_id, translate_activity

logger = logging.getLogger(__name__)

SUPPORTED_VAT_RATES = (21, 10, 4, 0)
FISCAL_SUBDIR = "fiscal"


@dataclass
class Model303Result:
    company_id: int
    period: str
    year: int
    quarter: int
    base_imponible: float
    iva_devengado: float
    iva_soportado: float
    resultado: float
    invoice_count: int
    expense_count: int
    vat_breakdown: Dict[str, float]


def _fiscal_root() -> Path:
    root = Path(settings.STATIC_DIR) / FISCAL_SUBDIR
    root.mkdir(parents=True, exist_ok=True)
    return root


def _quarter_bounds(year: int, quarter: int) -> Tuple[datetime, datetime]:
    if quarter not in (1, 2, 3, 4):
        raise HTTPException(status_code=422, detail="Trimestre debe ser 1-4.")
    start_month = (quarter - 1) * 3 + 1
    end_month = start_month + 2
    start = datetime(year, start_month, 1)
    if end_month == 12:
        end = datetime(year, 12, 31, 23, 59, 59)
    else:
        end = datetime(year, end_month + 1, 1) - timedelta(seconds=1)
    return start, end


def assert_user_company_access(db: Session, user: User, company_id: int) -> None:
    require_company_id(company_id, context="motor fiscal RAFAEL")
    if getattr(user, "is_superuser", False):
        return
    link = (
        db.query(UserCompany)
        .filter(UserCompany.user_id == user.id, UserCompany.company_id == company_id)
        .first()
    )
    if not link:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso a la empresa indicada.",
        )


def validate_file_size(file_path: str) -> int:
    path = Path(file_path)
    if not path.is_file():
        raise HTTPException(status_code=500, detail="Archivo fiscal no generado.")
    size = path.stat().st_size
    if size <= 0:
        raise HTTPException(status_code=422, detail="Documento fiscal vacío (0 KB).")
    return size


def fetch_period_financials(
    db: Session,
    *,
    company_id: int,
    year: int,
    quarter: int,
) -> Model303Result:
    start, end = _quarter_bounds(year, quarter)
    period = f"{year}-Q{quarter}"

    invoices = (
        db.query(Invoice)
        .filter(
            Invoice.company_id == company_id,
            Invoice.issue_date >= start,
            Invoice.issue_date <= end,
        )
        .all()
    )
    expenses = (
        db.query(Expense)
        .filter(
            Expense.company_id == company_id,
            Expense.issue_date >= start,
            Expense.issue_date <= end,
        )
        .all()
    )

    if not invoices and not expenses:
        raise HTTPException(
            status_code=422,
            detail="No hay datos financieros en el periodo (facturas ni gastos).",
        )

    base_imponible = sum(float(i.subtotal or 0) for i in invoices)
    iva_devengado = sum(float(i.tax_amount or 0) for i in invoices)
    iva_soportado = sum(float(e.tax_amount or 0) for e in expenses)
    resultado = round(iva_devengado - iva_soportado, 2)

    if base_imponible == 0 and iva_devengado == 0 and iva_soportado == 0:
        raise HTTPException(status_code=422, detail="Totales fiscales en cero; no se genera modelo 303.")

    vat_breakdown: Dict[str, float] = {}
    for inv in invoices:
        for item in inv.items or []:
            rate = round(float(item.tax_rate or 0), 2)
            key = str(int(rate)) if rate == int(rate) else str(rate)
            vat_breakdown[key] = vat_breakdown.get(key, 0.0) + float(item.tax_amount or 0)

    return Model303Result(
        company_id=company_id,
        period=period,
        year=year,
        quarter=quarter,
        base_imponible=round(base_imponible, 2),
        iva_devengado=round(iva_devengado, 2),
        iva_soportado=round(iva_soportado, 2),
        resultado=resultado,
        invoice_count=len(invoices),
        expense_count=len(expenses),
        vat_breakdown=vat_breakdown,
    )


def _relative_static_url(abs_path: str) -> str:
    static_root = Path(settings.STATIC_DIR).resolve()
    resolved = Path(abs_path).resolve()
    try:
        rel = resolved.relative_to(static_root)
    except ValueError:
        rel = Path(os.path.basename(abs_path))
    return f"/static/{rel.as_posix()}"


def register_fiscal_workspace_document(
    db: Session,
    *,
    user: User,
    company_id: int,
    title: str,
    document_type: str,
    fiscal_document_type: str,
    export_format: str,
    mime_type: str,
    file_path: str,
    file_size: int,
    extra_payload: Optional[Dict[str, Any]] = None,
) -> DocumentApproval:
    from datetime import timezone

    payload: Dict[str, Any] = {
        "title": title,
        "type": "fiscal_document",
        "content": {
            "document_type": document_type,
            "fiscal_document_type": fiscal_document_type,
            "file_path": file_path,
            "file_url": _relative_static_url(file_path),
            "file_size": file_size,
            "mime_type": mime_type,
            "only_real_file": True,
            **(extra_payload or {}),
        },
        "status": "draft",
        "visible_in_workspace": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    doc = DocumentApproval(
        user_id=user.id,
        company_id=company_id,
        agent_name="RAFAEL",
        document_type="fiscal_document",
        document_payload=payload,
        status="draft",
        visible_in_workspace=True,
        fiscal_document_type=fiscal_document_type,
        export_format=export_format,
        file_path=file_path,
        file_size_bytes=file_size,
        mime_type=mime_type,
        audit_log=[
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": "fiscal_document_stored",
                "agent": "RAFAEL",
                "file_size": file_size,
            }
        ],
    )
    try:
        db.add(doc)
        db.commit()
        db.refresh(doc)
    except (OperationalError, ProgrammingError) as exc:
        db.rollback()
        logger.exception("No se pudo guardar documento fiscal (esquema BD)")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Base de datos pendiente de actualizar para documentos fiscales. Reintenta en unos minutos.",
        ) from exc
    return doc


def generate_invoice_pdf_flow(
    db: Session,
    *,
    user: User,
    invoice_id: int,
    company_id: Optional[int] = None,
) -> Dict[str, Any]:
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada.")

    cid = company_id or getattr(invoice, "company_id", None)
    cid = require_company_id(cid, context="generar PDF de factura")
    assert_user_company_access(db, user, cid)

    if getattr(invoice, "company_id", None) and invoice.company_id != cid:
        raise HTTPException(status_code=403, detail="La factura no pertenece a la empresa indicada.")

    customer = None
    if invoice.customer_id:
        customer = db.query(Customer).filter(Customer.id == invoice.customer_id).first()

    client_name = (customer.name if customer else "Cliente") or "Cliente"
    client_email = (customer.email if customer else "") or ""

    items = []
    for item in invoice.items or []:
        items.append(
            {
                "description": item.description,
                "quantity": float(item.quantity or 1),
                "unit_price": float(item.unit_price or 0),
                "total": float(item.total or 0),
            }
        )

    if not items:
        raise HTTPException(status_code=422, detail="La factura no tiene líneas.")

    subtotal = float(invoice.subtotal or 0)
    tax_amount = float(invoice.tax_amount or 0)
    total = float(invoice.total or 0)
    if total <= 0:
        raise HTTPException(status_code=422, detail="Total de factura debe ser mayor que cero.")

    company = db.query(Company).filter(Company.id == cid).first()
    company_name = (company.company_name if company else f"Empresa {cid}") or f"Empresa {cid}"

    out_dir = _fiscal_root() / str(cid) / "invoices"
    filename = f"invoice_{invoice.invoice_number or invoice.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    pdf_path = generate_invoice_pdf_v1(
        output_path=out_dir / filename,
        company_name=company_name,
        client_name=client_name,
        client_email=client_email,
        invoice_number=str(invoice.invoice_number or invoice.id),
        issue_date=invoice.issue_date.strftime("%Y-%m-%d") if invoice.issue_date else date.today().isoformat(),
        items=items,
        subtotal=subtotal,
        tax_amount=tax_amount,
        total=total,
    )
    file_size = validate_file_size(pdf_path)

    doc = register_fiscal_workspace_document(
        db,
        user=user,
        company_id=cid,
        title=f"Factura {invoice.invoice_number}",
        document_type="invoice",
        fiscal_document_type="factura",
        export_format="pdf",
        mime_type="application/pdf",
        file_path=pdf_path,
        file_size=file_size,
        extra_payload={
            "invoice_id": invoice.id,
            "client_name": client_name,
            "client_email": client_email,
            "total": total,
            "vat": tax_amount,
        },
    )

    from services.event_bus import emit_cashflow_updated, emit_invoice_generated

    emit_invoice_generated(
        user_id=user.id,
        user_email=getattr(user, "email", None),
        company_id=cid,
        invoice_id=invoice.id,
        file_path=pdf_path,
        file_size=file_size,
        db=db,
    )
    emit_cashflow_updated(
        user_id=user.id,
        user_email=getattr(user, "email", None),
        company_id=cid,
        amount=total,
        direction="in",
        source="RAFAEL_INVOICE_PDF",
        invoice_id=invoice.id,
        db=db,
    )

    return {
        "success": True,
        "document_id": doc.id,
        "file_path": pdf_path,
        "file_url": _relative_static_url(pdf_path),
        "file_size": file_size,
        "mime_type": "application/pdf",
        "message": translate_activity("invoice_created"),
    }


def generate_model_303_flow(
    db: Session,
    *,
    user: User,
    company_id: int,
    year: int,
    quarter: int,
) -> Dict[str, Any]:
    cid = require_company_id(company_id, context="modelo 303")
    assert_user_company_access(db, user, cid)

    try:
        model = fetch_period_financials(db, company_id=cid, year=year, quarter=quarter)
    except (OperationalError, ProgrammingError) as exc:
        logger.exception("Consulta fiscal falló (esquema BD)")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Base de datos pendiente de actualizar para el modelo 303. Reintenta en unos minutos.",
        ) from exc

    company = db.query(Company).filter(Company.id == cid).first()
    company_name = (company.company_name if company else f"Empresa {cid}") or f"Empresa {cid}"

    out_dir = _fiscal_root() / str(cid) / "model_303"
    filename = f"modelo_303_{model.period}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    try:
        xlsx_path = generate_model_303_xlsx_v1(
            output_path=out_dir / filename,
            company_name=company_name,
            period=model.period,
            model_data={
                "base_imponible": model.base_imponible,
                "iva_devengado": model.iva_devengado,
                "iva_soportado": model.iva_soportado,
                "resultado": model.resultado,
                "vat_breakdown": model.vat_breakdown,
            },
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    file_size = validate_file_size(xlsx_path)

    doc = register_fiscal_workspace_document(
        db,
        user=user,
        company_id=cid,
        title=f"Modelo 303 {model.period}",
        document_type="model_303",
        fiscal_document_type="modelo_303",
        export_format="xlsx",
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        file_path=xlsx_path,
        file_size=file_size,
        extra_payload={
            "period": model.period,
            "iva_devengado": model.iva_devengado,
            "iva_soportado": model.iva_soportado,
            "resultado": model.resultado,
            "invoice_count": model.invoice_count,
            "expense_count": model.expense_count,
        },
    )

    from services.event_bus import emit_cashflow_updated, emit_model_303_generated

    emit_model_303_generated(
        user_id=user.id,
        user_email=getattr(user, "email", None),
        company_id=cid,
        period=model.period,
        file_path=xlsx_path,
        file_size=file_size,
        resultado=model.resultado,
        db=db,
    )
    emit_cashflow_updated(
        user_id=user.id,
        user_email=getattr(user, "email", None),
        company_id=cid,
        amount=abs(model.resultado),
        direction="out" if model.resultado >= 0 else "in",
        source="RAFAEL_MODEL_303",
        db=db,
    )

    return {
        "success": True,
        "document_id": doc.id,
        "file_path": xlsx_path,
        "file_url": _relative_static_url(xlsx_path),
        "file_size": file_size,
        "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "modelo_303": {
            "period": model.period,
            "iva_devengado": model.iva_devengado,
            "iva_soportado": model.iva_soportado,
            "resultado": model.resultado,
        },
        "message": translate_activity("tax_model_303_generated"),
    }
