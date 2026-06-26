"""Tests zeus_execution_controller_v1."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from services.zeus_data_pipeline_v1 import attach_pipeline_metadata, pipeline_definition
from services.zeus_execution_controller_v1 import get_execution_status, get_module_statuses


def test_pipeline_definition_flow():
    p = pipeline_definition()
    assert p["flow"] == ["RRHH", "OPS", "WORKSPACE"]
    assert p["sink"] == "workspace_playbooks"


def test_attach_pipeline_metadata():
    out = attach_pipeline_metadata("rrhh", {"checkin_id": 1})
    assert out["zeus_pipeline"]["stage"] == "rrhh"
    assert out["zeus_pipeline"]["next_stage"] == "ops"


def test_module_statuses_simulated_when_writes_off():
    db = MagicMock()
    db.execute.return_value = None
    with patch.dict(
        os.environ,
        {"AFRODITA_EXECUTION_ENABLED": "false", "AFRODITA_READ_ONLY_MODE": "false"},
        clear=False,
    ):
        status = get_execution_status(db)
    assert status["execution_mode"] == "SIMULATED"
    assert status["writes_enabled"] is False
    assert status["flag_consistency"] in ("UNIFIED", "DEGRADED")
    assert "rrhh" in status["modules"]
    assert status["modules"]["ops"]["write"] is False


def test_module_statuses_error_when_db_down():
    db = MagicMock()
    db.execute.side_effect = RuntimeError("db down")
    status = get_execution_status(db)
    assert status["execution_mode"] == "ERROR"
    assert status["db_status"]["connected"] is False
    mods = get_module_statuses(db, status["afrodita"])
    assert mods["rrhh"]["status"] == "ERROR"
