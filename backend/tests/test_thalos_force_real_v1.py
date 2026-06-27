"""Tests THALOS force real mode."""

from __future__ import annotations

from services.thalos_log_parser import parse_log_line, parse_log_lines


def test_parser_detects_auth_failure():
    ev = parse_log_line("WARN failed login user=demo@x.com")
    assert ev is not None
    assert ev["event_type"] == "auth_failure"
    assert ev["severity"] in ("high", "medium", "critical")


def test_parser_batch():
    lines = ["INFO ok", "ERROR unauthorized access", "INFO heartbeat"]
    out = parse_log_lines(lines)
    assert len(out) == 3


def test_control_layer_real_modules():
    from services.thalos_control_layer_v1 import MODULE_CLASSIFICATION

    assert MODULE_CLASSIFICATION["log_monitor"] == "REAL_SAFE"
    assert MODULE_CLASSIFICATION["backup_system"] != "SIMULATION"
