"""Pipeline unificado de escaneo físico — ZEUS IA v2."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.user import User
from services.dni_mrz_ocr_v1 import extract_mrz_from_image_base64
from services.scan_flow_service_v1 import process_dni_scan, process_nfc_scan, process_qr_scan
from services.scan_normalizer_v1 import normalize_nfc_payload, normalize_scan_type, normalize_text_payload


def ingest_physical_scan(
    db: Session,
    user: User,
    *,
    scan_type: str,
    payload: Optional[str] = None,
    payload_hex: Optional[str] = None,
    image_base64: Optional[str] = None,
    company_id: Optional[int] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    checkin_type: str = "entrada",
    employee_id: Optional[str] = None,
    force_execute: bool = False,
) -> Dict[str, Any]:
    """
    Entrada canónica: capture_data → normalize → validate → process.
    scan_type: QR_SCAN | NFC_SCAN | MRZ_SCAN (alias qr/nfc/mrz/dni).
    """
    kind = normalize_scan_type(scan_type)
    normalized_email = normalize_text_payload(email) or None
    normalized_phone = normalize_text_payload(phone) or None

    if kind == "qr":
        data = normalize_text_payload(payload)
        if not data:
            raise HTTPException(status_code=422, detail="Payload QR vacío.")
        out = process_qr_scan(
            db,
            user,
            data=data,
            company_id=company_id,
            force_execute=force_execute,
        )
        return {**out, "pipeline": "QR_SCAN", "normalized": True}

    if kind == "nfc":
        text, hex_payload = normalize_nfc_payload(payload, payload_hex)
        if not text and not hex_payload:
            raise HTTPException(status_code=422, detail="Payload NFC vacío.")
        out = process_nfc_scan(
            db,
            user,
            text=text or None,
            payload_hex=hex_payload,
            company_id=company_id,
            checkin_type=checkin_type,
            employee_id=employee_id,
        )
        return {**out, "pipeline": "NFC_SCAN", "normalized": True}

    mrz = normalize_text_payload(payload)
    ocr_relaxed = False
    if not mrz and image_base64:
        mrz = extract_mrz_from_image_base64(image_base64)
        ocr_relaxed = True
    elif image_base64:
        ocr_relaxed = True
    if not mrz:
        raise HTTPException(status_code=422, detail="MRZ requerido (texto o imagen).")
    out = process_dni_scan(
        db,
        user,
        mrz=mrz,
        company_id=company_id,
        email=normalized_email,
        phone=normalized_phone,
        ocr_relaxed=ocr_relaxed,
    )
    mrz_source = "ocr" if image_base64 and not normalize_text_payload(payload) else "text"
    return {**out, "pipeline": "MRZ_SCAN", "normalized": True, "mrz_source": mrz_source}
