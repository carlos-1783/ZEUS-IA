"""Tests for zeus_production_stabilization_v1 — env, handlers, cross-module events."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from config.afrodita_flags_v1 import get_afrodita_safety_flags, reset_afrodita_flag_warnings
from core.afrodita_env_debug import resolve_afrodita_env
from services.automation.handlers import (
    PRODUCTION_REAL_ACTION_HANDLERS,
    resolve_handler,
)
from services.automation.handlers.generic_internal import (
    GENERIC_INTERNAL_HANDLER_NAME,
    handle_soft_disabled_generic,
)
from services.automation.handlers.production_real_v1 import HANDLER_NAME
from services.zeus_cross_module_events_v1 import EVENT_TARGETS, emit_cross_module_event
from services.zeus_production_stabilization_v1 import (
    FIX_ID,
    validate_phase_1_env,
)


@pytest.fixture(autouse=True)
def _clear_flag_warnings():
    reset_afrodita_flag_warnings()
    yield
    reset_afrodita_flag_warnings()


def test_production_real_handlers_registered():
    assert set(PRODUCTION_REAL_ACTION_HANDLERS) == {
        "invoice_sent",
        "document_signed",
        "contract_creator_rrhh",
        "ads_campaign_builder",
    }
    assert resolve_handler("RAFAEL", "invoice_sent").__name__ == "handle_invoice_sent"
    assert resolve_handler("JUSTICIA", "document_signed").__name__ == "handle_document_signed"
    assert resolve_handler("AFRODITA", "contract_creator_rrhh").__name__ == "handle_contract_creator_rrhh"
    assert resolve_handler("PERSEO", "ads_campaign_builder").__name__ == "handle_ads_campaign_builder"
    assert HANDLER_NAME == "PRODUCTION_REAL_V1"


def test_soft_disable_generic_when_stabilization_on():
    with patch.dict(os.environ, {"ZEUS_PRODUCTION_STABILIZATION": "true"}, clear=False):
        handler = resolve_handler("ZEUS", "pricing_review")
        assert handler is handle_soft_disabled_generic
        activity = MagicMock(action_type="pricing_review", agent_name="ZEUS", details={})
        out = handler(activity)
        assert out["status"] == "skipped"
        assert out["executed_handler"] == "SOFT_DISABLED_GENERIC"


def test_generic_fallback_when_stabilization_off():
    with patch.dict(os.environ, {"ZEUS_PRODUCTION_STABILIZATION": "false"}, clear=False):
        handler = resolve_handler("ZEUS", "pricing_review")
        assert handler.__name__ == "handle_generic_internal"


def test_phase_1_passes_with_execution_flags(monkeypatch):
    monkeypatch.setenv("AFRODITA_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("AFRODITA_READ_ONLY_MODE", "false")
    monkeypatch.setenv("AFRODITA_OPS_ENABLED", "true")
    monkeypatch.setenv("AFRODITA_OPS_READ_ONLY", "false")
    report = validate_phase_1_env()
    assert report["fix_id"] == FIX_ID
    assert report["writes_enabled"] is True
    assert report["execution_mode"] == "REAL"
    assert report["passed"] is True


def test_railway_production_defaults_when_env_missing(monkeypatch):
    monkeypatch.delenv("AFRODITA_EXECUTION_ENABLED", raising=False)
    monkeypatch.delenv("AFRODITA_READ_ONLY_MODE", raising=False)
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.setenv("ZEUS_PRODUCTION_STABILIZATION", "true")
    resolved = resolve_afrodita_env()
    assert resolved["parsed"]["execution_enabled"] is True
    assert resolved["parsed"]["read_only"] is False
    assert resolved["parsed"]["writes_enabled"] is True
    flags = get_afrodita_safety_flags()
    assert flags["writes_enabled"] is True


def test_cross_module_event_targets():
    assert "employee_created" in EVENT_TARGETS
    assert "ops" in EVENT_TARGETS["employee_created"]
    assert "contract_rrhh_created" in EVENT_TARGETS


def test_emit_cross_module_event_workspace_target():
    db = MagicMock()
    user = MagicMock(id=1)
    with patch(
        "services.workspace_playbook_service_v1.persist_execution_playbook",
        return_value=MagicMock(id=42),
    ) as persist:
        with patch(
            "services.workspace_playbook_writer_v1.write_ops_playbook",
        ) as write_ops:
            with patch("app.models.compliance_event.ComplianceEvent"):
                result = emit_cross_module_event(
                    db,
                    user,
                    "employee_created",
                    {"employee_id": 7},
                )
    assert result["ok"] is True
    persist.assert_called_once()
    write_ops.assert_called_once()
