"""Fase 2 / Step 2 — validate_integrations ya no da OpenAI/Stripe por buenos por existir SECRET_KEY."""

from services import object_storage
from services.teamflow_engine import TeamFlowEngine


def test_checks_follow_real_credentials(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "presente")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("STRIPE_API_KEY", raising=False)
    monkeypatch.setattr(object_storage, "is_configured", lambda: False)
    r = TeamFlowEngine().validate_integrations()
    assert r["checks"] == {"openai": False, "stripe": False, "object_storage": False}
    assert r["status"] == "degraded" and r["check_type"] == "configured_only"
    assert "agent_to_agent" not in r["checks"]


def test_ready_only_when_all_configured(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    monkeypatch.setenv("STRIPE_API_KEY", "sk_test_x")
    monkeypatch.setattr(object_storage, "is_configured", lambda: True)
    r = TeamFlowEngine().validate_integrations()
    assert r["status"] == "ready" and r["missing"] == []
