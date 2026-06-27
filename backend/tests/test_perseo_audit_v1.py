"""Tests perseo_audit_service_v1 and video engine guards."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from services.perseo_audit_service_v1 import build_audit_report, build_feature_status_map


def test_feature_status_map_has_all_targets():
    features = build_feature_status_map(None)
    for key in (
        "content_generation",
        "ads_generation",
        "video_editing",
        "image_generation",
        "publishing",
        "analytics",
        "automation",
    ):
        assert key in features
        assert features[key]["status"] in ("REAL", "SIMULATED", "BROKEN", "MISSING")


def test_audit_report_structure():
    report = build_audit_report(MagicMock())
    assert report["project"] == "PERSEO_AGENT"
    assert "feature_status_map" in report
    assert "fake_features_list" in report
    assert report["video_editing_audit"]["required_endpoint"] == "/api/v1/perseo/video/edit"
    assert report["video_editing_audit"]["endpoint_exists"] is True


def test_video_editing_broken_without_ffmpeg():
    with patch("services.perseo_audit_service_v1._ffmpeg_available", return_value=False):
        features = build_feature_status_map(None)
    assert features["video_editing"]["status"] == "BROKEN"
