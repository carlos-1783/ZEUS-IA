"""Tests TeamFlow full system audit."""

from __future__ import annotations

from services.teamflow_state_v1 import VALID_STATUSES, can_transition


def test_valid_transitions():
    assert can_transition("draft", "pending")
    assert not can_transition("completed", "draft")
    assert len(VALID_STATUSES) >= 5


def test_audit_id_constant():
    from services.teamflow_audit_service_v1 import AUDIT_ID, FLOW_SOURCES

    assert AUDIT_ID == "teamflow_full_system_audit"
    assert "JUSTICIA" in FLOW_SOURCES
