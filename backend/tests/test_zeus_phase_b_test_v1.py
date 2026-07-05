"""Tests for zeus_phase_b_test_v1."""

import os
from unittest.mock import MagicMock, patch

from services.zeus_phase_b_test_v1 import check_phase_b_env, run_test_contract_flow


def test_check_phase_b_env_all_ok():
    env = {
        "AFRODITA_EXECUTION_ENABLED": "true",
        "AFRODITA_OPS_WRITES": "true",
        "ZEUS_EVENT_BUS_ENABLED": "true",
        "ZEUS_AUTOMATION_ENGINE_ENABLED": "true",
    }
    with patch.dict(os.environ, env, clear=False):
        out = check_phase_b_env()
    assert out["all_ok"] is True


def test_run_test_contract_flow_blocks_when_flags_missing():
    db = MagicMock()
    user = MagicMock()
    with patch.dict(os.environ, {}, clear=True):
        with patch("config.afrodita_flags_v1.get_afrodita_safety_flags", return_value={"AFRODITA_EXECUTION_ENABLED": False, "writes_enabled": False}):
            out = run_test_contract_flow(db, user)
    assert out["triggered"] is False
    assert out["reason"] == "phase_b_flags_incomplete"


def test_run_test_contract_flow_emits_when_ready():
    db = MagicMock()
    user = MagicMock()
    user.id = 1
    env = {
        "AFRODITA_EXECUTION_ENABLED": "true",
        "AFRODITA_OPS_WRITES": "true",
        "ZEUS_EVENT_BUS_ENABLED": "true",
        "ZEUS_AUTOMATION_ENGINE_ENABLED": "true",
    }
    with patch.dict(os.environ, env, clear=False):
        with patch("services.zeus_event_bus_v1.emit_event", return_value={"active": True, "pipeline": {"real_execution": True}}):
            with patch("services.zeus_automation_audit_v1.record_automation_audit"):
                out = run_test_contract_flow(db, user)
    assert out["triggered"] is True
    assert out["real_execution"] is True
    db.commit.assert_called_once()
