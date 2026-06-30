"""Tests zeus_safe_lock_v1."""

from __future__ import annotations

import os
from unittest.mock import patch

from services.zeus_safe_lock_v1 import LOCK_ID, run_safe_lock


def test_lock_id():
    assert LOCK_ID == "zeus_safe_lock_v1"


def test_warns_when_execution_not_real():
    with patch.dict(
        os.environ,
        {
            "AFRODITA_EXECUTION_ENABLED": "false",
            "AFRODITA_READ_ONLY_MODE": "false",
            "ZEUS_AGENT_ENABLED": "true",
        },
        clear=False,
    ):
        report = run_safe_lock(
            execution_status={"execution_mode": "SIMULATED", "writes_enabled": False},
            log_warnings=False,
        )
    assert report["verified_real"] is False
    assert report["warning_count"] >= 1
    codes = {w["code"] for w in report["warnings"]}
    assert "execution_disabled" in codes or "execution_mode_not_real" in codes


def test_verified_real_when_flags_ok():
    with patch.dict(
        os.environ,
        {
            "AFRODITA_EXECUTION_ENABLED": "true",
            "AFRODITA_READ_ONLY_MODE": "false",
            "ZEUS_AGENT_ENABLED": "true",
        },
        clear=False,
    ):
        report = run_safe_lock(
            execution_status={"execution_mode": "REAL", "writes_enabled": True, "db_status": {"connected": True}},
            log_warnings=False,
        )
    assert report["verified_real"] is True
