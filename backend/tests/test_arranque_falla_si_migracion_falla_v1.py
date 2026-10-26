"""El arranque de produccion se DETIENE (exit != 0, Gunicorn no arranca) si la migracion falla.

Se ejecuta la cadena REAL de `startCommand` de railway.toml (leida del archivo, sin modificarla) con `sh`,
desde backend/, igual que en el contenedor. Solo se sustituye el ejecutable `gunicorn` por uno falso en el
PATH que imprime una marca y sale con 0: asi se sabe si la cadena llego a arrancar la API (y en Windows no
hace falta Gunicorn real). `python` y `alembic` son los del entorno del test.

Casos (PostgreSQL real, ZEUS_TEST_PG_URL con un rol que pueda CREATE/DROP DATABASE; BD temporales propias):
  - URL inalcanzable -> el stamp legacy no conecta -> exit != 0, sin Gunicorn.
  - BD en 0069 donde la migracion 0070 falla (sin tablas que necesita) -> exit != 0, sin Gunicorn.
  - CONTROL: BD ya en head -> la cadena llega a Gunicorn con exit 0 (el test no es vacuo).
Sin ZEUS_TEST_PG_URL o sin `sh` -> skip con el motivo.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import NullPool

from app.db.migration_status import code_heads

PG_URL = os.environ.get("ZEUS_TEST_PG_URL", "").strip()
BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
MARK = "ZEUS_TEST_FAKE_GUNICORN_STARTED"


def _start_command() -> str:
    m = re.search(r'^startCommand\s*=\s*(".*")\s*$', (REPO / "railway.toml").read_text(encoding="utf-8"), re.M)
    assert m, "railway.toml sin startCommand"
    return json.loads(m.group(1))  # string basica TOML: mismas secuencias \" que JSON


@pytest.fixture(scope="module")
def sh():
    exe = shutil.which("sh")
    if not exe:
        pytest.skip("no hay `sh` en el PATH")
    return exe


@pytest.fixture(scope="module")
def admin():
    if not PG_URL or not PG_URL.startswith("postgresql"):
        pytest.skip("ZEUS_TEST_PG_URL (PostgreSQL) no definida")
    eng = create_engine(PG_URL, poolclass=NullPool, isolation_level="AUTOCOMMIT",
                        connect_args={"connect_timeout": 3})
    try:
        with eng.connect() as c:
            c.execute(text("SELECT 1"))
    except OperationalError as e:
        pytest.skip(f"PostgreSQL de ZEUS_TEST_PG_URL no responde: {str(e.orig).splitlines()[0]}")
    yield eng
    eng.dispose()


@pytest.fixture
def temp_db(admin):
    created = []

    def make(revision: str) -> str:
        name = f"t_boot_{uuid.uuid4().hex[:10]}"
        with admin.connect() as c:
            c.execute(text(f'CREATE DATABASE "{name}"'))
        created.append(name)
        url = make_url(PG_URL).set(database=name)
        eng = create_engine(url, poolclass=NullPool)
        with eng.begin() as c:
            c.execute(text("CREATE TABLE alembic_version (version_num varchar(32) PRIMARY KEY)"))
            c.execute(text("INSERT INTO alembic_version VALUES (:r)"), {"r": revision})
        eng.dispose()
        return url.render_as_string(hide_password=False)

    yield make
    with admin.connect() as c:
        for name in created:
            c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))


def _run_start(sh, tmp_path, database_url):
    fake = tmp_path / "bin"
    fake.mkdir()
    g = fake / "gunicorn"
    g.write_text(f"#!/bin/sh\necho {MARK}\nexit 0\n", encoding="utf-8")
    g.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if k not in ("SKIP_DB_MIGRATE", "ZEUS_TEST_PG_URL")}
    env["DATABASE_URL"] = database_url
    env["PATH"] = os.pathsep.join([str(fake), os.path.dirname(sys.executable), env.get("PATH", "")])
    env["PYTHONIOENCODING"] = "utf-8"
    p = subprocess.run([sh, "-c", _start_command()], cwd=BACKEND, env=env, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=600)
    return p.returncode, p.stdout + p.stderr


def test_start_command_has_no_swallowed_migration_failure():
    cmd = _start_command()
    assert "alembic upgrade head" in cmd
    assert "||" not in cmd and "; true" not in cmd and "WARN" not in cmd
    assert "alembic upgrade head && python scripts/ensure_schema_patches.py; fi && exec gunicorn" in cmd


def test_unreachable_database_stops_startup(sh, tmp_path):
    rc, out = _run_start(sh, tmp_path, "postgresql://postgres@127.0.0.1:1/nada")
    print(f"[inalcanzable] rc={rc}")
    assert rc != 0 and MARK not in out


def test_failing_migration_stops_startup(sh, tmp_path, temp_db):
    url = temp_db("0069")  # BD "en 0069" pero sin las tablas que 0070 necesita -> 0070 falla
    rc, out = _run_start(sh, tmp_path, url)
    print(f"[migracion falla] rc={rc} ultima linea: {out.strip().splitlines()[-1][:160] if out.strip() else ''}")
    assert rc != 0 and MARK not in out
    assert "Running upgrade 0069 -> 0070" in out


def test_control_up_to_date_database_reaches_gunicorn(sh, tmp_path, temp_db):
    url = temp_db(code_heads()[0])
    rc, out = _run_start(sh, tmp_path, url)
    print(f"[control al dia] rc={rc}")
    assert rc == 0 and MARK in out, out[-2000:]
