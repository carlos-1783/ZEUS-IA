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


def _text_generic(prefix: str, result: Dict[str, Any]) -> str:
    keys = list(result.keys())[:4]
    ktxt = ", ".join(keys) if keys else "sin detalles"
    return f"{prefix} completado correctamente. Resultado validado ({ktxt})."


def _text_scan_flow(flow: Dict[str, Any], *, label: str) -> str:
    if flow.get("needs_approval"):
        return (
            f"{label}: acción registrada, pendiente de aprobación humana "
            f"(ID {flow.get('approval_id')}). {flow.get('message', '')}"
        )
    parts = [str(flow.get("message") or f"{label} ejecutado en producción.")]
    if flow.get("customer_id"):
        parts.append(f"Cliente ID {flow['customer_id']}.")
    if flow.get("invoice_id"):
        parts.append(f"Factura ID {flow['invoice_id']}.")
    if flow.get("cashflow_updated"):
        parts.append("Cashflow actualizado.")
    if flow.get("lead_score") is not None:
        parts.append(f"Score {flow['lead_score']}.")
    if flow.get("employee_id"):
        parts.append(f"Empleado {flow['employee_id']}, fichaje {flow.get('checkin_type', 'ok')}.")
    if flow.get("scan_event_id"):
        parts.append(f"Evento scan #{flow['scan_event_id']} persistido.")
    return " ".join(parts)


def _decode_hex_payload(payload_hex: str) -> str:
    try:
        return bytes.fromhex(payload_hex.strip()).decode("utf-8", errors="ignore").strip()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="payload_hex NFC inválido.") from exc


def _persist_agent_tool_response(
    db: Session,
    *,
    current_user: User,
    agent_name: str,
    workspace_category: str,
    content_type: str,
    title: str,
    text: str,
    result: Dict[str, Any],
    event_name: str,
    chain_steps: List[str],
) -> Dict[str, Any]:
    doc = persist_workspace_deliverable(
        db,
        user_id=current_user.id,
        company_id=primary_company_id_for_user(db, current_user),
        agent_name=agent_name,
        workspace_category=workspace_category,
        title=title,
        content_type=content_type,
        content={"copy": text, "format": "tool_result_text", "result": result},
        status="draft",
        visible_in_workspace=True,
    )
    _log_event_chain(
        current_user=current_user,
        event_name=event_name,
        chain_steps=chain_steps,
        details={"document_id": int(doc.id), "agent_name": agent_name},
    )
    return {"success": True, "text": text, "document_id": int(doc.id), "result": result}


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
    company_id: Optional[int] = None
    year: Optional[int] = None
    quarter: Optional[int] = Field(default=None, ge=1, le=4)
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
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    from services.scan_flow_service_v1 import process_qr_scan

    flow = process_qr_scan(db, current_user, data=request.data.strip())
    text = _text_scan_flow(flow, label="Lectura QR fiscal")
    return _persist_agent_tool_response(
        db,
        current_user=current_user,
        agent_name="RAFAEL",
        workspace_category="fiscal_document",
        content_type="fiscal_document",
        title="Lectura QR RAFAEL",
        text=text,
        result=flow,
        event_name="qr_scan_detected",
        chain_steps=["create_or_update_customer", "generate_invoice", "update_cashflow"],
    )


@router.post("/rafael/nfc-scanner")
async def workspace_rafael_nfc(
    request: RafaelNfcRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    from services.scan_flow_service_v1 import process_nfc_scan, process_qr_scan

    decoded = _decode_hex_payload(request.payload_hex) if request.payload_hex else ""
    if decoded.upper().startswith(("ZEUS|", "ZEUSQR|")):
        flow = process_qr_scan(db, current_user, data=decoded)
        label = "Lectura NFC→QR fiscal"
    elif decoded.upper().startswith("ZEUSCHECK|"):
        flow = process_nfc_scan(db, current_user, text=decoded, payload_hex=request.payload_hex)
        label = "Fichaje NFC"
    else:
        flow = process_nfc_scan(
            db,
            current_user,
            text=decoded or None,
            payload_hex=request.payload_hex,
        )
        label = "Lectura NFC"
    text = _text_scan_flow(flow, label=label)
    return _persist_agent_tool_response(
        db,
        current_user=current_user,
        agent_name="RAFAEL",
        workspace_category="fiscal_document",
        content_type="fiscal_document",
        title="Lectura NFC RAFAEL",
        text=text,
        result=flow,
        event_name="nfc_detected",
        chain_steps=["checkin_or_link", "update_cashflow"],
    )


@router.post("/rafael/dni-ocr")
async def workspace_rafael_dni(
    request: RafaelDniRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    from services.scan_flow_service_v1 import process_dni_scan

    flow = process_dni_scan(db, current_user, mrz=request.mrz.strip())
    text = _text_scan_flow(flow, label="Parser DNIe")
    return _persist_agent_tool_response(
        db,
        current_user=current_user,
        agent_name="RAFAEL",
        workspace_category="fiscal_document",
        content_type="fiscal_document",
        title="Parser DNIe RAFAEL",
        text=text,
        result=flow,
        event_name="dni_detected",
        chain_steps=["crm.create_customer", "assign_score", "schedule_followup"],
    )


@router.post("/rafael/forms")
async def workspace_rafael_forms(
    request: RafaelFormsRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    from datetime import datetime

    import services.crm_office_service as crm_svc
    from services.rafael_fiscal_engine_v2 import generate_model_303_flow

    payload = request.model_dump()
    company_id = payload.get("company_id") or crm_svc.primary_company_id(db, current_user)
    year = payload.get("year") or datetime.utcnow().year
    quarter = payload.get("quarter") or ((datetime.utcnow().month - 1) // 3 + 1)

    if company_id:
        result = generate_model_303_flow(
            db,
            user=current_user,
            company_id=int(company_id),
            year=int(year),
            quarter=int(quarter),
        )
        text = (
            f"Modelo 303 {result.get('modelo_303', {}).get('period', '')} generado. "
            f"IVA devengado: {result.get('modelo_303', {}).get('iva_devengado', 0)} €. "
            f"Resultado: {result.get('modelo_303', {}).get('resultado', 0)} €. "
            f"Archivo: {result.get('file_size', 0)} bytes."
        )
        return {
            "success": True,
            "text": text,
            "document_id": result.get("document_id"),
            "file_url": result.get("file_url"),
            "file_size": result.get("file_size"),
            "result": result,
        }

    result = generate_fiscal_forms(payload)
    text = _text_generic("Generación de modelos fiscales (borrador manual)", result)
    return _persist_agent_tool_response(
        db,
        current_user=current_user,
        agent_name="RAFAEL",
        workspace_category="fiscal_document",
        content_type="fiscal_document",
        title="Modelos fiscales RAFAEL",
        text=text,
        result=result,
        event_name="rafael_forms_generated",
        chain_steps=["trigger_tax_review"],
    )


# ---------------------------------------------------------------------------
# JUSTICIA tools
# ---------------------------------------------------------------------------


@router.post("/justicia/pdf-signer")
async def workspace_justicia_signer(
    request: JusticiaSignerRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    result = sign_pdf_document(request.model_dump())
    text = _text_generic("Firma digital", result)
    return _persist_agent_tool_response(
        db,
        current_user=current_user,
        agent_name="JUSTICIA",
        workspace_category="legal_document",
        content_type="legal_document",
        title="Firma digital JUSTICIA",
        text=text,
        result=result,
        event_name="justicia_pdf_signed",
        chain_steps=["trigger_legal_archive"],
    )


@router.post("/justicia/contract")
async def workspace_justicia_contract(
    request: JusticiaContractRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    result = generate_contract_kit(request.model_dump())
    text = _text_generic("Generación de contrato legal", result)
    return _persist_agent_tool_response(
        db,
        current_user=current_user,
        agent_name="JUSTICIA",
        workspace_category="legal_document",
        content_type="legal_document",
        title="Contrato JUSTICIA",
        text=text,
        result=result,
        event_name="justicia_contract_generated",
        chain_steps=["trigger_compliance_review"],
    )


@router.post("/justicia/gdpr-audit")
async def workspace_justicia_gdpr(
    request: JusticiaGdprRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    result = run_gdpr_audit(request.model_dump())
    text = _text_generic("Auditoría GDPR", result)
    return _persist_agent_tool_response(
        db,
        current_user=current_user,
        agent_name="JUSTICIA",
        workspace_category="legal_document",
        content_type="legal_document",
        title="Auditoría GDPR JUSTICIA",
        text=text,
        result=result,
        event_name="justicia_gdpr_audited",
        chain_steps=["trigger_compliance_review"],
    )


# ---------------------------------------------------------------------------
# THALOS tools
# ---------------------------------------------------------------------------


@router.post("/thalos/log-monitor")
async def workspace_thalos_logs(
    request: ThalosLogRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    result = monitor_security_logs(request.model_dump())
    text = _text_generic("Monitor de logs de seguridad", result)
    return _persist_agent_tool_response(
        db,
        current_user=current_user,
        agent_name="THALOS",
        workspace_category="legal_document",
        content_type="legal_document",
        title="Monitor de logs THALOS",
        text=text,
        result=result,
        event_name="thalos_logs_monitored",
        chain_steps=["trigger_security_followup"],
    )


@router.post("/thalos/threat-detector")
async def workspace_thalos_threat(
    request: ThalosThreatRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    result = detect_threat_events(request.model_dump())
    text = _text_generic("Detección de amenazas", result)
    return _persist_agent_tool_response(
        db,
        current_user=current_user,
        agent_name="THALOS",
        workspace_category="legal_document",
        content_type="legal_document",
        title="Detección de amenazas THALOS",
        text=text,
        result=result,
        event_name="thalos_threat_detected",
        chain_steps=["trigger_security_followup"],
    )


@router.post("/thalos/credential-revoker")
async def workspace_thalos_credentials(
    request: ThalosCredentialRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    result = revoke_credentials(request.model_dump())
    text = _text_generic("Revocación de credenciales", result)
    return _persist_agent_tool_response(
        db,
        current_user=current_user,
        agent_name="THALOS",
        workspace_category="legal_document",
        content_type="legal_document",
        title="Revocación de credenciales THALOS",
        text=text,
        result=result,
        event_name="thalos_credentials_revoked",
        chain_steps=["trigger_security_followup"],
    )


# ---------------------------------------------------------------------------
# AFRODITA tools
# ---------------------------------------------------------------------------


@router.post("/afrodita/face-check-in")
async def workspace_afrodita_face(
    request: AfroditaFaceRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    result = record_face_check_in(request.model_dump())
    text = _text_generic("Fichaje facial", result)
    return _persist_agent_tool_response(
        db,
        current_user=current_user,
        agent_name="AFRODITA",
        workspace_category="hr_document",
        content_type="hr_document",
        title="Fichaje facial AFRODITA",
        text=text,
        result=result,
        event_name="afrodita_face_checkin",
        chain_steps=["trigger_shift_validation"],
    )


@router.post("/afrodita/qr-check-in")
async def workspace_afrodita_qr(
    request: AfroditaQrRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    from services.scan_flow_service_v1 import process_nfc_scan, process_qr_scan

    code = (request.qr_code or "").strip()
    if code.upper().startswith(("ZEUS|", "ZEUSQR|")):
        flow = process_qr_scan(db, current_user, data=code)
    else:
        flow = process_nfc_scan(db, current_user, text=code, checkin_type="entrada")
    text = _text_scan_flow(flow, label="Fichaje QR/NFC")
    return _persist_agent_tool_response(
        db,
        current_user=current_user,
        agent_name="AFRODITA",
        workspace_category="hr_document",
        content_type="hr_document",
        title="Fichaje QR AFRODITA",
        text=text,
        result=flow,
        event_name="nfc_detected",
        chain_steps=["checkin_employee", "calculate_cost"],
    )


@router.post("/afrodita/employee-manager")
async def workspace_afrodita_schedule(
    request: AfroditaScheduleRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    result = build_employee_schedule(request.model_dump())
    text = _text_generic("Generación de turnos", result)
    return _persist_agent_tool_response(
        db,
        current_user=current_user,
        agent_name="AFRODITA",
        workspace_category="hr_document",
        content_type="hr_document",
        title="Turnos AFRODITA",
        text=text,
        result=result,
        event_name="afrodita_schedule_generated",
        chain_steps=["trigger_hr_sync"],
    )


@router.post("/afrodita/contract")
async def workspace_afrodita_contract(
    request: AfroditaContractRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    result = create_rrhh_contract(request.model_dump())
    text = _text_generic("Contrato RRHH", result)
    return _persist_agent_tool_response(
        db,
        current_user=current_user,
        agent_name="AFRODITA",
        workspace_category="hr_document",
        content_type="hr_document",
        title="Contrato RRHH AFRODITA",
        text=text,
        result=result,
        event_name="afrodita_contract_generated",
        chain_steps=["trigger_hr_sync"],
    )


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

