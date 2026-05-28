"""
API de herramientas para los workspaces de los agentes.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import AnyHttpUrl, BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from services.activity_logger import ActivityLogger
from services.workspace_deliverables import persist_workspace_deliverable, primary_company_id_for_user
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
tools_router = APIRouter(prefix="/tools", tags=["tools"])


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


def _persist_tool_output(
    db: Session,
    *,
    current_user: User,
    title: str,
    content: Dict[str, Any],
) -> int:
    doc = persist_workspace_deliverable(
        db,
        user_id=current_user.id,
        company_id=primary_company_id_for_user(db, current_user),
        agent_name="PERSEO",
        workspace_category="marketing_campaign",
        title=title,
        content_type="social_media_post",
        content=content,
        status="draft",
        visible_in_workspace=True,
    )
    return int(doc.id)


def _log_event_chain(
    *,
    current_user: User,
    event_name: str,
    chain_steps: List[str],
    details: Dict[str, Any],
) -> None:
    ActivityLogger.log_activity(
        agent_name="ZEUS CORE",
        action_type=f"event_{event_name}",
        action_description=f"Evento emitido: {event_name}",
        details=details,
        user_email=current_user.email,
        status="completed",
        priority="normal",
        visible_to_client=True,
    )
    for step in chain_steps:
        ActivityLogger.log_activity(
            agent_name="ZEUS CORE",
            action_type="workflow_triggered",
            action_description=f"Workflow disparado: {step}",
            details={"source_event": event_name, "workflow": step, **details},
            user_email=current_user.email,
            status="completed",
            priority="normal",
            visible_to_client=True,
        )


def _text_for_image(result: Dict[str, Any]) -> str:
    dims = result.get("dimensions") or {}
    width = dims.get("width") or 0
    height = dims.get("height") or 0
    ratio = dims.get("aspect_ratio")
    palette = result.get("palette") or []
    insights = result.get("insights") or []
    first_insight = insights[0] if insights else "Añade un CTA claro al inicio."
    return (
        f"Imagen analizada correctamente ({width}x{height}, ratio {ratio}). "
        f"Paleta principal: {', '.join(palette[:3]) if palette else 'no detectada'}. "
        f"Recomendación: {first_insight}"
    )


def _text_for_video(result: Dict[str, Any]) -> str:
    rec = result.get("recommended_duration")
    tone = result.get("tone")
    timeline = result.get("timeline") or []
    return (
        f"Plan de vídeo generado: duración recomendada {rec}s, tono {tone}. "
        f"Se definieron {len(timeline)} bloques narrativos para mejorar retención y CTA final."
    )


def _text_for_seo(result: Dict[str, Any]) -> str:
    score = result.get("score")
    kw = result.get("keyword_score")
    issues = result.get("issues") or []
    issue = issues[0] if issues else "Checklist técnico aprobado."
    return f"Auditoría SEO completada: score {score}/100, cobertura keywords {kw}%. Prioridad inmediata: {issue}"


def _text_for_ads(result: Dict[str, Any]) -> str:
    channels = result.get("channels") or []
    kpis = result.get("kpis") or {}
    kpi_txt = ", ".join([f"{k}={v}" for k, v in kpis.items()]) or "sin KPI"
    return (
        f"Plan de Ads generado con {len(channels)} canales y reparto de presupuesto listo para ejecutar. "
        f"KPIs sugeridos: {kpi_txt}."
    )


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
    current_user: User = Depends(get_current_active_user),
):
    return {"success": True, "result": analyze_perseo_image(request.model_dump(), user_email=current_user.email)}


@router.post("/perseo/video-enhancer")
async def workspace_perseo_video(
    request: PerseoVideoEnhancerRequest,
    current_user: User = Depends(get_current_active_user),
):
    return {"success": True, "result": enhance_perseo_video(request.model_dump(), user_email=current_user.email)}


@router.post("/perseo/seo-audit")
async def workspace_perseo_seo(
    request: PerseoSeoAuditRequest,
    current_user: User = Depends(get_current_active_user),
):
    return {"success": True, "result": run_seo_audit(request.model_dump(), user_email=current_user.email)}


@router.post("/perseo/ads-builder")
async def workspace_perseo_ads(
    request: PerseoAdsBuilderRequest,
    current_user: User = Depends(get_current_active_user),
):
    return {"success": True, "result": build_ads_blueprint(request.model_dump(), user_email=current_user.email)}


@tools_router.post("/analyze-image")
async def tool_analyze_image(
    request: PerseoImageAnalyzerRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    result = analyze_perseo_image(request.model_dump(), user_email=current_user.email)
    text = _text_for_image(result)
    doc_id = _persist_tool_output(
        db,
        current_user=current_user,
        title="Análisis de imagen PERSEO",
        content={"copy": text, "format": "tool_result_text", "result": result},
    )
    _log_event_chain(
        current_user=current_user,
        event_name="image_analyzed",
        chain_steps=["trigger_copywriting_agent"],
        details={"document_id": doc_id},
    )
    return {"success": True, "text": text, "document_id": doc_id}


@tools_router.post("/improve-video")
async def tool_improve_video(
    request: PerseoVideoEnhancerRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    result = enhance_perseo_video(request.model_dump(), user_email=current_user.email)
    text = _text_for_video(result)
    doc_id = _persist_tool_output(
        db,
        current_user=current_user,
        title="Mejora de vídeo PERSEO",
        content={"copy": text, "format": "tool_result_text", "result": result},
    )
    _log_event_chain(
        current_user=current_user,
        event_name="video_recommended",
        chain_steps=["trigger_campaign_builder"],
        details={"document_id": doc_id},
    )
    return {"success": True, "text": text, "document_id": doc_id}


@tools_router.post("/seo-audit")
async def tool_seo_audit(
    request: PerseoSeoAuditRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    result = run_seo_audit(request.model_dump(), user_email=current_user.email)
    text = _text_for_seo(result)
    doc_id = _persist_tool_output(
        db,
        current_user=current_user,
        title="Auditoría SEO PERSEO",
        content={"copy": text, "format": "tool_result_text", "result": result},
    )
    _log_event_chain(
        current_user=current_user,
        event_name="seo_audit_completed",
        chain_steps=["trigger_content_strategy", "trigger_ads_recommendation"],
        details={"document_id": doc_id},
    )
    return {"success": True, "text": text, "document_id": doc_id}


@tools_router.post("/generate-ads-plan")
async def tool_generate_ads_plan(
    request: PerseoAdsBuilderRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    result = build_ads_blueprint(request.model_dump(), user_email=current_user.email)
    text = _text_for_ads(result)
    doc_id = _persist_tool_output(
        db,
        current_user=current_user,
        title="Plan de Ads PERSEO",
        content={"copy": text, "format": "tool_result_text", "result": result},
    )
    _log_event_chain(
        current_user=current_user,
        event_name="ads_plan_generated",
        chain_steps=["trigger_campaign_builder"],
        details={"document_id": doc_id},
    )
    return {"success": True, "text": text, "document_id": doc_id}


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

