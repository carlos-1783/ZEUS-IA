"""PERSEO v1 API — audit, status, video edit."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from services.perseo_audit_service_v1 import build_audit_report, build_feature_status_map
from services.perseo_video_engine_v1 import create_video_edit_job, get_video_job
from services.perseo_video_engine_v3 import ENGINE_VERSION as V3_VERSION, generate_perseo_video_v3
from services.perseo_video_pro_engine_v4 import ENGINE_VERSION as V4_VERSION, generate_perseo_video_pro_v4
from services.zeus_execution_controller_v1 import get_execution_status

router = APIRouter(prefix="/perseo", tags=["perseo"])


class VideoEditOperation(BaseModel):
    type: str
    start_sec: Optional[float] = None
    end_sec: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None


class VideoEditRequest(BaseModel):
    input_url: str = Field(..., min_length=1)
    operations: List[VideoEditOperation] = Field(default_factory=list)
    transaction_id: Optional[str] = None


class VideoBranding(BaseModel):
    logo: Optional[str] = None
    primary_color: Optional[str] = None
    font_style: Optional[str] = None


class VideoProBranding(BaseModel):
    logo: Optional[str] = None
    primary_color: Optional[str] = None
    font_style: Optional[str] = None


class VideoProGenerateRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1)
    image_url: str = Field(..., min_length=1)
    product_info: Optional[str] = None
    branding: Optional[VideoProBranding] = None
    platform: str = "meta_ads"
    lead_id: Optional[int] = None
    campaign_id: Optional[str] = None
    customer_id: Optional[int] = None
    enable_audio: bool = True
    enable_voiceover: bool = True


class VideoGenerateRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1)
    image_url: str = Field(..., min_length=1)
    product_info: Optional[str] = None
    branding: Optional[VideoBranding] = None
    lead_id: Optional[int] = None
    campaign_id: Optional[str] = None
    customer_id: Optional[int] = None


@router.get("/status")
def perseo_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ = current_user
    execution = get_execution_status(db)
    features = build_feature_status_map(db)
    return {
        "success": True,
        "agent": "PERSEO",
        "execution_mode": execution["execution_mode"],
        "writes_enabled": execution["writes_enabled"],
        "feature_status_map": features,
        "zeus_module": "PERSEO",
    }


@router.get("/audit")
def perseo_audit(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ = current_user
    return {"success": True, **build_audit_report(db)}


@router.post("/video/generate")
def perseo_video_generate(
    body: VideoGenerateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """PERSEO Video Engine v3 — imagen + copy conversión → MP4 vertical 15s (FFmpeg real)."""
    branding = body.branding.model_dump(exclude_none=True) if body.branding else None
    result = generate_perseo_video_v3(
        db,
        current_user,
        tenant_id=body.tenant_id,
        image_url=body.image_url,
        product_info=body.product_info,
        branding=branding,
        lead_id=body.lead_id,
        campaign_id=body.campaign_id,
        customer_id=body.customer_id,
    )
    return result


@router.get("/video/engine")
def perseo_video_engine_info(
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    _ = current_user
    from services.perseo_video_engine_v3 import video_engine_v3_configured

    return {
        "success": True,
        "engine": "perseo_video_engine_v3",
        "version": V3_VERSION,
        "endpoint": "POST /api/v1/perseo/video/generate",
        "configured": video_engine_v3_configured(),
        "execution": "real",
        "tool": "ffmpeg",
    }


@router.post("/video-pro/generate")
def perseo_video_pro_generate(
    body: VideoProGenerateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """PERSEO Video Pro Engine v4 — anuncios performance 9:16 con motion, audio y preview GIF."""
    branding = body.branding.model_dump(exclude_none=True) if body.branding else None
    return generate_perseo_video_pro_v4(
        db,
        current_user,
        tenant_id=body.tenant_id,
        image_url=body.image_url,
        product_info=body.product_info,
        branding=branding,
        platform=body.platform,
        lead_id=body.lead_id,
        campaign_id=body.campaign_id,
        customer_id=body.customer_id,
        enable_audio=body.enable_audio,
        enable_voiceover=body.enable_voiceover,
    )


@router.get("/video-pro/engine")
def perseo_video_pro_engine_info(
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    _ = current_user
    from services.perseo_video_pro_engine_v4 import video_pro_engine_v4_configured

    return {
        "success": True,
        "engine": "perseo_video_pro_engine_v4",
        "version": V4_VERSION,
        "endpoint": "POST /api/v1/perseo/video-pro/generate",
        "configured": video_pro_engine_v4_configured(),
        "mode": "production_pro",
        "tool": "ffmpeg",
    }


@router.post("/video/edit")
def perseo_video_edit(
    body: VideoEditRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    ops = [o.model_dump(exclude_none=True) for o in body.operations]
    result = create_video_edit_job(
        db,
        current_user,
        input_url=body.input_url,
        operations=ops or None,
        transaction_id=body.transaction_id,
    )
    return {"success": True, **result}


@router.get("/video/jobs/{job_id}")
def perseo_video_job_status(
    job_id: str,
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    job = get_video_job(job_id, current_user.id)
    return {"success": job["status"] == "completed", **job}
