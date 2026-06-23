"""Tests afrodita_flag_safety_v1."""

from __future__ import annotations

import logging
import os
from unittest.mock import patch

import pytest

from config.afrodita_flags_v1 import get_afrodita_safety_flags, reset_afrodita_flag_warnings
from services.afrodita_control_layer_v1 import writes_enabled


@pytest.fixture(autouse=True)
def _clear_flag_warnings():
    reset_afrodita_flag_warnings()
    yield
    reset_afrodita_flag_warnings()


def test_missing_env_defaults_false_and_not_loaded(caplog):
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("AFRODITA_EXECUTION_ENABLED", "AFRODITA_READ_ONLY_MODE")
    }
    with patch.dict(os.environ, env, clear=True):
        reset_afrodita_flag_warnings()
        with caplog.at_level(logging.WARNING):
            flags = get_afrodita_safety_flags()

    assert flags["AFRODITA_EXECUTION_ENABLED"] is False
    assert flags["AFRODITA_READ_ONLY_MODE"] is False
    assert flags["flags_loaded"] is False
    assert flags["writes_enabled"] is False
    assert any("AFRODITA_EXECUTION_ENABLED missing" in r.message for r in caplog.records)
    assert any("AFRODITA_READ_ONLY_MODE missing" in r.message for r in caplog.records)


def test_writes_enabled_only_when_both_loaded_and_execution_on():
    with patch.dict(
        os.environ,
        {
            "AFRODITA_EXECUTION_ENABLED": "true",
            "AFRODITA_READ_ONLY_MODE": "false",
        },
        clear=False,
    ):
        flags = get_afrodita_safety_flags()
        assert flags["flags_loaded"] is True
        assert flags["writes_enabled"] is True
        assert writes_enabled() is True


def test_writes_enabled_false_when_read_only_true():
    with patch.dict(
        os.environ,
        {
            "AFRODITA_EXECUTION_ENABLED": "true",
            "AFRODITA_READ_ONLY_MODE": "true",
        },
        clear=False,
    ):
        flags = get_afrodita_safety_flags()
        assert flags["flags_loaded"] is True
        assert flags["writes_enabled"] is False


def test_writes_enabled_false_when_only_execution_set():
    env = {
        k: v
        for k, v in os.environ.items()
        if k != "AFRODITA_READ_ONLY_MODE"
    }
    with patch.dict(os.environ, {**env, "AFRODITA_EXECUTION_ENABLED": "true"}, clear=True):
        flags = get_afrodita_safety_flags()
        assert flags["flags_loaded"] is False
        assert flags["writes_enabled"] is False
