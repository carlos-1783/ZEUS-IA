"""
Herramientas de workspace para RAFAEL.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from services.mrz_parser_v1 import parse_mrz

from .base import log_tool_execution


def read_qr_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Interpretar datos codificados en QR textual."""
    raw = payload.get("data", "")
    parts = raw.split("|")
    parsed = {
        "raw": raw,
        "customer": parts[1] if len(parts) > 1 else payload.get("customer"),
        "amount": float(parts[2]) if len(parts) > 2 and parts[2].isdigit() else payload.get("amount", 0.0),
        "currency": parts[3] if len(parts) > 3 else "EUR",
        "timestamp": parts[4] if len(parts) > 4 else datetime.utcnow().isoformat(),
    }
    log_tool_execution("RAFAEL", "qr_reader", "QR analizado", {"payload": payload, "parsed": parsed})
    return parsed


def scan_nfc_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Decodificar contenido hexadecimal proveniente de una etiqueta NFC."""
    hex_data = payload.get("payload_hex", "")
    try:
        decoded = bytes.fromhex(hex_data).decode("utf-8", errors="ignore")
    except ValueError:
        decoded = ""
    result = {
        "tag_type": payload.get("tag_type", "NDEF"),
        "decoded_text": decoded,
        "bytes": len(hex_data) // 2,
    }
    log_tool_execution("RAFAEL", "nfc_scanner", "NFC leído", {"payload": payload, "result": result})
    return result


def parse_dnie_mrz(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Parsear MRZ de DNIe usando el parser central (TD1/TD2)."""
    raw_mrz = payload.get("mrz", "")
    result = parse_mrz(raw_mrz)
    log_tool_execution("RAFAEL", "dni_ocr_parser", "MRZ parseado", {"mrz": raw_mrz, "result": result})
    return result


def generate_fiscal_forms(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Crear borrador de modelos fiscales."""
    revenue = float(payload.get("revenue", 0))
    expenses = float(payload.get("expenses", 0))
    iva_type = float(payload.get("iva_type", 21))

    iva_due = max(revenue * iva_type / 100 - expenses * 0.1, 0)
    modelo_303 = {
        "base_imponible": round(revenue, 2),
        "cuota": round(iva_due, 2),
        "status": "ready",
    }
    modelo_390 = {
        "annual_revenue_projection": round(revenue * 4, 2),
        "annual_tax_projection": round(iva_due * 4, 2),
    }
    result = {
        "modelo_303": modelo_303,
        "modelo_390": modelo_390,
        "cashflow_alert": "Ingreso < gastos" if revenue < expenses else None,
    }
    log_tool_execution(
        "RAFAEL",
        "fiscal_forms_generator",
        "Modelos fiscales generados",
        {"payload": payload, "result": result},
        metrics={"iva_due": iva_due},
    )
    return result

