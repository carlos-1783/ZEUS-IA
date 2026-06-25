"""Tests afrodita_ops_control_layer_v1 shim."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from services.afrodita_ops_control_layer_v1 import can_write_stock, global_status_payload, wrap_response


def test_ops_status_matches_global_simulated_by_default():
    payload = global_status_payload()
    assert payload["execution_mode"] == "SIMULATED"


def test_can_write_stock_requires_global_writes():
    with patch.dict(os.environ, {"AFRODITA_EXECUTION_ENABLED": "false"}, clear=False):
        assert can_write_stock() is False
    with patch.dict(
        os.environ,
        {
            "AFRODITA_EXECUTION_ENABLED": "true",
            "AFRODITA_READ_ONLY_MODE": "false",
        },
        clear=False,
    ):
        with patch("services.afrodita_unified_control.current_flags") as mock_flags:
            mock_flags.return_value = {
                "AFRODITA_ENABLE_STOCK_SYNC": True,
            }
            assert can_write_stock() is True


def test_ops_wrap_response_global_mode():
    db = MagicMock()
    db.execute.return_value = None
    out = wrap_response({"ok": True}, db=db, data_origin="backend", read_only=True)
    assert out["execution_mode"] in ("REAL", "SIMULATED", "ERROR")
    assert "afrodita_ops_control" not in out
