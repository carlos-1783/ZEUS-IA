"""Tests system_visibility_v1 Phase A."""

from __future__ import annotations

from services.execution_mode_v1 import normalize_execution_mode
from services.system_visibility_v1 import execution_status_payload


def test_normalize_execution_mode():
    assert normalize_execution_mode("REAL_ACTIVE") == "REAL"
    assert normalize_execution_mode("REAL_SAFE") == "READ_ONLY"
    assert normalize_execution_mode("SIMULATION") == "SIMULATED"
    assert normalize_execution_mode(None) == "SIMULATED"


def test_execution_status_payload():
    payload = execution_status_payload()
    assert payload["system_state"] == "CONTROLLED_UNTRUSTED"
    assert payload["visibility"] == "FULL"
    assert "flags" in payload
    assert len(payload["agents"]) == 6
    assert all("execution_mode" in a for a in payload["agents"])
    assert payload["summary"]["execution_ready_count"] == 0
