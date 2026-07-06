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
    assert payload["system_state"] in ("CONTROLLED_UNTRUSTED", "ORCHESTRATION_ACTIVE")
    assert payload["visibility"] == "FULL"
    assert "flags" in payload
    assert len(payload["agents"]) == 6
    assert all("execution_mode" in a for a in payload["agents"])
    zeus = next(a for a in payload["agents"] if a["name"] == "ZEUS CORE")
    assert zeus["status"] in ("REAL", "PARTIAL", "DISCONNECTED")


def test_zeus_core_real_when_orchestration_flags_on():
    import os
    from unittest.mock import patch

    env = {
        "ZEUS_CORE_ENABLED": "true",
        "ZEUS_AGENT_ENABLED": "true",
        "RAFAEL_EXECUTION_ENABLED": "true",
        "AFRODITA_EXECUTION_ENABLED": "true",
        "THALOS_EXECUTION_ENABLED": "true",
        "JUSTICE_REAL_AUDIT_ENABLED": "true",
        "ZEUS_EVENT_BUS_ENABLED": "true",
        "ZEUS_AUTOMATION_ENGINE_ENABLED": "true",
    }
    with patch.dict(os.environ, env, clear=False):
        payload = execution_status_payload()
    zeus = next(a for a in payload["agents"] if a["name"] == "ZEUS CORE")
    assert zeus["status"] == "REAL"
    assert zeus["execution_ready"] is True
    assert payload["zeus_core_orchestration_active"] is True
    assert payload["summary"]["execution_ready_count"] >= 1
