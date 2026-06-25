"""Tests afrodita_env_debug runtime diagnostics."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from core.afrodita_env_debug import (
    get_env_debug,
    parse_bool,
    resolve_afrodita_env,
    salvage_embedded_env,
    scan_misconfigured_railway_env,
)
from services.afrodita_unified_control import get_global_status


def test_parse_bool():
    assert parse_bool(None) is False
    assert parse_bool("true") is True
    assert parse_bool("TRUE") is True
    assert parse_bool("1") is True
    assert parse_bool("yes") is True
    assert parse_bool("t") is True
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
    assert debug["resolution"]["AFRODITA_EXECUTION_ENABLED"] == "env:AFRODITA_EXECUTION_ENABLED"


def test_salvage_execution_from_static_dir_typo():
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("AFRODITA_EXECUTION_ENABLED", "AFRODITA_READ_ONLY_MODE", "STATIC_DIR")
    }
    env["STATIC_DIR"] = '/app/""""/data/static"AFRODITA_EXECUTION_ENABLED=true'
    with patch.dict(os.environ, env, clear=True):
        salvaged, source = salvage_embedded_env("AFRODITA_EXECUTION_ENABLED")
        resolved = resolve_afrodita_env()
    assert salvaged == "true"
    assert source == "STATIC_DIR"
    assert resolved["parsed"]["execution_enabled"] is True
    assert resolved["parsed"]["writes_enabled"] is True
    assert resolved["salvaged_from_misconfigured_env"] is True


def test_legacy_rh_agent_alias():
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("AFRODITA_EXECUTION_ENABLED", "AFRODITA_RH_AGENT_ENABLED")
    }
    env["AFRODITA_RH_AGENT_ENABLED"] = "true"
    with patch.dict(os.environ, env, clear=True):
        resolved = resolve_afrodita_env()
    assert resolved["parsed"]["execution_enabled"] is True
    assert resolved["resolution"]["AFRODITA_EXECUTION_ENABLED"] == "env:AFRODITA_RH_AGENT_ENABLED"


def test_scan_misconfigured_railway_env():
    env = {
        k: v
        for k, v in os.environ.items()
        if k != "STATIC_DIR"
    }
    env["STATIC_DIR"] = '/data/static"AFRODITA_EXECUTION_ENABLED=true'
    with patch.dict(os.environ, env, clear=True):
        audit = scan_misconfigured_railway_env()
    assert audit["count"] >= 1
    assert audit["misconfigured_env_vars"][0]["host_var"] == "STATIC_DIR"


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
