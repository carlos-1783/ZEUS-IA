"""PERSEO analytics v2 — real metrics from Meta/Google when configured."""

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


def fetch_meta_insights(*, campaign_id: Optional[str] = None) -> Dict[str, Any]:
    token = os.getenv("FACEBOOK_ACCESS_TOKEN") or os.getenv("META_ACCESS_TOKEN")
    account = os.getenv("FACEBOOK_AD_ACCOUNT_ID") or os.getenv("META_AD_ACCOUNT_ID")
    if not token or not account:
        raise HTTPException(status_code=503, detail={"error": "meta_ads_not_configured"})
    act = account if account.startswith("act_") else f"act_{account}"
    target = campaign_id or act
    fields = "impressions,clicks,ctr,spend,actions"
    url = f"https://graph.facebook.com/v21.0/{target}/insights"
    r = requests.get(url, params={"access_token": token, "fields": fields}, timeout=30)
    body = r.json()
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail={"error": "meta_insights_failed", "response": body})
    rows = body.get("data") or []
    if not rows:
        return {"source": "meta_ads", "metrics": {}, "note": "no_data_in_range"}
    row = rows[0]
    clicks = int(row.get("clicks") or 0)
    impressions = int(row.get("impressions") or 0)
    ctr = float(row.get("ctr") or (clicks / impressions * 100 if impressions else 0))
    conversions = 0
    for action in row.get("actions") or []:
        if action.get("action_type") in ("purchase", "lead", "complete_registration"):
            conversions += int(action.get("value") or 0)
    return {
        "source": "meta_ads",
        "simulated": False,
        "metrics": {
            "impressions": impressions,
            "ctr": round(ctr, 4),
            "conversions": conversions,
            "engagement_rate": round(clicks / impressions * 100, 4) if impressions else 0,
            "ad_spend": float(row.get("spend") or 0),
        },
    }


def fetch_analytics(
    db: Session,
    user: User,
    *,
    source: str = "meta_ads",
    campaign_id: Optional[str] = None,
) -> Dict[str, Any]:
    execution = get_execution_status(db)
    if execution["execution_mode"] == "ERROR":
        raise HTTPException(status_code=503, detail="execution_mode ERROR")
    _ = user
    src = source.lower()
    if src in ("meta", "meta_ads"):
        return fetch_meta_insights(campaign_id=campaign_id)
    if src in ("google", "google_ads"):
        if not (os.getenv("GOOGLE_ADS_CUSTOMER_ID") and os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")):
            raise HTTPException(status_code=503, detail={"error": "google_ads_not_configured"})
        raise HTTPException(status_code=501, detail={"error": "google_ads_reporting_requires_client_library"})
    raise HTTPException(status_code=422, detail=f"Unknown analytics source: {source}")
