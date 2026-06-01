"""Esquemas Marketing Integrations v1."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class SocialPlatformConfig(BaseModel):
    connected: bool = False
    username: Optional[str] = ""
    page_id: Optional[str] = ""
    phone_number: Optional[str] = ""
    location_id: Optional[str] = ""
    email: Optional[str] = ""


class AdsPlatformConfig(BaseModel):
    connected: bool = False
    account_id: str = ""
    track_metrics: bool = True


class MarketingPermissions(BaseModel):
    allow_auto_post: bool = False
    allow_auto_ads_analysis: bool = True
    allow_auto_messages: bool = False


class MarketingIntegrationsIn(BaseModel):
    social_platforms: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    ads_platforms: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    permissions: MarketingPermissions = Field(default_factory=MarketingPermissions)


class MarketingIntegrationsOut(BaseModel):
    company_id: int
    social_platforms: Dict[str, Any]
    ads_platforms: Dict[str, Any]
    permissions: Dict[str, Any]
    metrics_collected: list[str]
    updated_at: Optional[str] = None
