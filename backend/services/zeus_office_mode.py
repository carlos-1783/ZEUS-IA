"""
ZEUS Office Mode v1 — reglas de integridad, validación de entidades y traducciones.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status

OFFICE_MODE_V1: Dict[str, Any] = {
    "environment": "production_ready",
    "core_modules": {
        "crm": True,
        "billing": True,
        "payments": True,
        "taxes": True,
        "cashflow": True,
        "analytics": True,
    },
    "data_integrity_rules": {
        "no_empty_records": True,
        "no_0kb_documents": True,
        "strict_required_fields": True,
        "company_id_mandatory": True,
    },
    "entities": {
        "customers": {"required": ["id", "name", "email"]},
        "invoices": {
            "required": [
                "invoice_id",
                "customer_id",
                "date",
                "base_amount",
                "tax_amount",
                "total_amount",
                "status",
            ],
            "status_values": ["draft", "sent", "paid", "overdue"],
        },
        "payments": {
            "required": ["payment_id", "invoice_id", "amount", "method", "date"],
        },
        "taxes": {
            "modelo_303": {
                "type": "quarterly_vat",
                "requires": ["period", "vat_collected", "vat_paid"],
            },
            "modelo_390": {"type": "annual_summary"},
        },
    },
    "ui_rules": {
        "hide_internal_ids": True,
        "hide_workspace_ids": True,
        "human_readable_only": True,
    },
    "exports": {"csv": True, "excel": True, "fields_standardized": True},
    "activity_log": {
        "track_all_financial_events": True,
        "track_user_actions": True,
        "human_readable": True,
    },
}

ACTIVITY_HUMAN: Dict[str, str] = {
    "payment_created": "Cobro registrado",
    "payment_registered": "Pago registrado",
    "record_created": "Expediente creado",
    "customer_created": "Cliente creado",
    "customer_updated": "Cliente actualizado",
    "record_updated": "Expediente actualizado",
    "record_deleted": "Expediente eliminado",
    "invoice_created": "Factura creada",
    "invoice_paid": "Factura pagada",
    "cashflow_updated": "Cashflow actualizado",
    "invoice_generated": "Factura generada correctamente",
    "tax_model_303_generated": "Modelo 303 generado",
    "fiscal_document_stored": "Documento fiscal almacenado",
    "tax_model_390_generated": "Modelo 390 generado",
}

MIN_DOCUMENT_BYTES = 32


def translate_activity(action: str) -> str:
    return ACTIVITY_HUMAN.get(action, action.replace("_", " ").capitalize())


def require_company_id(company_id: Optional[int], *, context: str = "operación") -> int:
    if company_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Se requiere empresa asociada para {context} (company_id obligatorio).",
        )
    return int(company_id)


def _missing_fields(data: Dict[str, Any], required: List[str]) -> List[str]:
    missing: List[str] = []
    for key in required:
        val = data.get(key)
        if val is None:
            missing.append(key)
        elif isinstance(val, str) and not val.strip():
            missing.append(key)
    return missing


def validate_customer_record(
    *,
    customer_id: Optional[int] = None,
    name: Optional[str] = None,
    email: Optional[str] = None,
    for_create: bool = False,
) -> None:
    if not OFFICE_MODE_V1["data_integrity_rules"]["strict_required_fields"]:
        return
    if for_create:
        payload = {
            "name": (name or "").strip(),
            "email": (email or "").strip() if email else None,
        }
        missing = _missing_fields(payload, ["name", "email"])
        if missing:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Cliente incompleto. Campos obligatorios: {', '.join(missing)}",
            )
        return
    if name is not None and not str(name).strip():
        raise HTTPException(status_code=422, detail="El nombre del cliente no puede estar vacío.")
    if email is not None and not str(email).strip():
        raise HTTPException(status_code=422, detail="El email del cliente es obligatorio.")
    _ = customer_id


def validate_invoice_logical(
    *,
    customer_id: Optional[int],
    issue_date: Any,
    subtotal: float,
    tax_amount: float,
    total: float,
    status_value: str,
) -> None:
    if not OFFICE_MODE_V1["data_integrity_rules"]["strict_required_fields"]:
        return
    payload = {
        "customer_id": customer_id,
        "date": issue_date,
        "base_amount": subtotal,
        "tax_amount": tax_amount,
        "total_amount": total,
        "status": status_value,
    }
    missing = _missing_fields(payload, ["customer_id", "date", "base_amount", "tax_amount", "total_amount", "status"])
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Factura incompleta. Campos obligatorios: {', '.join(missing)}",
        )
    allowed = OFFICE_MODE_V1["entities"]["invoices"]["status_values"]
    norm = (status_value or "").lower().replace("partially_paid", "paid")
    if norm not in allowed and norm not in ("partially_paid", "void", "proforma"):
        raise HTTPException(status_code=422, detail=f"Estado de factura no válido: {status_value}")


def validate_payment_logical(
    *,
    invoice_id: int,
    amount: float,
    method: str,
    payment_date: Any,
) -> None:
    if not OFFICE_MODE_V1["data_integrity_rules"]["strict_required_fields"]:
        return
    payload = {
        "invoice_id": invoice_id,
        "amount": amount,
        "method": method,
        "date": payment_date,
    }
    missing = _missing_fields(payload, ["invoice_id", "amount", "method", "date"])
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Pago incompleto. Campos obligatorios: {', '.join(missing)}",
        )
    if amount <= 0:
        raise HTTPException(status_code=422, detail="El importe del pago debe ser mayor que cero.")


def validate_tax_model_303(data: Dict[str, Any]) -> None:
    if not OFFICE_MODE_V1["data_integrity_rules"]["strict_required_fields"]:
        return
    modelo = data.get("modelo_303") if isinstance(data.get("modelo_303"), dict) else data
    if not isinstance(modelo, dict):
        raise HTTPException(status_code=422, detail="Modelo 303 inválido.")
    period = modelo.get("period") or modelo.get("quarter")
    vat_collected = modelo.get("vat_collected") if modelo.get("vat_collected") is not None else modelo.get("cuota")
    vat_paid = modelo.get("vat_paid")
    if period is None or vat_collected is None:
        raise HTTPException(
            status_code=422,
            detail="Modelo 303 requiere periodo, IVA repercutido y soportado.",
        )
    _ = vat_paid


def assert_non_empty_record(title: Optional[str], *, entity: str = "registro") -> None:
    if not OFFICE_MODE_V1["data_integrity_rules"]["no_empty_records"]:
        return
    if not (title or "").strip():
        raise HTTPException(status_code=422, detail=f"No se permite {entity} sin título o nombre.")


def assert_deliverable_content(content: Any, *, title: str = "") -> None:
    if not OFFICE_MODE_V1["data_integrity_rules"]["no_0kb_documents"]:
        return
    if content is None:
        raise HTTPException(status_code=422, detail="Documento vacío: sin contenido.")
    if isinstance(content, str):
        raw = content.encode("utf-8")
    else:
        try:
            raw = json.dumps(content, ensure_ascii=False, default=str).encode("utf-8")
        except Exception:
            raw = str(content).encode("utf-8")
    if len(raw) < MIN_DOCUMENT_BYTES and not (title or "").strip():
        raise HTTPException(
            status_code=422,
            detail="Documento demasiado pequeño (0 KB). Añade contenido antes de guardar.",
        )


def payment_status_human(status: str) -> str:
    mapping = {
        "registered": "Registrado",
        "completed": "Completado",
        "pending": "Pendiente",
        "paid": "Pagado",
        "open": "Abierto",
        "in_progress": "En curso",
        "closed": "Cerrado",
        "active": "Activo",
        "inactive": "Inactivo",
    }
    return mapping.get((status or "").lower(), status)


def money_str(value: Any) -> str:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"{n:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
