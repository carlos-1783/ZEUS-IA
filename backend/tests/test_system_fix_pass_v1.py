"""Tests system_fix_pass_v1."""

from __future__ import annotations

from services.automation.handlers import resolve_handler
from services.system_fix_pass_v1 import fix_pass_payload


def test_fix_pass_payload_structure():
    payload = fix_pass_payload()
    assert payload["audit_type"] == "system_fix_pass_v1"
    assert payload["system_state"] == "CONTROLLED_UNTRUSTED"
    assert payload["approval_flow"] == "CONNECTED"
    assert len(payload["agents"]) == 6
    assert payload["ready_for_phase_B"] is True


def test_resolve_handler_safe_fallback():
    handler = resolve_handler("UNKNOWN_AGENT", "unknown_action_xyz")
    assert handler is not None
    assert handler.__name__ == "handle_generic_internal"
