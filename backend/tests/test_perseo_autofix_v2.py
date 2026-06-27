"""Tests PERSEO V2 autofix — AI, pipeline, audit modules."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from services.perseo_audit_service_v1 import build_feature_status_map
from services.perseo_ai_service_v2 import openai_configured


def test_audit_includes_ai_modules():
    with patch("services.perseo_audit_service_v1.get_execution_status") as gs:
        gs.return_value = {"execution_mode": "REAL", "writes_enabled": True, "modules": {}}
        with patch("services.perseo_audit_service_v1.openai_configured", return_value=True):
            features = build_feature_status_map(None)
    assert features["image_analyzer"]["status"] == "REAL"
    assert features["pipeline"]["endpoint"] == "/api/v1/perseo/v2/pipeline/run"
    assert "video_generation" in features


def test_ai_fallback_without_openai():
    with patch("services.perseo_ai_service_v2.openai_configured", return_value=False):
        from services.perseo_ai_service_v2 import recommend_video_ai

        out = recommend_video_ai({"duration_seconds": 30, "tone": "calm", "platform": "meta"})
    assert out.get("ai_powered") is False


def test_pipeline_status_structure():
    from services.perseo_pipeline_v2 import pipeline_status, PIPELINE_STAGES

    with patch("services.perseo_pipeline_v2.get_execution_status") as gs:
        gs.return_value = {"execution_mode": "REAL", "writes_enabled": True}
        st = pipeline_status(None)
    assert st["orchestrator"] == "ZEUS_CORE"
    assert st["stages"] == PIPELINE_STAGES
