"""Normalización de entradas del pipeline unificado de escaneo físico."""

from __future__ import annotations

from typing import Optional, Tuple

SCAN_TYPE_ALIASES = {
    "QR_SCAN": "qr",
    "QR": "qr",
    "NFC_SCAN": "nfc",
    "NFC": "nfc",
    "MRZ_SCAN": "mrz",
    "DNI_SCAN": "mrz",
    "MRZ": "mrz",
    "DNI": "mrz",
}


def normalize_scan_type(raw: str) -> str:
    key = (raw or "").strip()
    upper = key.upper()
    if upper in SCAN_TYPE_ALIASES:
        return SCAN_TYPE_ALIASES[upper]
    lower = key.lower()
    if lower in {"qr", "nfc", "mrz", "dni"}:
        return "dni" if lower == "dni" else lower
    raise ValueError(f"Tipo de escaneo no soportado: {raw}")


def normalize_text_payload(value: Optional[str]) -> str:
    return (value or "").strip()


def normalize_nfc_payload(
    text: Optional[str],
    payload_hex: Optional[str],
) -> Tuple[str, Optional[str]]:
    cleaned_text = normalize_text_payload(text)
    cleaned_hex = normalize_text_payload(payload_hex) or None
    if cleaned_text:
        return cleaned_text, cleaned_hex
    if cleaned_hex:
        return "", cleaned_hex
    return "", None
