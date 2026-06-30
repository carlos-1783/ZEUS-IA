"""STATIC_DIR sanitization — corrupted Railway env must not crash startup."""

from __future__ import annotations

import importlib
import os
import sys
from unittest.mock import patch


def _reload_config():
    for mod in ("app.core.config", "app.main"):
        if mod in sys.modules:
            del sys.modules[mod]
    return importlib.import_module("app.core.config")


def test_corrupted_static_dir_sanitized_to_data_static():
    corrupted = '/data/static"AFRODITA_EXECUTION_ENABLED=true'
    env = {k: v for k, v in os.environ.items() if k not in ("STATIC_DIR", "ZEUS_STATIC_DIR")}
    env["STATIC_DIR"] = corrupted
    with patch.dict(os.environ, env, clear=True):
        cfg = _reload_config()
        assert "AFRODITA" not in cfg.settings.STATIC_DIR
        assert cfg.settings.STATIC_DIR.replace("\\", "/").endswith("/data/static")
        assert len(cfg.settings.STATIC_DIR) < 64


def test_corrupted_zeus_static_dir_via_pydantic():
    corrupted = '/app/""""/data/static"AFRODITA_EXECUTION_ENABLED=true'
    env = {k: v for k, v in os.environ.items() if k not in ("STATIC_DIR", "ZEUS_STATIC_DIR")}
    env["ZEUS_STATIC_DIR"] = corrupted
    with patch.dict(os.environ, env, clear=True):
        cfg = _reload_config()
        assert "AFRODITA" not in cfg.settings.STATIC_DIR
        assert cfg.settings.STATIC_DIR.replace("\\", "/").endswith("/data/static")


def test_ensure_static_root_ready_never_raises_on_absurd_path():
    absurd = "/data/static" + "X" * 500 + "AFRODITA_EXECUTION_ENABLED=true"
    with patch.dict(os.environ, {"ZEUS_STATIC_DIR": absurd}, clear=False):
        cfg = _reload_config()
        root = cfg.ensure_static_root_ready()
        assert os.path.isdir(root)
        assert len(root) < 300
