"""
PERSEO full-system audit v1 — feature classification and report generation.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal

from sqlalchemy.orm import Session

from app.core.config import settings
from services.zeus_execution_controller_v1 import get_execution_status

logger = logging.getLogger(__name__)

FeatureStatus = Literal["REAL", "SIMULATED", "BROKEN", "MISSING"]

AUDIT_TARGETS = (
    "content_generation",
    "ads_generation",
    "video_editing",
    "image_generation",
    "video_generation",
    "video_engine_v3",
    "video_engine_pro_v4",
    "image_analyzer",
    "video_recommender",
    "seo_audit",
    "ads_blueprint",
    "pipeline",
    "publishing",
    "analytics",
    "automation",
)


def _ffmpeg_available() -> bool:
    try:
        import imageio_ffmpeg  # type: ignore

        imageio_ffmpeg.get_ffmpeg_exe()
        return True
    except Exception:
        return False


def build_feature_status_map(db: Session | None = None) -> Dict[str, Dict[str, Any]]:
    execution = get_execution_status(db)
    ffmpeg_ok = _ffmpeg_available()
    images_on = bool(getattr(settings, "PERSEO_IMAGES_ENABLED", True))
    v2 = bool(getattr(settings, "PERSEO_V2_ENABLED", False))

    from services.perseo_storage_v2 import s3_configured

    try:
        from services.perseo_image_engine_v2 import _provider_configured
        from services.perseo_video_gen_engine_v2 import video_gen_configured
        from services.perseo_video_engine_v3 import video_engine_v3_configured
        from services.perseo_video_pro_engine_v4 import video_pro_engine_v4_configured
        from services.perseo_ai_service_v2 import openai_configured
        from services.perseo_ads_engine_v2 import _meta_configured, _google_configured
        from services.perseo_publishing_v1 import _instagram_configured
    except ImportError:
        _provider_configured = lambda: False  # type: ignore
        video_gen_configured = lambda: False  # type: ignore
        video_engine_v3_configured = lambda: False  # type: ignore
        video_pro_engine_v4_configured = lambda: False  # type: ignore
        openai_configured = lambda: False  # type: ignore
        _meta_configured = lambda: False  # type: ignore
        _google_configured = lambda: False  # type: ignore
        _instagram_configured = lambda: False  # type: ignore

    ai_on = openai_configured()

    video_status: FeatureStatus = "REAL" if ffmpeg_ok else "BROKEN"
    if v2 and not s3_configured():
        video_status = "BROKEN"

    image_status: FeatureStatus = "SIMULATED"
    if v2 and _provider_configured():
        image_status = "REAL"
    elif images_on and not v2:
        image_status = "REAL"

    ads_status: FeatureStatus = "SIMULATED"
    if _meta_configured() or _google_configured():
        ads_status = "REAL" if _meta_configured() else "BROKEN"

    pub_status: FeatureStatus = "MISSING"
    if _instagram_configured():
        pub_status = "REAL"

    analytics_status: FeatureStatus = "REAL" if _meta_configured() else "SIMULATED"

    ai_tool_status: FeatureStatus = "REAL" if ai_on else "SIMULATED"
    video_gen_status: FeatureStatus = "REAL" if video_gen_configured() and s3_configured() else (
        "BROKEN" if video_gen_configured() and not s3_configured() else ("SIMULATED" if not video_gen_configured() else "REAL")
    )
    pipeline_status_val: FeatureStatus = "REAL" if (ffmpeg_ok and (not v2 or s3_configured())) else "BROKEN"
    v3_status: FeatureStatus = "REAL" if (ffmpeg_ok and execution["writes_enabled"]) else (
        "BROKEN" if not ffmpeg_ok else "SIMULATED"
    )
    v4_status: FeatureStatus = "REAL" if (ffmpeg_ok and execution["writes_enabled"]) else (
        "BROKEN" if not ffmpeg_ok else "SIMULATED"
    )

    return {
        "content_generation": {
            "status": "REAL",
            "endpoint": "POST /api/v1/chat (agent=PERSEO)",
            "notes": "LLM copy via OpenAI; workspace persist to document_approvals",
            "execution_mode": execution["execution_mode"],
        },
        "video_editing": {
            "status": video_status,
            "endpoint": "/api/v1/perseo/v2/video/edit" if v2 else "/api/v1/perseo/video/edit",
            "notes": "FFmpeg v2 + cloud storage when PERSEO_V2_ENABLED",
            "ffmpeg_available": ffmpeg_ok,
            "engine": "perseo_video_engine_v2" if v2 else "perseo_video_engine_v1",
        },
        "image_generation": {
            "status": image_status,
            "endpoint": "/api/v1/perseo/v2/image/generate" if v2 else "/api/v1/perseo/upload-image",
            "notes": "AI via Replicate/Stability when configured" if v2 else "Local upload only",
            "storage": getattr(settings, "PERSEO_STORAGE_BACKEND", "local"),
        },
        "video_generation": {
            "status": video_gen_status,
            "endpoint": "/api/v1/perseo/v2/ai/generate-video",
            "notes": "Replicate zeroscope-v2-xl → S3",
            "model": "zeroscope-v2-xl",
        },
        "video_engine_v3": {
            "status": v3_status,
            "endpoint": "POST /api/v1/perseo/video/generate",
            "notes": "FFmpeg imagen→MP4 vertical 15s + copy conversión + CRM (v3.0.0)",
            "ffmpeg_available": ffmpeg_ok,
            "openai_copy": ai_on,
            "engine": "perseo_video_engine_v3",
        },
        "video_engine_pro_v4": {
            "status": v4_status,
            "endpoint": "POST /api/v1/perseo/video-pro/generate",
            "notes": "PERSEO_FFMPEG_VIDEO_PRODUCTION — zoompan filter_complex, copy manual/IA, S3 videos/{tenant}/ (v4.1.0)",
            "ffmpeg_available": ffmpeg_ok,
            "openai_copy": ai_on,
            "engine": "perseo_video_pro_engine_v4",
        },
        "image_analyzer": {
            "status": ai_tool_status,
            "endpoint": "/api/v1/perseo/v2/ai/analyze-image",
            "notes": "GPT-4o vision when OPENAI_API_KEY configured",
        },
        "video_recommender": {
            "status": ai_tool_status,
            "endpoint": "/api/v1/perseo/v2/ai/recommend-video",
            "notes": "GPT-4o script and scene breakdown",
        },
        "seo_audit": {
            "status": ai_tool_status,
            "endpoint": "/api/v1/perseo/v2/ai/seo-audit",
            "notes": "GPT-4o SEO audit with meta tags",
        },
        "ads_blueprint": {
            "status": "REAL" if (_meta_configured() or ai_on) else "SIMULATED",
            "endpoint": "/api/v1/perseo/v2/ai/generate-ads",
            "notes": "GPT-4o blueprint + Meta API for live campaigns",
        },
        "pipeline": {
            "status": pipeline_status_val,
            "endpoint": "/api/v1/perseo/v2/pipeline/run",
            "notes": "Full flow orchestrated by ZEUS_CORE",
            "stages": [
                "input_media",
                "ai_analysis",
                "content_generation",
                "video_processing",
                "storage_upload",
                "optimization",
                "publishing",
            ],
        },
        "ads_generation": {
            "status": ads_status,
            "endpoint": "/api/v1/perseo/v2/ads/create",
            "notes": "Meta Graph API when token configured; Google requires client library",
            "blocked_for_real_badges": ads_status == "SIMULATED",
        },
        "publishing": {
            "status": pub_status,
            "endpoint": "/api/v1/perseo/v2/publish",
            "notes": "Instagram Reels via Graph API when configured",
        },
        "analytics": {
            "status": analytics_status,
            "endpoint": "/api/v1/perseo/v2/analytics",
            "notes": "Meta insights — no placeholders when configured",
            "blocked_for_real_badges": analytics_status == "SIMULATED",
        },
        "automation": {
            "status": "REAL",
            "endpoint": "automation/handlers/perseo.py",
            "notes": "Files to storage/outputs/perseo; external AI prompts are text-only",
        },
    }


def build_audit_report(db: Session | None = None) -> Dict[str, Any]:
    features = build_feature_status_map(db)
    fake = [k for k, v in features.items() if v["status"] == "SIMULATED"]
    broken = [k for k, v in features.items() if v["status"] == "BROKEN"]
    missing = [k for k, v in features.items() if v["status"] == "MISSING"]
    real = [k for k, v in features.items() if v["status"] == "REAL"]

    execution = get_execution_status(db)
    return {
        "project": "PERSEO_AGENT",
        "version": "v1_full_system_audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "full_system_audit",
        "execution_mode": execution["execution_mode"],
        "writes_enabled": execution["writes_enabled"],
        "audit_targets": list(AUDIT_TARGETS),
        "feature_status_map": features,
        "summary": {
            "REAL": real,
            "SIMULATED": fake,
            "BROKEN": broken,
            "MISSING": missing,
        },
        "fake_features_list": fake,
        "broken_features_list": broken,
        "video_editing_audit": {
            "required_endpoint": "/api/v1/perseo/video/edit",
            "endpoint_exists": True,
            "ffmpeg_available": _ffmpeg_available(),
            "storage": "local_static",
            "checks_passed": _ffmpeg_available(),
        },
        "zeus_integration": {
            "transaction_module": "PERSEO",
            "supported_actions": [
                "video_edit",
                "generate_image",
                "generate_video",
                "analyze_image",
                "recommend_video",
                "seo_audit",
                "generate_ads",
                "create_campaign",
                "publish_post",
                "run_pipeline",
                "store_object",
            ],
            "storage_module": "STORAGE",
            "require_transaction_id": False,
            "respect_execution_mode": True,
        },
        "rules": {
            "no_success_without_real_output": True,
            "require_storage_for_media": True,
            "all_writes_must_use_zeus_transaction": False,
        },
    }


def write_audit_report_file(db: Session | None = None) -> Path:
    report = build_audit_report(db)
    out_dir = Path(__file__).resolve().parents[1] / "config"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "perseo_audit_report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("[PERSEO_AUDIT] report written to %s", path)
    return path
