"""Tests afrodita_unified_control v1."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from services.afrodita_unified_control import (
    assert_can_write,
    get_global_status,
    resolve_execution_mode,
    wrap_response,
    writes_enabled,
)


def test_resolve_execution_mode_error_when_db_down():
    assert resolve_execution_mode(db_connected=False, writes_on=True) == "ERROR"
    assert resolve_execution_mode(db_connected=False, writes_on=False) == "ERROR"


def test_resolve_execution_mode_real_when_writes_on():
    assert resolve_execution_mode(db_connected=True, writes_on=True) == "REAL"
    assert resolve_execution_mode(db_connected=True, writes_on=False) == "SIMULATED"


def test_get_global_status_error_when_db_probe_fails():
    db = MagicMock()
    db.execute.side_effect = RuntimeError("db down")
    payload = get_global_status(db)
    assert payload["execution_mode"] == "ERROR"
    assert payload["db_connected"] is False


def test_assert_can_write_403_when_disabled():
    db = MagicMock()
    with patch("services.afrodita_unified_control.probe_db_connected", return_value=True):
        with patch("services.afrodita_unified_control.writes_enabled", return_value=False):
            with pytest.raises(HTTPException) as exc:
                assert_can_write(db)
    assert exc.value.status_code == 403


def test_wrap_response_dry_run_success_false():
    db = MagicMock()
    db.execute.return_value = None
    with patch.dict(
        os.environ,
        {"AFRODITA_EXECUTION_ENABLED": "false", "AFRODITA_READ_ONLY_MODE": "false"},
        clear=False,
    ):
        out = wrap_response({"success": True, "note": "x"}, db=db, data_origin="mock", dry_run=True)
    assert out["success"] is False
    assert out["dry_run"] is True
    assert out["execution_mode"] == "SIMULATED"


def test_wrap_response_read_only_real_execution_follows_global_mode():
    db = MagicMock()
    db.execute.return_value = None
    with patch.dict(
        os.environ,
        {"AFRODITA_EXECUTION_ENABLED": "true", "AFRODITA_READ_ONLY_MODE": "false"},
        clear=False,
    ):
        out = wrap_response({"success": True}, db=db, data_origin="backend", read_only=True)
    assert out["execution_mode"] == "REAL"
    assert out["real_execution"] is True
