"""
API de herramientas para los workspaces de los agentes.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import AnyHttpUrl, BaseModel, Field

from app.core.auth import get_current_active_user
from app.core.config import settings
from app.models.user import User
from services.workspaces import (
    analyze_perseo_image,
    enhance_perseo_video,
    run_seo_audit,
    build_ads_blueprint,
    read_qr_payload,
    scan_nfc_payload,
    parse_dnie_mrz,
    generate_fiscal_forms,
    sign_pdf_document,
    generate_contract_kit,
    run_gdpr_audit,
    monitor_security_logs,
    detect_threat_events,
    revoke_credentials,
    record_face_check_in,
    handle_qr_check_in,
    build_employee_schedule,
    create_rrhh_contract,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class PerseoImageAnalyzerRequest(BaseModel):
    image_url: Optional[AnyHttpUrl] = None
    goals: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class PerseoVideoEnhancerRequest(BaseModel):
    duration_seconds: int = 45
    tone: str = "energético"
    platform: str = "meta"


class PerseoSeoAuditRequest(BaseModel):
    url: Optional[AnyHttpUrl] = None
    keywords: List[str] = Field(default_factory=list)
    html_snapshot: Optional[str] = None


class PerseoAdsBuilderRequest(BaseModel):
    product: str
    budget: float = 1000
    audience: str = "general"
    objective: str = "leads"


class RafaelQrRequest(BaseModel):
    data: str
    customer: Optional[str] = None
    amount: Optional[float] = None


class RafaelNfcRequest(BaseModel):
    payload_hex: str
    tag_type: str = "NDEF"


class RafaelDniRequest(BaseModel):
    mrz: str


class RafaelFormsRequest(BaseModel):
    revenue: float = 0
    expenses: float = 0
    iva_type: float = 21


class JusticiaSignerRequest(BaseModel):
    document_name: str
    file_hash: str
    signer: Optional[str] = "JUSTICIA"


class JusticiaContractRequest(BaseModel):
    parties: List[str] = Field(default_factory=list)
    scope: str = "servicios"
    media_buying: bool = False


class JusticiaGdprRequest(BaseModel):
    systems: List[str] = Field(default_factory=list)
    data_flows: List[str] = Field(default_factory=list)


class ThalosLogRequest(BaseModel):
    logs: List[str] = Field(default_factory=list)


class ThalosThreatRequest(BaseModel):
    events: List[Dict[str, Any]] = Field(default_factory=list)


class ThalosCredentialRequest(BaseModel):
    credential_ids: List[str]


class AfroditaFaceRequest(BaseModel):
    employee_id: str
    embedding: List[float] = Field(default_factory=list)
    timestamp: Optional[str] = None


class AfroditaQrRequest(BaseModel):
    qr_code: str


class AfroditaScheduleRequest(BaseModel):
    employees: List[Dict[str, Any]] = Field(default_factory=list)
    week: Optional[str] = None


class AfroditaContractRequest(BaseModel):
    employee_name: str
    role: str
    salary: float
    contract_type: str = "indefinido"


# ---------------------------------------------------------------------------
# PERSEO tools
# ---------------------------------------------------------------------------


@router.post("/perseo/image-analyzer")
async def workspace_perseo_image(
    request: PerseoImageAnalyzerRequest,
    _: User = Depends(get_current_active_user),
):
    return {"success": True, "result": analyze_perseo_image(request.model_dump())}


@router.post("/perseo/video-enhancer")
async def workspace_perseo_video(
    request: PerseoVideoEnhancerRequest,
    _: User = Depends(get_current_active_user),
):
    return {"success": True, "result": enhance_perseo_video(request.model_dump())}


@router.post("/perseo/seo-audit")
async def workspace_perseo_seo(
    request: PerseoSeoAuditRequest,
    _: User = Depends(get_current_active_user),
):
    return {"success": True, "result": run_seo_audit(request.model_dump())}


@router.post("/perseo/ads-builder")
async def workspace_perseo_ads(
    request: PerseoAdsBuilderRequest,
    _: User = Depends(get_current_active_user),
):
    return {"success": True, "result": build_ads_blueprint(request.model_dump())}


# ---------------------------------------------------------------------------
# RAFAEL tools
# ---------------------------------------------------------------------------


@router.post("/rafael/qr-reader")
async def workspace_rafael_qr(
    request: RafaelQrRequest,
    _: User = Depends(get_current_active_user),
):
    return {"success": True, "result": read_qr_payload(request.model_dump())}


@router.post("/rafael/nfc-scanner")
async def workspace_rafael_nfc(
    request: RafaelNfcRequest,
    _: User = Depends(get_current_active_user),
):
    return {"success": True, "result": scan_nfc_payload(request.model_dump())}


@router.post("/rafael/dni-ocr")
async def workspace_rafael_dni(
    request: RafaelDniRequest,
    _: User = Depends(get_current_active_user),
):
    return {"success": True, "result": parse_dnie_mrz(request.model_dump())}


@router.post("/rafael/forms")
async def workspace_rafael_forms(
    request: RafaelFormsRequest,
    _: User = Depends(get_current_active_user),
):
    return {"success": True, "result": generate_fiscal_forms(request.model_dump())}


# ---------------------------------------------------------------------------
# JUSTICIA tools
# ---------------------------------------------------------------------------


@router.post("/justicia/pdf-signer")
async def workspace_justicia_signer(
    request: JusticiaSignerRequest,
    _: User = Depends(get_current_active_user),
):
    return {"success": True, "result": sign_pdf_document(request.model_dump())}


@router.post("/justicia/contract")
async def workspace_justicia_contract(
    request: JusticiaContractRequest,
    _: User = Depends(get_current_active_user),
):
    return {"success": True, "result": generate_contract_kit(request.model_dump())}


@router.post("/justicia/gdpr-audit")
async def workspace_justicia_gdpr(
    request: JusticiaGdprRequest,
    _: User = Depends(get_current_active_user),
):
    return {"success": True, "result": run_gdpr_audit(request.model_dump())}


# ---------------------------------------------------------------------------
# THALOS tools
# ---------------------------------------------------------------------------


@router.post("/thalos/log-monitor")
async def workspace_thalos_logs(
    request: ThalosLogRequest,
    _: User = Depends(get_current_active_user),
):
    return {"success": True, "result": monitor_security_logs(request.model_dump())}


@router.post("/thalos/threat-detector")
async def workspace_thalos_threat(
    request: ThalosThreatRequest,
    _: User = Depends(get_current_active_user),
):
    return {"success": True, "result": detect_threat_events(request.model_dump())}


@router.post("/thalos/credential-revoker")
async def workspace_thalos_credentials(
    request: ThalosCredentialRequest,
    _: User = Depends(get_current_active_user),
):
    return {"success": True, "result": revoke_credentials(request.model_dump())}


# ---------------------------------------------------------------------------
# AFRODITA tools
# ---------------------------------------------------------------------------


@router.post("/afrodita/face-check-in")
async def workspace_afrodita_face(
    request: AfroditaFaceRequest,
    _: User = Depends(get_current_active_user),
):
    return {"success": True, "result": record_face_check_in(request.model_dump())}


@router.post("/afrodita/qr-check-in")
async def workspace_afrodita_qr(
    request: AfroditaQrRequest,
    _: User = Depends(get_current_active_user),
):
    return {"success": True, "result": handle_qr_check_in(request.model_dump())}


@router.post("/afrodita/employee-manager")
async def workspace_afrodita_schedule(
    request: AfroditaScheduleRequest,
    _: User = Depends(get_current_active_user),
):
    return {"success": True, "result": build_employee_schedule(request.model_dump())}


@router.post("/afrodita/contract")
async def workspace_afrodita_contract(
    request: AfroditaContractRequest,
    _: User = Depends(get_current_active_user),
):
    return {"success": True, "result": create_rrhh_contract(request.model_dump())}


# ---------------------------------------------------------------------------
# Uploads
# ---------------------------------------------------------------------------

UPLOAD_WHITELIST = {
    "imagenes": {"image/jpeg", "image/png", "image/webp"},
    "videos": {"video/mp4", "video/webm", "video/quicktime"},
    "documentos": {"application/pdf", "text/plain"},
}


@router.post("/uploads/{category}")
async def workspace_upload(
    category: str,
    file: UploadFile = File(...),
    _: User = Depends(get_current_active_user),
):
    cat = category.lower()
    if cat not in UPLOAD_WHITELIST:
        raise HTTPException(status_code=400, detail="Categoría no soportada")
    if file.content_type not in UPLOAD_WHITELIST[cat]:
        raise HTTPException(
            status_code=415,
            detail=f"Formato no permitido para {cat}.",
        )

    upload_root = Path(settings.STATIC_DIR) / "uploads" / cat
    upload_root.mkdir(parents=True, exist_ok=True)
    filename = f"{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}_{file.filename}"
    destination = upload_root / filename

    contents = await file.read()
    destination.write_bytes(contents)

    return {
        "success": True,
        "filename": filename,
        "content_type": file.content_type,
        "size_bytes": len(contents),
        "url": f"{settings.STATIC_URL.rstrip('/')}/uploads/{cat}/{filename}",
    }

