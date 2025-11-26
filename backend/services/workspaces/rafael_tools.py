"""
Herramientas de workspace para RAFAEL.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

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
    """Parsear MRZ de DNIe (2 líneas)."""
    mrz = payload.get("mrz", "").splitlines()
    if len(mrz) < 2:
        raise ValueError("MRZ incompleto")
    line1, line2 = mrz[0], mrz[1]
    document_number = line1[5:14].replace("<", "")
    birth_date = line2[0:6]
    expiry = line2[8:14]
    result = {
        "document_number": document_number,
        "birth_date": f"20{birth_date[0:2]}-{birth_date[2:4]}-{birth_date[4:6]}",
        "expiry_date": f"20{expiry[0:2]}-{expiry[2:4]}-{expiry[4:6]}",
        "nationality": line2[15:18].replace("<", ""),
    }
    log_tool_execution("RAFAEL", "dni_ocr_parser", "MRZ parseado", {"mrz": mrz, "result": result})
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

