"""Tests for zeus_crm_payment_risk_v1 and Phase C payment risk flow."""

import os
from unittest.mock import MagicMock, patch

from services.zeus_crm_payment_risk_v1 import evaluate_payment_risk, handle_crm_payment_risk
from services.zeus_phase_c_test_v1 import check_phase_c_env, run_test_payment_risk_flow


def test_evaluate_payment_risk_high():
    out = evaluate_payment_risk({"client_id": "c1", "amount": 1250})
    assert out["risk"] == "high"
    assert out["risk_level"] == "high"


def test_evaluate_payment_risk_medium():
    out = evaluate_payment_risk({"amount": 500})
    assert out["risk"] == "medium"


def test_evaluate_payment_risk_low():
    out = evaluate_payment_risk({"amount": 100})
    assert out["risk"] == "low"


def test_handle_crm_payment_risk_emits_for_high():
    db = MagicMock()
    user = MagicMock()
    user.id = 1
    with patch("services.zeus_event_bus_v1.emit_event", return_value={"active": True}) as mock_emit:
        with patch("services.zeus_automation_audit_v1.record_automation_audit"):
            out = handle_crm_payment_risk(db, user, {"client_id": "x", "amount": 1500})
    assert out["payment_risk_emitted"] is True
    mock_emit.assert_called_once()
    assert mock_emit.call_args.kwargs["event_name"] == "payment_risk"


def test_handle_crm_payment_risk_skips_emit_for_low():
    db = MagicMock()
    user = MagicMock()
    user.id = 1
    with patch("services.zeus_event_bus_v1.emit_event") as mock_emit:
        with patch("services.zeus_automation_audit_v1.record_automation_audit"):
            out = handle_crm_payment_risk(db, user, {"amount": 50})
    assert out["payment_risk_emitted"] is False
    mock_emit.assert_not_called()


def test_check_phase_c_env_all_ok():
    env = {
        "RAFAEL_EXECUTION_ENABLED": "true",
        "ZEUS_EVENT_BUS_ENABLED": "true",
        "ZEUS_AUTOMATION_ENGINE_ENABLED": "true",
    }
    with patch.dict(os.environ, env, clear=False):
        out = check_phase_c_env()
    assert out["all_ok"] is True


def test_run_test_payment_risk_flow_blocks_when_flags_missing():
    db = MagicMock()
    user = MagicMock()
    with patch.dict(os.environ, {}, clear=True):
        out = run_test_payment_risk_flow(db, user)
    assert out["triggered"] is False
    assert out["reason"] == "phase_c_flags_incomplete"


def test_run_test_payment_risk_flow_emits_when_ready():
    db = MagicMock()
    user = MagicMock()
    user.id = 1
    env = {
        "RAFAEL_EXECUTION_ENABLED": "true",
        "ZEUS_EVENT_BUS_ENABLED": "true",
        "ZEUS_AUTOMATION_ENGINE_ENABLED": "true",
    }
    bus_return = {
        "active": True,
        "pipeline": {
            "crm_payment_risk": {
                "evaluation": {"risk": "high", "amount": 1250},
                "payment_risk_emitted": True,
            }
        },
    }
    with patch.dict(os.environ, env, clear=False):
        with patch("services.zeus_event_bus_v1.emit_event", return_value=bus_return):
            with patch("services.zeus_automation_audit_v1.record_automation_audit"):
                out = run_test_payment_risk_flow(db, user)
    assert out["triggered"] is True
    assert out["risk"]["risk"] == "high"
    db.commit.assert_called_once()
