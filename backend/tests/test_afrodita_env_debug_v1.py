"""Tests afrodita_env_debug runtime diagnostics."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from core.afrodita_env_debug import get_env_debug, parse_bool
from services.afrodita_unified_control import get_global_status


def test_parse_bool():
    assert parse_bool(None) is False
    assert parse_bool("true") is True
    assert parse_bool("TRUE") is True
    assert parse_bool("1") is True
    assert parse_bool("yes") is True
    assert parse_bool("false") is False


def test_get_env_debug_railway_shape():
    with patch.dict(
        os.environ,
        {
            "AFRODITA_EXECUTION_ENABLED": "true",
            "AFRODITA_READ_ONLY_MODE": "false",
        },
        clear=False,
    ):
        debug = get_env_debug()
    assert debug["raw"]["AFRODITA_EXECUTION_ENABLED"] == "true"
    assert debug["raw"]["AFRODITA_READ_ONLY_MODE"] == "false"
    assert debug["parsed"]["writes_enabled"] is True


def test_real_mode_when_writes_and_db():
    db = MagicMock()
    db.execute.return_value = None
    with patch.dict(
        os.environ,
        {
            "AFRODITA_EXECUTION_ENABLED": "true",
            "AFRODITA_READ_ONLY_MODE": "false",
        },
        clear=False,
    ):
        status = get_global_status(db)
    assert status["writes_enabled"] is True
    assert status["db_connected"] is True
    assert status["execution_mode"] == "REAL"
