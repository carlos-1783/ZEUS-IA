"""Tests PERSEO Video Engine v3."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.perseo_video_engine_v3 import (
    ENGINE_VERSION,
    _is_generic_copy,
    _limit_words,
    _validate_script,
    video_engine_v3_configured,
)


def test_limit_words_caps_at_15():
    text = " ".join(f"w{i}" for i in range(30))
    assert len(_limit_words(text).split()) == 15


def test_validate_script_rejects_missing_cta():
    with pytest.raises(Exception) as exc:
        _validate_script({"hook": "a b", "problem": "c d", "solution": "e f", "cta": ""})
    assert "invalid_script" in str(exc.value.detail) or "generic" in str(exc.value.detail)


def test_validate_script_rejects_generic():
    script = {
        "hook": "descubre más sobre nosotros",
        "problem": "sin problema real",
        "solution": "somos líderes siempre",
        "cta": "descubre más hoy",
    }
    with pytest.raises(Exception):
        _validate_script(script)


def test_valid_conversion_script_passes():
    script = {
        "hook": "¿Sigues perdiendo ventas cada día?",
        "problem": "Tu mensaje no convierte en redes",
        "solution": "PERSEO crea vídeos que venden",
        "cta": "Reserva demo ahora — plazas limitadas",
    }
    assert not _is_generic_copy(script)
    _validate_script(script)


def test_engine_version_constant():
    assert ENGINE_VERSION == "3.0.0"


@patch("services.perseo_video_engine_v3._ffmpeg_path", return_value="/usr/bin/ffmpeg")
def test_video_engine_v3_configured(_mock):
    assert video_engine_v3_configured() is True


def test_audit_includes_video_engine_v3():
    from services.perseo_audit_service_v1 import build_feature_status_map

    features = build_feature_status_map(None)
    assert "video_engine_v3" in features
    assert features["video_engine_v3"]["endpoint"] == "POST /api/v1/perseo/video/generate"


@patch("services.perseo_video_engine_v3._run_ffmpeg_pipeline")
@patch("services.perseo_video_engine_v3._persist_video")
@patch("services.perseo_video_engine_v3._crm_integrate")
@patch("services.perseo_video_engine_v3._resolve_image_path")
@patch("services.perseo_video_engine_v3._generate_conversion_copy")
@patch("services.perseo_video_engine_v3.resolve_tenant_company")
@patch("services.perseo_video_engine_v3.get_execution_status")
@patch("services.perseo_video_engine_v3._ffmpeg_path", return_value="/usr/bin/ffmpeg")
def test_generate_perseo_video_v3_orchestration(
    _ff,
    mock_exec,
    mock_tenant,
    mock_copy,
    mock_img,
    mock_crm,
    mock_store,
    mock_ffmpeg,
):
    from services.perseo_video_engine_v3 import generate_perseo_video_v3

    mock_exec.return_value = {"execution_mode": "REAL", "writes_enabled": True}
    company = MagicMock()
    company.id = 7
    company.slug = "demo-co"
    company.company_name = "Demo Co"
    mock_tenant.return_value = (company, 7)
    mock_copy.return_value = {
        "script": {
            "hook": "¿Aún sin clientes nuevos?",
            "problem": "Tu competencia te adelanta cada día",
            "solution": "Demo Co multiplica tus leads",
            "cta": "Pide tu demo gratis hoy",
        },
        "ai_powered": True,
        "mode": "conversion_only",
    }
    mock_img.return_value = Path("/tmp/test.jpg")
    mock_store.return_value = {"video_url": "/static/uploads/videos/tenant_7/x.mp4", "storage": "local"}
    mock_crm.return_value = {
        "crm_saved": True,
        "store_video_asset": True,
        "link_to_campaign": True,
        "attach_to_lead": False,
    }

    user = MagicMock()
    user.id = 1
    db = MagicMock()
    out = generate_perseo_video_v3(
        db,
        user,
        tenant_id="7",
        image_url="https://example.com/p.jpg",
        product_info="servicio premium",
    )
    assert out["success"] is True
    assert out["version"] == "3.0.0"
    assert out["video_url"].endswith(".mp4")
    assert out["script"]["cta"]
    mock_ffmpeg.assert_called_once()
