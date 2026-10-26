"""Saneado central del entorno (app/core/env_sanitize.py, invocado al importar app/core/config.py).

Cada valor de os.environ: recorte de espacios/saltos de linea en los extremos + UN par de comillas
envolventes iguales fuera (como python-dotenv). Comillas internas intactas. Se comprueba la regla pura,
el cableado real (importar config sanea os.environ antes de Settings y de los resolvedores) y el efecto en
el modo de ejecucion efectivo de AFRODITA con el resolvedor real (get_global_status sobre la BD de tests).
"""
from __future__ import annotations

import importlib
import logging
import os
import sys
from unittest.mock import patch

import pytest

from app.core.env_sanitize import clean_env_value, sanitize_environ


@pytest.mark.parametrize(
    "raw, expected",
    [
        ('"true"', "true"),
        ("  /data/static  ", "/data/static"),
        ("'activo'", "activo"),
        ("  \"true\"\n", "true"),
        ("sin-comillas", "sin-comillas"),
        ("postgresql://u:p@h:5432/db", "postgresql://u:p@h:5432/db"),
        ('{"a":"b"}', '{"a":"b"}'),             # JSON con comillas internas: intacto
        ('"{"a":"b"}"', '{"a":"b"}'),           # solo el par exterior
        ("'{\"a\":\"b\"}'", '{"a":"b"}'),
        ('"abc\'', '"abc\''),                  # comillas distintas: no se tocan
        ('"', '"'),                             # una sola comilla: no es un par
        ('""', ""),
        ('" con espacios dentro "', " con espacios dentro "),  # dentro de las comillas se respeta
        ('a "b" c', 'a "b" c'),
        ("", ""),
    ],
)
def test_clean_env_value_rule(raw, expected):
    assert clean_env_value(raw) == expected


def test_sanitize_environ_reports_only_changed_names_and_is_idempotent(caplog):
    env = {"A": '"true"', "B": "intacto", "C": '{"a":"b"}', "D": "  x  "}
    with caplog.at_level(logging.WARNING, logger="zeus.config"):
        changed = sanitize_environ(env)
    assert sorted(changed) == ["A", "D"]
    assert env == {"A": "true", "B": "intacto", "C": '{"a":"b"}', "D": "x"}
    # el log lleva nombres, nunca valores
    assert "A, D" in caplog.text and '"true"' not in caplog.text
    assert sanitize_environ(env) == []


def _reload_config():
    for mod in ("app.core.config", "app.main"):
        sys.modules.pop(mod, None)
    return importlib.import_module("app.core.config")


def _base_env(**extra):
    drop = ("STATIC_DIR", "ZEUS_STATIC_DIR", "AFRODITA_EXECUTION_ENABLED", "AFRODITA_READ_ONLY_MODE",
            "AFRODITA_RH_AGENT_ENABLED", "R2_ACCOUNT_ID")
    env = {k: v for k, v in os.environ.items() if k not in drop}
    env.update(extra)
    return env


def test_importing_config_sanitizes_os_environ_before_settings():
    env = _base_env(
        STATIC_DIR="  /data/static  ",
        AFRODITA_EXECUTION_ENABLED='"true"',
        THALOS_ENABLED="'false'",
        ZEUS_TEST_JSON_CFG='{"a":"b"}',
    )
    with patch.dict(os.environ, env, clear=True):
        cfg = _reload_config()
        assert os.environ["STATIC_DIR"] == "/data/static"
        assert os.environ["AFRODITA_EXECUTION_ENABLED"] == "true"
        assert os.environ["ZEUS_TEST_JSON_CFG"] == '{"a":"b"}'
        assert cfg.settings.AFRODITA_EXECUTION_ENABLED is True
        assert cfg.settings.THALOS_ENABLED is False
        assert cfg.settings.STATIC_DIR.replace("\\", "/").endswith("/data/static")
    _reload_config()  # deja config como estaba para el resto del proceso


def test_quoted_afrodita_flag_resolves_to_real_execution_mode():
    from app.db.base import SessionLocal
    from core.afrodita_env_debug import parse_bool
    from services.afrodita_unified_control import get_global_status

    env = _base_env(AFRODITA_EXECUTION_ENABLED='"true"', AFRODITA_READ_ONLY_MODE='"false"')
    db = SessionLocal()
    try:
        with patch.dict(os.environ, env, clear=True):
            # Control (el test no es vacuo): con el valor crudo de Railway el resolvedor real NO ve REAL.
            assert parse_bool(os.environ["AFRODITA_EXECUTION_ENABLED"]) is False
            assert get_global_status(db)["execution_mode"] == "SIMULATED"
            # Arranque real: importar config sanea el entorno -> mismo resolvedor, modo REAL.
            _reload_config()
            status = get_global_status(db)
            assert status["db_connected"] is True
            assert status["execution_enabled"] is True and status["read_only_mode"] is False
            assert status["writes_enabled"] is True
            assert status["execution_mode"] == "REAL"
    finally:
        db.close()
    _reload_config()


def test_multiline_garbage_in_static_dir_is_not_hidden(caplog):
    """Otra variable pegada dentro de STATIC_DIR NO se arregla aqui: solo se recortan los extremos, el
    interior sigue ahi, el detector de STATIC_DIR lo avisa y R2_ACCOUNT_ID sigue sin existir."""
    garbage = "/data/static\nR2_ACCOUNT_ID=valor-falso-de-test\n"
    with patch.dict(os.environ, _base_env(STATIC_DIR=garbage), clear=True):
        with caplog.at_level(logging.WARNING, logger="zeus.config"):
            cfg = _reload_config()
        assert os.environ["STATIC_DIR"] == "/data/static\nR2_ACCOUNT_ID=valor-falso-de-test"
        assert "R2_ACCOUNT_ID" not in os.environ
        assert cfg.settings.R2_ACCOUNT_ID == ""
        assert "STATIC_DIR sanitized" in caplog.text
    _reload_config()
