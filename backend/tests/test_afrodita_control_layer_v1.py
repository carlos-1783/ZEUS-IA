"""Tests afrodita_control_layer_v1."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.core.config import settings
from services.afrodita_control_layer_v1 import (
    MODULE_UI_BADGE,
    can_create_employee,
    can_execute_checkin,
    global_status_payload,
    parse_zeuscheck_code,
    validate_qr_freshness,
    wrap_response,
)


def test_default_flags_simulated():
    payload = global_status_payload()
    assert payload["system_default_mode"] == "SIMULATED"
    assert payload["AFRODITA_EXECUTION_ENABLED"] is False
    assert payload["writes_enabled"] is False


def test_can_execute_checkin_requires_flags():
    with patch.dict(os.environ, {"AFRODITA_EXECUTION_ENABLED": "false"}, clear=False):
        assert can_execute_checkin() is False
        assert can_create_employee() is False
    with patch.dict(
        os.environ,
        {"AFRODITA_EXECUTION_ENABLED": "true", "AFRODITA_READ_ONLY_MODE": "true"},
        clear=False,
    ):
        assert can_execute_checkin() is False
        assert can_create_employee() is False
    with patch.dict(
        os.environ,
        {"AFRODITA_EXECUTION_ENABLED": "true", "AFRODITA_READ_ONLY_MODE": "false"},
        clear=False,
    ):
        with patch.object(settings, "AFRODITA_USE_REAL_CHECKINS", True):
            assert can_execute_checkin() is True
        with patch.object(settings, "AFRODITA_USE_REAL_EMPLOYEES", True):
            assert can_create_employee() is True


def test_validate_qr_freshness_stale():
    old = (datetime.now(timezone.utc) - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    code = f"ZEUSCHECK|EMP1|{old}"
    ok, reason = validate_qr_freshness(code)
    assert ok is False
    assert "stale" in reason


def test_validate_qr_freshness_fresh():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ok, reason = validate_qr_freshness(f"ZEUSCHECK|EMP1|{now}")
    assert ok is True
    assert reason == "ok"


def test_parse_zeuscheck():
    parsed = parse_zeuscheck_code("ZEUSCHECK|EMP-001|2025-01-01T10:00:00Z")
    assert parsed is not None
    assert parsed["employee_id"] == "EMP-001"


def test_wrap_response_contract():
    out = wrap_response({"ok": True}, "employee_manager", data_origin="backend", real_execution=True)
    assert out["afrodita_control"]["ui_badge"] == MODULE_UI_BADGE["employee_manager"]
    assert out["real_execution"] is True
