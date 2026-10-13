"""Fase 2 #1 — PERSEO no usa la credencial GLOBAL de Meta/Instagram/Google Ads en nombre
de un usuario de empresa.

Usuario normal → 503 "no conectado para tu empresa" y NO se llama a la API externa.
Superusuario (operador de plataforma) → sí se llama (cliente HTTP doble solo en test).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

import services.perseo_ads_engine_v2 as ads
import services.perseo_analytics_v2 as analytics
import services.perseo_publishing_v1 as publishing

EXEC_OK = {"execution_mode": "REAL", "writes_enabled": True, "modules": {}}

USER = SimpleNamespace(id=7, email="empresa@a.test", is_superuser=False)
SUPER = SimpleNamespace(id=1, email="root@zeus.test", is_superuser=True)


@pytest.fixture
def platform_env(monkeypatch):
    monkeypatch.setenv("FACEBOOK_ACCESS_TOKEN", "platform-token")
    monkeypatch.setenv("FACEBOOK_AD_ACCOUNT_ID", "act_999")
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "ig-platform-token")
    monkeypatch.setenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "17841400000")
    monkeypatch.setenv("GOOGLE_ADS_CUSTOMER_ID", "123")
    monkeypatch.setenv("GOOGLE_ADS_DEVELOPER_TOKEN", "dev")


def _resp(status, body):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body
    return r


def _assert_not_connected(exc, integration):
    assert exc.value.status_code == 503
    assert exc.value.detail["error"] == f"{integration}_not_connected_for_company"
    assert "no conectado para tu empresa" in exc.value.detail["message"]


# ------------------------------------------------------------------ Ads


def test_usuario_empresa_no_crea_campana_con_cuenta_de_plataforma(platform_env):
    with patch.object(ads, "get_execution_status", return_value=EXEC_OK), \
         patch.object(ads.requests, "post") as post:
        with pytest.raises(HTTPException) as exc:
            ads.create_ad_campaign(MagicMock(), USER, platform="meta", name="x", budget=50)
    _assert_not_connected(exc, "meta_ads")
    post.assert_not_called()


def test_usuario_empresa_google_ads_tambien_503(platform_env):
    with patch.object(ads, "get_execution_status", return_value=EXEC_OK):
        with pytest.raises(HTTPException) as exc:
            ads.create_ad_campaign(MagicMock(), USER, platform="google_ads", name="x", budget=50)
    _assert_not_connected(exc, "google_ads")


def test_usuario_sin_flag_superuser_tratado_como_normal(platform_env):
    anon_like = SimpleNamespace(id=3)
    with patch.object(ads, "get_execution_status", return_value=EXEC_OK), \
         patch.object(ads.requests, "post") as post:
        with pytest.raises(HTTPException) as exc:
            ads.create_ad_campaign(MagicMock(), anon_like, platform="meta", name="x", budget=5)
    assert exc.value.status_code == 503
    post.assert_not_called()


def test_superusuario_si_usa_la_cuenta_de_plataforma(platform_env):
    with patch.object(ads, "get_execution_status", return_value=EXEC_OK), \
         patch.object(ads.requests, "post", return_value=_resp(200, {"id": "cmp_1"})) as post:
        out = ads.create_ad_campaign(MagicMock(), SUPER, platform="meta", name="x", budget=12.5)
    assert out["campaign_id"] == "cmp_1"
    post.assert_called_once()
    assert "act_999/campaigns" in post.call_args.args[0]
    assert post.call_args.kwargs["data"]["daily_budget"] == "1250"


def test_plataforma_desconocida_sigue_siendo_422(platform_env):
    with patch.object(ads, "get_execution_status", return_value=EXEC_OK):
        with pytest.raises(HTTPException) as exc:
            ads.create_ad_campaign(MagicMock(), USER, platform="myspace", name="x", budget=5)
    assert exc.value.status_code == 422


# ------------------------------------------------------------------ Insights


def test_usuario_empresa_no_lee_insights_de_ningun_campaign_id(platform_env):
    with patch.object(analytics, "get_execution_status", return_value=EXEC_OK), \
         patch.object(analytics.requests, "get") as get:
        with pytest.raises(HTTPException) as exc:
            analytics.fetch_analytics(MagicMock(), USER, source="meta_ads", campaign_id="2384000000")
    _assert_not_connected(exc, "meta_insights")
    get.assert_not_called()


def test_superusuario_lee_insights(platform_env):
    body = {"data": [{"impressions": "1000", "clicks": "20", "ctr": "2.0", "spend": "9.5", "actions": []}]}
    with patch.object(analytics, "get_execution_status", return_value=EXEC_OK), \
         patch.object(analytics.requests, "get", return_value=_resp(200, body)) as get:
        out = analytics.fetch_analytics(MagicMock(), SUPER, source="meta_ads", campaign_id="2384000000")
    get.assert_called_once()
    assert out["metrics"]["impressions"] == 1000
    assert out["metrics"]["ad_spend"] == 9.5


# ------------------------------------------------------------------ Publicación


@pytest.mark.parametrize("platform", ["instagram", "youtube", "tiktok"])
def test_usuario_empresa_no_publica_en_cuentas_de_plataforma(platform_env, platform):
    with patch.object(publishing, "get_execution_status", return_value=EXEC_OK), \
         patch.object(publishing.requests, "post") as post:
        with pytest.raises(HTTPException) as exc:
            publishing.publish_post(
                MagicMock(), USER, platform=platform, video_url="https://cdn.example/v.mp4", caption="hola"
            )
    _assert_not_connected(exc, platform)
    post.assert_not_called()


def test_superusuario_publica_en_instagram(platform_env):
    with patch.object(publishing, "get_execution_status", return_value=EXEC_OK), \
         patch.object(
             publishing.requests,
             "post",
             side_effect=[_resp(200, {"id": "creation_1"}), _resp(200, {"id": "media_1"})],
         ) as post:
        out = publishing.publish_post(
            MagicMock(), SUPER, platform="instagram", video_url="https://cdn.example/v.mp4", caption="hola"
        )
    assert out["media_id"] == "media_1"
    assert post.call_count == 2


# ------------------------------------------------------------------ Estado


def test_status_no_anuncia_meta_a_usuario_de_empresa(platform_env):
    from app.api.v1.endpoints import perseo_v2 as ep

    with patch.object(ep, "get_execution_status", return_value=EXEC_OK), \
         patch.object(ep, "pipeline_status", return_value={}), \
         patch.object(ep, "count_jobs_by_status", return_value=0):
        normal = ep.perseo_v2_status(current_user=USER, db=MagicMock())
        root = ep.perseo_v2_status(current_user=SUPER, db=MagicMock())
    assert normal["engines"]["ads_engine_v2"]["meta"] is False
    assert normal["engines"]["publishing_v1"]["instagram"] is False
    assert normal["engines"]["analytics_v2"]["meta"] is False
    assert normal["engines"]["ads_engine_v2"]["scope"] == "no_conectado_para_tu_empresa"
    assert root["engines"]["ads_engine_v2"]["meta"] is True
    assert root["engines"]["publishing_v1"]["instagram"] is True
