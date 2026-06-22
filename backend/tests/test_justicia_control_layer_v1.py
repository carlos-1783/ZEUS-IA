"""Tests justicia_control_layer_v1 and justice_system_audit_v1."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.core.config import settings
from services.justicia_control_layer_v1 import (
    MODULE_UI_BADGE,
    global_status_payload,
    wrap_response,
)
from services.justice_system_audit_v1 import run_system_audit


def test_default_flags_simulated():
    payload = global_status_payload()
    assert payload["JUSTICE_REAL_AUDIT_ENABLED"] is False
    assert payload["execution_mode"] in ("SIMULATED", "READ_ONLY")


def test_real_audit_flag():
    with patch.object(settings, "JUSTICE_REAL_AUDIT_ENABLED", True):
        with patch.object(settings, "JUSTICE_READ_ONLY_MODE", False):
            payload = global_status_payload()
            assert payload["system_default_mode"] == "REAL"


def test_wrap_includes_audit_trace():
    out = wrap_response(
        {"ok": True},
        "system_audit",
        data_origin="backend",
        audit_trace=[{"kind": "table", "ref": "products"}],
    )
    assert out["audit_trace"][0]["ref"] == "products"
    assert out["justicia_control"]["ui_badge"] == MODULE_UI_BADGE["system_audit"]


def test_system_audit_structure():
    db = MagicMock()
    user = MagicMock()
    user.id = 1
    db.query.return_value.filter.return_value.scalar.return_value = 0
    db.query.return_value.scalar.return_value = 0

    with patch("services.justice_system_audit_v1._company_ids", return_value=[1]):
        with patch("services.justice_system_audit_v1._safe_count", return_value=(0, True)):
            body = run_system_audit(db, user)

    assert body["audit_id"] == "justice_deep_audit_v1"
    assert "conclusions" in body
    assert "domain_verdicts" in body
    assert body["system_status"] in ("OPERATIONAL", "UNTRUSTED", "BROKEN", "INVALID")
