"""Fase 2 / Step 2 — marketing_service ya no inventa campanas ni metricas."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from services.marketing_service import MarketingService

_ENV_OFF = {k: "" for k in (
    "GOOGLE_ADS_DEVELOPER_TOKEN", "GOOGLE_ADS_CUSTOMER_ID", "FACEBOOK_ACCESS_TOKEN", "META_ACCESS_TOKEN",
    "FACEBOOK_AD_ACCOUNT_ID", "META_AD_ACCOUNT_ID", "GA_PROPERTY_ID", "GA_CREDENTIALS",
)}


def _run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize("method,code", [
    ("create_google_ads_campaign", 503),
    ("get_google_ads_performance", 503),
    ("optimize_google_ads_campaign", 503),
    ("get_analytics_data", 503),
])
def test_unconfigured_platforms_fail_explicitly(monkeypatch, method, code):
    for k, v in _ENV_OFF.items():
        monkeypatch.setenv(k, v)
    with pytest.raises(HTTPException) as exc:
        _run(getattr(MarketingService(), method)())
    assert exc.value.status_code == code


def test_google_ads_with_credentials_is_501_not_fake_success(monkeypatch):
    monkeypatch.setenv("GOOGLE_ADS_DEVELOPER_TOKEN", "t")
    monkeypatch.setenv("GOOGLE_ADS_CUSTOMER_ID", "1")
    for m in ("create_google_ads_campaign", "get_google_ads_performance", "optimize_google_ads_campaign"):
        with pytest.raises(HTTPException) as exc:
            _run(getattr(MarketingService(), m)())
        assert exc.value.status_code == 501


def test_report_without_real_sources_is_503(monkeypatch):
    for k, v in _ENV_OFF.items():
        monkeypatch.setenv(k, v)
    with pytest.raises(HTTPException) as exc:
        _run(MarketingService().generate_marketing_report())
    assert exc.value.status_code == 503


def test_meta_insights_calls_graph_api_and_returns_its_data(monkeypatch):
    monkeypatch.setenv("FACEBOOK_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("FACEBOOK_AD_ACCOUNT_ID", "123")
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"data": [{"impressions": "7", "clicks": "1"}]}
    with patch("services.marketing_service.requests.get", return_value=resp) as get:
        out = _run(MarketingService().get_meta_ads_insights())
    assert get.call_args.args[0].endswith("/act_123/insights")
    assert out["data"] == [{"impressions": "7", "clicks": "1"}] and out["source"] == "graph_api"


def test_meta_api_error_is_502_not_success(monkeypatch):
    monkeypatch.setenv("FACEBOOK_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("FACEBOOK_AD_ACCOUNT_ID", "123")
    resp = MagicMock(status_code=400)
    resp.json.return_value = {"error": {"message": "Invalid token"}}
    with patch("services.marketing_service.requests.get", return_value=resp):
        with pytest.raises(HTTPException) as exc:
            _run(MarketingService().get_meta_ads_insights())
    assert exc.value.status_code == 502
