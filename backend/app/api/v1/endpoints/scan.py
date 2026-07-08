"""Scan endpoints — zeus_full_real_flow_v3 + unified ingest v2."""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from services.dni_mrz_ocr_v1 import extract_mrz_from_image_base64
from services.scan_flow_service_v1 import process_dni_scan, process_nfc_scan, process_qr_scan
from services.scan_ingest_v1 import ingest_physical_scan

router = APIRouter()


class QrScanRequest(BaseModel):
    data: str = Field(..., min_length=1, description="Contenido decodificado del QR")
    company_id: Optional[int] = None
    force_execute: bool = False


class NfcScanRequest(BaseModel):
    text: Optional[str] = Field(None, description="Texto NDEF decodificado")
    payload_hex: Optional[str] = Field(None, description="Payload hexadecimal NFC")
    company_id: Optional[int] = None
    employee_id: Optional[str] = None
    checkin_type: str = Field("entrada", description="entrada|salida|pausa_inicio|pausa_fin")


class DniScanRequest(BaseModel):
    mrz: str = Field(..., min_length=20, description="Líneas MRZ del DNIe")
    company_id: Optional[int] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class DniImageScanRequest(BaseModel):
    image_base64: str = Field(..., min_length=32, description="Imagen del reverso del DNI (base64)")
    company_id: Optional[int] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class ScanIngestRequest(BaseModel):
    scan_type: Literal["QR_SCAN", "NFC_SCAN", "MRZ_SCAN", "qr", "nfc", "mrz", "dni"]
    payload: Optional[str] = Field(None, description="Texto QR/NFC/MRZ")
    payload_hex: Optional[str] = Field(None, description="Payload hex NFC")
    image_base64: Optional[str] = Field(None, description="Imagen DNI para OCR")
    company_id: Optional[int] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    employee_id: Optional[str] = None
    checkin_type: str = "entrada"
    force_execute: bool = False


@router.post("/ingest")
def scan_ingest(
    body: ScanIngestRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Pipeline unificado: QR_SCAN | NFC_SCAN | MRZ_SCAN."""
    return ingest_physical_scan(
        db,
        current_user,
        scan_type=body.scan_type,
        payload=body.payload,
        payload_hex=body.payload_hex,
        image_base64=body.image_base64,
        company_id=body.company_id,
        email=body.email,
        phone=body.phone,
        checkin_type=body.checkin_type,
        employee_id=body.employee_id,
        force_execute=body.force_execute,
    )


@router.post("/qr")
def scan_qr(
    body: QrScanRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """QR → cliente / factura / cashflow (RAFAEL) o fichaje (AFRODITA)."""
    return process_qr_scan(
        db,
        current_user,
        data=body.data,
        company_id=body.company_id,
        force_execute=body.force_execute,
    )


@router.post("/nfc")
def scan_nfc(
    body: NfcScanRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """NFC → fichaje real + coste laboral (AFRODITA)."""
    return process_nfc_scan(
        db,
        current_user,
        text=body.text,
        payload_hex=body.payload_hex,
        company_id=body.company_id,
        checkin_type=body.checkin_type,
        employee_id=body.employee_id,
    )


@router.post("/dni")
def scan_dni(
    body: DniScanRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """DNI MRZ → cliente CRM + scoring (ZEUS)."""
    return process_dni_scan(
        db,
        current_user,
        mrz=body.mrz,
        company_id=body.company_id,
        email=body.email,
        phone=body.phone,
    )


@router.post("/dni-image")
def scan_dni_image(
    body: DniImageScanRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Captura imagen DNI → OCR MRZ → alta cliente."""
    mrz = extract_mrz_from_image_base64(body.image_base64)
    out = process_dni_scan(
        db,
        current_user,
        mrz=mrz,
        company_id=body.company_id,
        email=body.email,
        phone=body.phone,
    )
    return {**out, "mrz_extracted": mrz, "ocr": True}
