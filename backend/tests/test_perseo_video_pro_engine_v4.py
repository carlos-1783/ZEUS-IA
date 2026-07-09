"""Tests PERSEO Video Pro Engine v4."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.perseo_video_pro_engine_v4 import (
    ENGINE_VERSION,
    MAX_WORDS_PER_SCENE,
    _limit_words,
    _validate_pro_script,
    video_pro_engine_v4_configured,
)


def test_pro_limit_words_max_10():
    text = " ".join(f"w{i}" for i in range(20))
    assert len(_limit_words(text).split()) == MAX_WORDS_PER_SCENE


def test_validate_pro_script_ok():
    script = {
        "hook": "¿Sigues sin clientes hoy?",
        "problem": "Tu anuncio no convierte en Meta",
        "solution": "PERSEO Pro crea vídeos que venden",
        "cta": "Reserva demo gratis ahora",
    }
    v = _validate_pro_script(script)
    assert v["hook_visible_first_2s"] is True
    assert v["cta_button_visible"] is True
    assert v["movement"] is True


def test_validate_pro_rejects_generic():
    with pytest.raises(Exception):
        _validate_pro_script({
            "hook": "descubre más sobre nosotros",
            "problem": "sin problema",
            "solution": "somos líderes",
            "cta": "descubre más",
        })


def test_engine_version():
    assert ENGINE_VERSION == "4.0.0"


@patch("services.perseo_video_pro_engine_v4._ffmpeg_path", return_value="/usr/bin/ffmpeg")
def test_pro_configured(_mock):
    assert video_pro_engine_v4_configured() is True


def test_audit_has_video_engine_pro_v4():
    from services.perseo_audit_service_v1 import build_feature_status_map

    features = build_feature_status_map(None)
    assert "video_engine_pro_v4" in features
    assert "video-pro/generate" in features["video_engine_pro_v4"]["endpoint"]


@patch("services.perseo_video_pro_engine_v4._persist_gif")
@patch("services.perseo_video_pro_engine_v4._generate_gif_preview")
@patch("services.perseo_video_pro_engine_v4._mux_audio")
@patch("services.perseo_video_pro_engine_v4._generate_voiceover")
@patch("services.perseo_video_pro_engine_v4._generate_background_music")
@patch("services.perseo_video_pro_engine_v4._run_ffmpeg_video")
@patch("services.perseo_video_pro_engine_v4._persist_video")
@patch("services.perseo_video_pro_engine_v4._crm_integrate")
@patch("services.perseo_video_pro_engine_v4._resolve_image_path")
@patch("services.perseo_video_pro_engine_v4._generate_pro_copy")
@patch("services.perseo_video_pro_engine_v4.resolve_tenant_company")
@patch("services.perseo_video_pro_engine_v4.get_execution_status")
@patch("services.perseo_video_pro_engine_v4._ffmpeg_path", return_value="/usr/bin/ffmpeg")
def test_generate_pro_v4_orchestration(
    _ff,
    mock_exec,
    mock_tenant,
    mock_copy,
    mock_img,
    mock_crm,
    mock_store,
    mock_ffmpeg,
    _music,
    _voice,
    _mux,
    mock_gif,
    mock_persist_gif,
):
    from services.perseo_video_pro_engine_v4 import generate_perseo_video_pro_v4

    mock_exec.return_value = {"execution_mode": "REAL", "writes_enabled": True}
    company = MagicMock()
    company.id = 3
    company.slug = "acme"
    company.company_name = "Acme"
    mock_tenant.return_value = (company, 3)
    mock_copy.return_value = {
        "script": {
            "hook": "¿Sin ventas esta semana?",
            "problem": "Tu competencia te gana en ads",
            "solution": "Acme genera anuncios que convierten",
            "cta": "Pide tu demo gratis hoy",
        },
        "structured_copy": {},
        "ai_powered": True,
        "mode": "high_conversion",
    }
    mock_img.return_value = Path("/tmp/img.jpg")
    mock_store.return_value = {"video_url": "/static/v.mp4", "storage": "local"}
    mock_crm.return_value = {"crm_saved": True}
    mock_gif.return_value = Path("/tmp/p.gif")
    mock_persist_gif.return_value = "/static/p.gif"

    user = MagicMock()
    user.id = 1
    out = generate_perseo_video_pro_v4(
        MagicMock(),
        user,
        tenant_id="3",
        image_url="https://x.com/p.jpg",
        product_info="SaaS",
    )
    assert out["version"] == "4.0.0"
    assert out["ready_for_ads"] is True
    assert out["preview"] == "/static/p.gif"
    mock_ffmpeg.assert_called_once()
