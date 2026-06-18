"""Tests thalos_control_layer_v1 — execution modes and response contract."""

from __future__ import annotations

from unittest.mock import patch

from app.core.config import settings
from services.thalos_control_layer_v1 import (
    MODULE_CLASSIFICATION,
    build_metadata,
    can_run_active_execution,
    global_status_payload,
    resolve_execution_mode,
    wrap_response,
)


def test_default_mode_is_simulation_for_heuristic_modules():
    assert resolve_execution_mode("log_monitor") == "SIMULATION"
    assert resolve_execution_mode("text_analysis") == "SIMULATION"


def test_auditoria_and_workspace_are_real_safe():
    assert resolve_execution_mode("auditoria_real") == "REAL_SAFE"
    assert resolve_execution_mode("workspace") == "REAL_SAFE"


def test_backup_requires_execution_and_backup_flags():
    with patch.object(settings, "THALOS_EXECUTION_ENABLED", False):
        assert resolve_execution_mode("backup_system") == "SIMULATION"
    with patch.object(settings, "THALOS_EXECUTION_ENABLED", True):
        with patch.object(settings, "THALOS_BACKUP_ENABLED", False):
            assert resolve_execution_mode("backup_system") == "SIMULATION"
        with patch.object(settings, "THALOS_BACKUP_ENABLED", True):
            assert resolve_execution_mode("backup_system") == "REAL_ACTIVE"


def test_wrap_response_includes_required_fields():
    body = {"ok": True}
    out = wrap_response(body, "auditoria_real", data_origin="backend", real_execution=True)
    assert out["ok"] is True
    assert out["execution_mode"] == "REAL_SAFE"
    assert out["data_origin"] == "backend"
    assert out["real_execution"] is True
    assert out["thalos_control"]["module"] == "auditoria_real"
    assert out["thalos_control"]["ui_badge"] == "REAL"


def test_can_run_active_blocks_destructive_when_simulation():
    assert can_run_active_execution("backup_system", "trigger_backup") is False
    assert can_run_active_execution("auditoria_real", "security_monitor") is True


def test_global_status_payload_structure():
    payload = global_status_payload()
    assert "system_default_mode" in payload
    assert payload["execution_mode"] == "REAL_SAFE"
    assert "THALOS_REAL_LOGS_ENABLED" in payload["thalos_control"]["flags"]
    assert payload["module_classification"] == MODULE_CLASSIFICATION


def test_build_metadata_origin_mock():
    meta = build_metadata("text_analysis", data_origin="mock", real_execution=False)
    assert meta.data_origin == "mock"
    assert meta.real_execution is False
    assert meta.ui_badge == "SIMULADO"
