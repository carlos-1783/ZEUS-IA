"""PERSEO v2 API — transactional marketing engines."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from services.perseo_ads_engine_v2 import create_ad_campaign, _meta_configured, _google_configured
from services.perseo_ai_service_v2 import (
    analyze_image_ai,
    generate_ads_ai,
    openai_configured,
    recommend_video_ai,
    seo_audit_ai,
)
from services.perseo_analytics_v2 import fetch_analytics
from services.perseo_audit_service_v1 import build_audit_report
from services.perseo_image_engine_v2 import create_image_generation_job, _provider_configured
from services.perseo_job_queue_v1 import count_jobs_by_status, get_job
from services.perseo_pipeline_v2 import pipeline_status, run_pipeline
from services.perseo_publishing_v1 import publish_post, _instagram_configured
from services.perseo_storage_v2 import s3_configured, storage_backend
from services.perseo_video_engine_v2 import create_video_edit_job_v2
from services.perseo_video_gen_engine_v2 import create_video_generation_job, video_gen_configured
from services.zeus_execution_controller_v1 import get_execution_status

router = APIRouter(prefix="/perseo/v2", tags=["perseo-v2"])


class VideoEditOp(BaseModel):
    type: str
    start_sec: Optional[float] = None
    end_sec: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    text: Optional[str] = None
    audio_url: Optional[str] = None


class VideoEditBody(BaseModel):
    input_url: str
    operations: List[VideoEditOp] = Field(default_factory=list)
    transaction_id: Optional[str] = None


class ImageGenBody(BaseModel):
    prompt: str = Field(..., min_length=3)
    transaction_id: Optional[str] = None


class AdsCreateBody(BaseModel):
    platform: str
    name: str
    budget: float = Field(..., gt=0)
    transaction_id: Optional[str] = None


class PublishBody(BaseModel):
    platform: str
    video_url: str
    caption: str = ""
    transaction_id: Optional[str] = None


class AiImageAnalyzeBody(BaseModel):
    image_url: str
    goals: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class AiVideoRecommendBody(BaseModel):
    duration_seconds: float = 45
    tone: str = "energético"
    platform: str = "meta"


class AiSeoAuditBody(BaseModel):
    url: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    html_snapshot: Optional[str] = None


class AiAdsBody(BaseModel):
    product: str = ""
    budget: float = 1000
    audience: str = "general"
    objective: str = "leads"


class AiVideoGenBody(BaseModel):
    prompt: str = Field(..., min_length=3)
    duration_sec: float = Field(default=5.0, gt=0, le=10)
    transaction_id: Optional[str] = None


class PipelineRunBody(BaseModel):
    input_url: Optional[str] = None
    image_url: Optional[str] = None
    prompt: Optional[str] = None
    platform: str = "instagram"
    duration_sec: float = 5.0
    generate_video: bool = False
    publish: bool = False
    caption: str = ""
    seo_url: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    ads_budget: Optional[float] = None
    transaction_id: Optional[str] = None
    require_approval: bool = True


@router.get("/status")
def perseo_v2_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ = current_user
    execution = get_execution_status(db)
    return {
        "success": True,
        "version": "v2",
        "perseo_v2_enabled": bool(settings.PERSEO_V2_ENABLED),
        "execution_mode": execution["execution_mode"],
        "writes_enabled": execution["writes_enabled"],
        "storage": {
            "backend": storage_backend(),
            "s3_configured": s3_configured(),
            "cloud_required": bool(settings.PERSEO_V2_ENABLED),
        },
        "engines": {
            "video_engine_v2": {"ffmpeg": True, "async": True},
            "video_generation": {"configured": video_gen_configured(), "model": "zeroscope-v2-xl"},
            "image_generation": {"configured": _provider_configured(), "provider": settings.PERSEO_IMAGE_PROVIDER},
            "ai_tools": {"openai": openai_configured(), "model": settings.PERSEO_AI_MODEL},
            "pipeline": pipeline_status(db),
            "ads_engine_v2": {"meta": _meta_configured(), "google": _google_configured()},
            "publishing_v1": {"instagram": _instagram_configured(), "mode": "semi_auto", "requires_approval": True},
            "analytics_v2": {"meta": _meta_configured()},
        },
        "queue": {
            "active": count_jobs_by_status(db, "processing"),
            "queued": count_jobs_by_status(db, "queued"),
            "failed": count_jobs_by_status(db, "failed"),
        },
    }


@router.get("/audit")
def perseo_v2_audit(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ = current_user
    base = build_audit_report(db)
    base["version"] = "v2_full_rebuild"
    base["perseo_v2"] = {
        "enabled": bool(settings.PERSEO_V2_ENABLED),
        "storage_backend": storage_backend(),
        "s3_configured": s3_configured(),
        "transactional_flow": True,
        "engines": ["video_engine_v2", "image_engine_v2", "ads_engine_v2", "publishing_v1", "analytics_v2"],
    }
    return {"success": True, **base}


@router.post("/video/edit")
def perseo_v2_video_edit(
    body: VideoEditBody,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    ops = [o.model_dump(exclude_none=True) for o in body.operations]
    return {"success": True, **create_video_edit_job_v2(
        db, current_user, input_url=body.input_url, operations=ops, transaction_id=body.transaction_id,
    )}


@router.post("/image/generate")
def perseo_v2_image_generate(
    body: ImageGenBody,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return {"success": True, **create_image_generation_job(
        db, current_user, prompt=body.prompt, transaction_id=body.transaction_id,
    )}


@router.post("/ads/create")
def perseo_v2_ads_create(
    body: AdsCreateBody,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return {"success": True, **create_ad_campaign(
        db, current_user, platform=body.platform, name=body.name, budget=body.budget,
        transaction_id=body.transaction_id,
    )}


@router.post("/publish")
def perseo_v2_publish(
    body: PublishBody,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return {"success": True, **publish_post(
        db, current_user, platform=body.platform, video_url=body.video_url,
        caption=body.caption, transaction_id=body.transaction_id,
    )}


@router.get("/analytics")
def perseo_v2_analytics(
    source: str = "meta_ads",
    campaign_id: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return {"success": True, **fetch_analytics(db, current_user, source=source, campaign_id=campaign_id)}


@router.get("/jobs/{job_id}")
def perseo_v2_job(
    job_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        job = get_job(db, job_id, current_user.id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"success": job["status"] == "completed", **job}


@router.post("/ai/analyze-image")
def perseo_ai_analyze_image(
    body: AiImageAnalyzeBody,
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    _ = current_user
    return {"success": True, **analyze_image_ai(body.model_dump())}


@router.post("/ai/recommend-video")
def perseo_ai_recommend_video(
    body: AiVideoRecommendBody,
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    _ = current_user
    return {"success": True, **recommend_video_ai(body.model_dump())}


@router.post("/ai/seo-audit")
def perseo_ai_seo_audit(
    body: AiSeoAuditBody,
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    _ = current_user
    return {"success": True, **seo_audit_ai(body.model_dump())}


@router.post("/ai/generate-ads")
def perseo_ai_generate_ads(
    body: AiAdsBody,
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    _ = current_user
    return {"success": True, **generate_ads_ai(body.model_dump())}


@router.post("/ai/generate-image")
def perseo_ai_generate_image(
    body: ImageGenBody,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return {"success": True, **create_image_generation_job(
        db, current_user, prompt=body.prompt, transaction_id=body.transaction_id,
    )}


@router.post("/ai/generate-video")
def perseo_ai_generate_video(
    body: AiVideoGenBody,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return {"success": True, **create_video_generation_job(
        db, current_user, prompt=body.prompt, duration_sec=body.duration_sec,
        transaction_id=body.transaction_id,
    )}


@router.get("/pipeline/status")
def perseo_pipeline_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ = current_user
    return {"success": True, **pipeline_status(db)}


@router.post("/pipeline/run")
def perseo_pipeline_run(
    body: PipelineRunBody,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return run_pipeline(db, current_user, **body.model_dump())
