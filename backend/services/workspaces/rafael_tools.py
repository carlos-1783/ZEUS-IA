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
