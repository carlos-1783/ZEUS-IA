"""PERSEO ads engine v2 — Meta + Google Ads (real API or explicit failure)."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import requests
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.user import User
from services.zeus_execution_controller_v1 import get_execution_status

logger = logging.getLogger(__name__)


def _meta_configured() -> bool:
    return bool(
        (os.getenv("FACEBOOK_ACCESS_TOKEN") or os.getenv("META_ACCESS_TOKEN"))
        and (os.getenv("FACEBOOK_AD_ACCOUNT_ID") or os.getenv("META_AD_ACCOUNT_ID"))
    )


def _google_configured() -> bool:
    return bool(os.getenv("GOOGLE_ADS_CUSTOMER_ID") and os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN"))


def create_meta_campaign(
    *,
    name: str,
    objective: str = "OUTCOME_TRAFFIC",
    daily_budget_cents: int = 1000,
    status: str = "PAUSED",
) -> Dict[str, Any]:
    token = os.getenv("FACEBOOK_ACCESS_TOKEN") or os.getenv("META_ACCESS_TOKEN")
    account = os.getenv("FACEBOOK_AD_ACCOUNT_ID") or os.getenv("META_AD_ACCOUNT_ID")
    if not token or not account:
        raise HTTPException(status_code=503, detail={"error": "meta_ads_not_configured"})
    act = account if account.startswith("act_") else f"act_{account}"
    url = f"https://graph.facebook.com/v21.0/{act}/campaigns"
    data = {
        "access_token": token,
        "name": name,
        "objective": objective,
        "status": status,
        "special_ad_categories": "[]",
        "daily_budget": str(daily_budget_cents),
    }
    r = requests.post(url, data=data, timeout=30)
    body = r.json()
    if r.status_code >= 400 or "error" in body:
        raise HTTPException(
            status_code=502,
            detail={"error": "meta_ads_api_failed", "response": body},
        )
    return {
        "success": True,
        "platform": "meta_ads",
        "campaign_id": body.get("id"),
        "simulated": False,
    }


def create_google_campaign(
    *,
    name: str,
    daily_budget_micros: int = 10_000_000,
) -> Dict[str, Any]:
    _ = name, daily_budget_micros
    if not _google_configured():
        raise HTTPException(status_code=503, detail={"error": "google_ads_not_configured"})
    # GOOGLE_ADS_CUSTOMER_ID / GOOGLE_ADS_DEVELOPER_TOKEN están presentes, pero no
    # existe cliente real de la Google Ads API integrado (no hay librería
    # `google-ads` en requirements.txt ni llamada HTTP real como en Meta Ads).
    # Devolver success=True aquí sería un falso-éxito: la campaña NUNCA se crea
    # en Google Ads. Fallar de forma explícita en su lugar.
    raise HTTPException(
        status_code=501,
        detail={
            "error": "google_ads_client_not_implemented",
            "message": (
                "Google Ads API client no está implementado — la campaña NO se ha "
                "creado en Google Ads. Falta integración real (librería google-ads "
                "y flujo OAuth) antes de poder crear campañas reales."
            ),
        },
    )


def create_ad_campaign(
    db: Session,
    user: User,
    *,
    platform: str,
    name: str,
    budget: float,
    transaction_id: Optional[str] = None,
) -> Dict[str, Any]:
    execution = get_execution_status(db)
    if execution["execution_mode"] == "ERROR":
        raise HTTPException(status_code=503, detail="execution_mode ERROR")
    if not execution["writes_enabled"]:
        raise HTTPException(status_code=403, detail="writes_enabled false")
    _ = user
    plat = platform.lower()
    if plat in ("meta", "meta_ads", "facebook"):
        return {
            **create_meta_campaign(name=name, daily_budget_cents=int(budget * 100)),
            "transaction_id": transaction_id,
        }
    if plat in ("google", "google_ads"):
        return {
            **create_google_campaign(name=name, daily_budget_micros=int(budget * 1_000_000)),
            "transaction_id": transaction_id,
        }
    raise HTTPException(status_code=422, detail=f"Unknown ads platform: {platform}")
