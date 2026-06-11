"""Generación real de PDF de factura (invoice_template_v1)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def _wrap(text: str, max_chars: int) -> List[str]:
    words = (text or "").split()
    lines: List[str] = []
    current = ""
    for w in words:
        if len(current) + len(w) + 1 > max_chars:
            if current:
                lines.append(current)
            current = w
        else:
            current = f"{current} {w}".strip()
    if current:
        lines.append(current)
    return lines or [""]


def generate_invoice_pdf_v1(
    *,
    output_path: Path,
    company_name: str,
    client_name: str,
    client_email: str,
    invoice_number: str,
    issue_date: str,
    items: List[Dict[str, Any]],
    subtotal: float,
    tax_amount: float,
    total: float,
) -> str:
    """Escribe PDF de factura. Devuelve ruta absoluta."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path = output_path.with_suffix(".pdf")

    try:
        from reportlab.lib.pagesizes import A4  # pyright: ignore[reportMissingModuleSource]
        from reportlab.lib.units import cm  # pyright: ignore[reportMissingModuleSource]
        from reportlab.pdfgen import canvas  # pyright: ignore[reportMissingModuleSource]
    except ImportError as exc:
        raise RuntimeError("reportlab no disponible para generar PDF de factura") from exc

    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    width, height = A4
    y = height - 2 * cm

    c.setFont("Helvetica-Bold", 16)
    c.drawString(2 * cm, y, "FACTURA")
    y -= 0.8 * cm
    c.setFont("Helvetica", 10)
    c.drawString(2 * cm, y, f"Nº: {invoice_number}")
    y -= 0.5 * cm
    c.drawString(2 * cm, y, f"Fecha: {issue_date}")
    y -= 0.8 * cm
    c.drawString(2 * cm, y, f"Emisor: {company_name}")
    y -= 0.5 * cm
    c.drawString(2 * cm, y, f"Cliente: {client_name}")
    y -= 0.5 * cm
    c.drawString(2 * cm, y, f"Email: {client_email or '—'}")
    y -= 1 * cm

    c.setFont("Helvetica-Bold", 10)
    c.drawString(2 * cm, y, "Descripción")
    c.drawString(11 * cm, y, "Cant.")
    c.drawString(13 * cm, y, "P.unit.")
    c.drawString(16 * cm, y, "Total")
    y -= 0.6 * cm
    c.setFont("Helvetica", 9)

    for item in items:
        desc = str(item.get("description") or item.get("product_name") or "—")[:60]
        qty = float(item.get("quantity") or 1)
        unit = float(item.get("unit_price") or 0)
        line_total = float(item.get("total") or qty * unit)
        c.drawString(2 * cm, y, desc)
        c.drawString(11 * cm, y, f"{qty:.2f}")
        c.drawString(13 * cm, y, f"{unit:.2f} €")
        c.drawString(16 * cm, y, f"{line_total:.2f} €")
        y -= 0.5 * cm
        if y < 3 * cm:
            c.showPage()
            y = height - 2 * cm

    y -= 0.5 * cm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(13 * cm, y, "Base imponible:")
    c.drawString(16 * cm, y, f"{subtotal:.2f} €")
    y -= 0.5 * cm
    c.drawString(13 * cm, y, "IVA:")
    c.drawString(16 * cm, y, f"{tax_amount:.2f} €")
    y -= 0.5 * cm
    c.drawString(13 * cm, y, "TOTAL:")
    c.drawString(16 * cm, y, f"{total:.2f} €")

    c.showPage()
    c.save()
    logger.info("Invoice PDF generated: %s", pdf_path)
    return str(pdf_path.resolve())
