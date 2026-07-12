"""Tests PERSEO FFmpeg Video Production v4."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.perseo_video_pro_engine_v4 import (
    DEFAULT_BRAND_COLOR,
    ENGINE_NAME,
    ENGINE_VERSION,
    MAX_WORDS_PER_SCENE,
    _brand_color_ffmpeg,
    _build_production_filter_complex,
    _limit_words,
    _sanitize_ffmpeg_text,
    _validate_pro_script,
    video_pro_engine_v4_configured,
)


def test_sanitize_ffmpeg_text():
    assert _sanitize_ffmpeg_text("50% off") == "50%% off"
    assert "\\:" in _sanitize_ffmpeg_text("hola: mundo")
    assert "\\'" in _sanitize_ffmpeg_text("it's now")


def test_brand_color_default():
    assert _brand_color_ffmpeg("") == DEFAULT_BRAND_COLOR
    assert _brand_color_ffmpeg("#004481") == "0x004481"


def test_production_filter_complex_has_cta_button():
    script = {
        "hook": "Hook test",
        "problem": "Problem test",
        "solution": "Solution test",
        "cta": "CTA test",
    }
    fc = _build_production_filter_complex(script, "0x004481")
    assert "zoompan" in fc
    assert "drawbox=x=(w/2)-300:y=1400" in fc
    assert "between(t\\,10\\,15)" in fc
    assert "Hook test" in fc


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
    assert v["cta_visible"] is True
    assert v["hook_visible_first_2s"] is True


def test_engine_meta():
    assert ENGINE_VERSION == "4.1.0"
    assert ENGINE_NAME == "PERSEO_FFMPEG_VIDEO_PRODUCTION"


@patch("services.perseo_video_pro_engine_v4._ffmpeg_path", return_value="/usr/bin/ffmpeg")
def test_pro_configured(_mock):
    assert video_pro_engine_v4_configured() is True


@patch("services.perseo_video_pro_engine_v4._persist_gif")
@patch("services.perseo_video_pro_engine_v4._generate_gif_preview")
@patch("services.perseo_video_pro_engine_v4.upload_tenant_video")
@patch("services.perseo_video_pro_engine_v4._validate_output_video")
@patch("services.perseo_video_pro_engine_v4._run_ffmpeg_production")
@patch("services.perseo_video_pro_engine_v4._download_image_to_workdir")
@patch("services.perseo_video_pro_engine_v4._crm_integrate")
@patch("services.perseo_video_pro_engine_v4._resolve_tenant_id")
@patch("services.perseo_video_pro_engine_v4.get_execution_status")
@patch("services.perseo_video_pro_engine_v4._ffmpeg_path", return_value="/usr/bin/ffmpeg")
def test_generate_with_manual_copy(
    _ff,
    mock_exec,
    mock_tenant,
    mock_crm,
    mock_dl,
    mock_ffmpeg,
    mock_validate,
    mock_upload,
    mock_gif,
    mock_persist_gif,
):
    from services.perseo_video_pro_engine_v4 import generate_perseo_video_pro_v4

    mock_exec.return_value = {"execution_mode": "REAL", "writes_enabled": True}
    company = MagicMock()
    company.id = 3
    company.slug = "acme"
    mock_tenant.return_value = (company, 3)
    mock_dl.return_value = Path("/tmp/input.jpg")
    mock_validate.return_value = {
        "video_file_exists": True,
        "duration_15s": True,
        "cta_visible": True,
        "cta_button_rendered": True,
        "animated": True,
    }
    mock_upload.return_value = {
        "url": "https://cdn/videos/3/20260101.mp4",
        "storage": "s3",
        "key": "videos/3/20260101.mp4",
    }
    mock_crm.return_value = {"crm_saved": True, "link_to_campaign": True}
    mock_gif.return_value = Path("/tmp/p.gif")
    mock_persist_gif.return_value = "/static/p.gif"

    user = MagicMock()
    user.id = 1
    out = generate_perseo_video_pro_v4(
        MagicMock(),
        user,
        image_url="https://x.com/p.jpg",
        hook="¿Sin ventas?",
        problem="Tu anuncio falla",
        solution="Acme lo arregla",
        cta="Reserva demo hoy",
    )
    assert out["mode"] == "real_execution"
    assert out["name"] == ENGINE_NAME
    assert out["copy_engine"]["mode"] == "manual_copy"
    assert out["ready_for_ads"] is True
    mock_ffmpeg.assert_called_once()
