"""PERSEO publishing v1 — Instagram / YouTube / TikTok (real API when configured)."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import requests
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.user import User
from services.zeus_execution_controller_v1 import get_execution_status

logger = logging.getLogger(__name__)


def _instagram_configured() -> bool:
    return bool(os.getenv("INSTAGRAM_ACCESS_TOKEN") and os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID"))


def publish_instagram_reel(*, video_url: str, caption: str) -> Dict[str, Any]:
    token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    ig_user = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")
    if not token or not ig_user:
        raise HTTPException(status_code=503, detail={"error": "instagram_not_configured"})
    base = f"https://graph.facebook.com/v21.0/{ig_user}"
    create = requests.post(
        f"{base}/media",
        data={"media_type": "REELS", "video_url": video_url, "caption": caption, "access_token": token},
        timeout=60,
    )
    body = create.json()
    if create.status_code >= 400:
        raise HTTPException(status_code=502, detail={"error": "instagram_create_failed", "response": body})
    creation_id = body.get("id")
    pub = requests.post(
        f"{base}/media_publish",
        data={"creation_id": creation_id, "access_token": token},
        timeout=60,
    )
    pub_body = pub.json()
    if pub.status_code >= 400:
        raise HTTPException(status_code=502, detail={"error": "instagram_publish_failed", "response": pub_body})
    return {"success": True, "platform": "instagram", "media_id": pub_body.get("id"), "simulated": False}


def publish_post(
    db: Session,
    user: User,
    *,
    platform: str,
    video_url: str,
    caption: str,
    transaction_id: Optional[str] = None,
) -> Dict[str, Any]:
    execution = get_execution_status(db)
    if execution["execution_mode"] == "ERROR":
        raise HTTPException(status_code=503, detail="execution_mode ERROR")
    if not execution["writes_enabled"]:
        raise HTTPException(status_code=403, detail="writes_enabled false")
    _ = user
    plat = platform.lower()
    if plat == "instagram":
        return {**publish_instagram_reel(video_url=video_url, caption=caption), "transaction_id": transaction_id}
    if plat == "youtube":
        if not os.getenv("YOUTUBE_ACCESS_TOKEN"):
            raise HTTPException(status_code=503, detail={"error": "youtube_not_configured"})
        raise HTTPException(status_code=501, detail={"error": "youtube_upload_requires_resumable_api"})
    if plat == "tiktok":
        if not os.getenv("TIKTOK_ACCESS_TOKEN"):
            raise HTTPException(status_code=503, detail={"error": "tiktok_not_configured"})
        raise HTTPException(status_code=501, detail={"error": "tiktok_upload_not_implemented"})
    raise HTTPException(status_code=422, detail=f"Unknown platform: {platform}")
