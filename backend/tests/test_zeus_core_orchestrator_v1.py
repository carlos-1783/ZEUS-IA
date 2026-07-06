"""Tests for zeus_core_orchestrator_v1."""

import os
from unittest.mock import MagicMock, patch

from services.zeus_core_orchestrator_v1 import (
    check_core_orchestration_env,
    is_core_orchestration_active,
    zeus_core_orchestrate_payment_due,
)


def _full_core_env() -> dict:
    return {
        "ZEUS_CORE_ENABLED": "true",
        "ZEUS_AGENT_ENABLED": "true",
        "RAFAEL_EXECUTION_ENABLED": "true",
        "AFRODITA_EXECUTION_ENABLED": "true",
        "THALOS_EXECUTION_ENABLED": "true",
        "JUSTICE_REAL_AUDIT_ENABLED": "true",
    }


def test_check_core_orchestration_env_all_ok():
    with patch.dict(os.environ, _full_core_env(), clear=False):
        out = check_core_orchestration_env()
        assert out["all_ok"] is True
        assert is_core_orchestration_active() is True


def test_orchestrate_requires_user():
    db = MagicMock()
    with patch.dict(os.environ, _full_core_env(), clear=False):
        out = zeus_core_orchestrate_payment_due(db, None, {"amount": 1500})
    assert out["orchestrated"] is False
    assert out["reason"] == "user_required"


def test_orchestrate_high_risk_invokes_all_agents():
    db = MagicMock()
    user = MagicMock()
    user.id = 1
    with patch.dict(os.environ, _full_core_env(), clear=False):
        with patch("services.teamflow_persistence_v1.create_item", return_value={"id": "tf-1"}):
            with patch("services.zeus_analytics_real_v1.record_zeus_alert"):
                with patch("services.zeus_automation_audit_v1.record_automation_audit"):
                    out = zeus_core_orchestrate_payment_due(
                        db,
                        user,
                        {"client_id": "C-1", "name": "Test", "amount": 1500},
                    )
    assert out["orchestrated"] is True
    assert out["risk"] == "high"
    assert set(out["agents_invoked"]) == {"rafael", "afrodita", "justicia", "thalos"}


def test_orchestrate_low_risk_only_rafael():
    db = MagicMock()
    user = MagicMock()
    user.id = 1
    with patch.dict(os.environ, _full_core_env(), clear=False):
        with patch("services.zeus_automation_audit_v1.record_automation_audit"):
            out = zeus_core_orchestrate_payment_due(db, user, {"amount": 100})
    assert out["orchestrated"] is True
    assert out["agents_invoked"] == ["rafael"]
