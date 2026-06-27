"""Tests PERSEO V2 status and audit."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from services.perseo_audit_service_v1 import build_audit_report, build_feature_status_map


def test_v2_feature_map_includes_publishing():
    features = build_feature_status_map(None)
    assert "publishing" in features
    assert features["publishing"]["endpoint"]


def test_v2_audit_report_has_engines():
    with patch("services.perseo_audit_service_v1.get_execution_status") as gs:
        gs.return_value = {
            "execution_mode": "SIMULATED",
            "writes_enabled": False,
            "db_status": {"connected": True},
            "modules": {},
        }
        report = build_audit_report(MagicMock())
    assert report["project"] == "PERSEO_AGENT"
    assert "video_editing_audit" in report


def test_v2_video_broken_without_s3_when_enabled():
    with patch("services.perseo_audit_service_v1.get_execution_status") as gs:
        gs.return_value = {"execution_mode": "REAL", "writes_enabled": True, "modules": {}}
        with patch("services.perseo_audit_service_v1._ffmpeg_available", return_value=True):
            with patch("services.perseo_audit_service_v1.settings.PERSEO_V2_ENABLED", True):
                with patch("services.perseo_storage_v2.s3_configured", return_value=False):
                    features = build_feature_status_map(None)
    assert features["video_editing"]["status"] == "BROKEN"
