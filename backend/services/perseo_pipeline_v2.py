"""PERSEO pipeline v2 — end-to-end media flow orchestrated by ZEUS."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.user import User
from services.perseo_ai_service_v2 import (
    analyze_image_ai,
    generate_ads_ai,
    openai_configured,
    recommend_video_ai,
    seo_audit_ai,
)
from services.perseo_events_v1 import emit_generation_progress, emit_perseo_event
from services.perseo_image_engine_v2 import create_image_generation_job, get_image_job
from services.perseo_publishing_v1 import publish_post
from services.perseo_storage_v2 import s3_configured
from services.perseo_video_engine_v2 import create_video_edit_job_v2, get_video_job_v2
from services.perseo_video_gen_engine_v2 import create_video_generation_job, get_video_gen_job, video_gen_configured
from services.zeus_execution_controller_v1 import get_execution_status

logger = logging.getLogger(__name__)

PIPELINE_STAGES = [
    "input_media",
    "ai_analysis",
    "content_generation",
    "video_processing",
    "storage_upload",
    "optimization",
    "publishing",
]


def pipeline_status(db: Session | None = None) -> Dict[str, Any]:
    execution = get_execution_status(db)
    return {
        "stages": PIPELINE_STAGES,
        "orchestrator": "ZEUS_CORE",
        "connected": True,
        "ai_enabled": openai_configured(),
        "video_generation": video_gen_configured(),
        "storage": "s3" if s3_configured() else "local",
        "execution_mode": execution["execution_mode"],
        "writes_enabled": execution["writes_enabled"],
    }


def _poll_job(get_fn, db, job_id, user_id, max_attempts=120, interval=1.0):
    for _ in range(max_attempts):
        job = get_fn(db, job_id, user_id)
        if job["status"] == "completed":
            return job
        if job["status"] == "failed":
            raise HTTPException(status_code=500, detail=job.get("error") or "job failed")
        time.sleep(interval)
    raise HTTPException(status_code=504, detail="pipeline job timeout")


def run_pipeline(
    db: Session,
    user: User,
    *,
    input_url: Optional[str] = None,
    image_url: Optional[str] = None,
    prompt: Optional[str] = None,
    platform: str = "instagram",
    duration_sec: float = 5.0,
    generate_video: bool = False,
    publish: bool = False,
    caption: str = "",
    seo_url: Optional[str] = None,
    keywords: Optional[List[str]] = None,
    ads_budget: Optional[float] = None,
    transaction_id: Optional[str] = None,
    require_approval: bool = True,
) -> Dict[str, Any]:
    execution = get_execution_status(db)
    if execution["execution_mode"] == "ERROR":
        raise HTTPException(status_code=503, detail="execution_mode ERROR")
    if not execution["writes_enabled"]:
        raise HTTPException(status_code=403, detail="writes_enabled false")

    media_url = input_url or image_url
    stages: Dict[str, Any] = {}
    emit_perseo_event(user.id, "pipeline_started", {"transaction_id": transaction_id, "stages": PIPELINE_STAGES})

    # 1 input_media
    stages["input_media"] = {"url": media_url, "prompt": prompt}

    # 2 ai_analysis
    if media_url and (media_url.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")) or "image" in media_url):
        stages["ai_analysis"] = analyze_image_ai({"image_url": media_url, "goals": ["conversion"], "tags": keywords or []})
        if not prompt and stages["ai_analysis"].get("hooks"):
            prompt = stages["ai_analysis"]["hooks"][0]
    else:
        stages["ai_analysis"] = {"skipped": True, "reason": "no image input"}

    emit_generation_progress(user.id, transaction_id or "pipeline", 15, "ai_analysis")

    # 3 content_generation
    content_prompt = prompt or "Marketing video for brand awareness"
    stages["content_generation"] = recommend_video_ai(
        {"duration_seconds": duration_sec * 3, "tone": "energético", "platform": platform}
    )
    if seo_url:
        stages["content_generation"]["seo"] = seo_audit_ai({"url": seo_url, "keywords": keywords or []})
    if ads_budget:
        stages["content_generation"]["ads"] = generate_ads_ai(
            {"budget": ads_budget, "audience": "general", "objective": "leads", "product": content_prompt[:80]}
        )

    emit_generation_progress(user.id, transaction_id or "pipeline", 35, "content_generation")

    # 4 video_processing
    video_output: Dict[str, Any] = {}
    if generate_video and video_gen_configured():
        created = create_video_generation_job(
            db, user, prompt=content_prompt, duration_sec=duration_sec, transaction_id=transaction_id,
        )
        job = _poll_job(get_video_gen_job, db, created["job_id"], user.id, max_attempts=90, interval=3)
        video_output = job.get("output") or {}
    elif media_url:
        ops: List[Dict[str, Any]] = [{"type": "scale", "width": 1280, "height": 720}]
        script = stages["content_generation"].get("script") or ""
        if script:
            ops.append({"type": "text_overlay", "text": script[:120]})
        created = create_video_edit_job_v2(
            db, user, input_url=media_url, operations=ops, transaction_id=transaction_id,
        )
        job = _poll_job(get_video_job_v2, db, created["job_id"], user.id)
        video_output = job.get("output") or {}
    else:
        if generate_video:
            img_job = create_image_generation_job(db, user, prompt=content_prompt, transaction_id=transaction_id)
            img = _poll_job(get_image_job, db, img_job["job_id"], user.id, max_attempts=90, interval=2)
            image_out = img.get("output") or {}
            created = create_video_generation_job(
                db, user, prompt=content_prompt, duration_sec=duration_sec, transaction_id=transaction_id,
            )
            job = _poll_job(get_video_gen_job, db, created["job_id"], user.id, max_attempts=90, interval=3)
            video_output = {**(job.get("output") or {}), "source_image": image_out.get("image_url")}
        else:
            img_job = create_image_generation_job(db, user, prompt=content_prompt, transaction_id=transaction_id)
            img = _poll_job(get_image_job, db, img_job["job_id"], user.id, max_attempts=90, interval=2)
            video_output = {"image_url": (img.get("output") or {}).get("image_url"), "mode": "image_only"}

    stages["video_processing"] = video_output
    emit_generation_progress(user.id, transaction_id or "pipeline", 70, "video_processing")

    # 5 storage_upload (engines upload to S3 when configured)
    stages["storage_upload"] = {
        "backend": "s3" if s3_configured() else "local",
        "video_url": video_output.get("video_url"),
        "image_url": video_output.get("image_url"),
    }

    # 6 optimization
    stages["optimization"] = {
        "recommendations": stages["content_generation"].get("structure") or [],
        "cta": stages["content_generation"].get("cta"),
    }

    # 7 publishing (semi-auto with approval gate)
    video_url = video_output.get("video_url")
    if publish and video_url:
        if require_approval:
            stages["publishing"] = {
                "status": "pending_approval",
                "platform": platform,
                "video_url": video_url,
                "caption": caption or stages["content_generation"].get("cta", ""),
            }
        else:
            pub = publish_post(
                db, user, platform=platform, video_url=video_url,
                caption=caption or stages["content_generation"].get("cta", ""),
                transaction_id=transaction_id,
            )
            stages["publishing"] = {"status": "published", **pub}
    else:
        stages["publishing"] = {"status": "skipped", "reason": "publish=false or no video"}

    emit_perseo_event(user.id, "pipeline_completed", {"transaction_id": transaction_id, "stages": list(stages.keys())})

    return {
        "success": True,
        "pipeline": PIPELINE_STAGES,
        "orchestrator": "ZEUS_CORE",
        "transaction_id": transaction_id,
        "stages": stages,
        "assets": {
            "video_url": video_url,
            "image_url": video_output.get("image_url"),
        },
    }
