"""/health informa del estado de las migraciones Alembic (app/main.py + app/db/migration_status.py).

- Mismo codigo HTTP de siempre (200): informa, no cambia el healthcheck de Railway.
- `migrations.head` sale de backend/alembic/versions (codigo desplegado; igual que ScriptDirectory.get_heads(),
  comprobado abajo); `migrations.current` de la tabla alembic_version de la BD; `up_to_date` = coinciden.
- Publico: solo numeros de revision. Si la BD falla, `migrations.error` lleva la clase de error, nunca el
  mensaje (host/usuario) ni una traza.
Contra PostgreSQL real (opcional, ZEUS_TEST_PG_URL a una BD migrada) se comprueba up_to_date=True.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from app.db.migration_status import code_heads, migration_status
from app.main import app

PG_URL = os.environ.get("ZEUS_TEST_PG_URL", "").strip()
REV = re.compile(r"^\d{4}")


def test_code_head_is_a_single_revision_from_alembic_versions():
    heads = code_heads()
    assert len(heads) == 1 and REV.match(heads[0]), heads


def test_code_heads_match_alembic_script_directory(tmp_path):
    """La head calculada sin importar alembic coincide con ScriptDirectory.get_heads() del alembic instalado
    (ejecutado fuera de backend/, donde la carpeta alembic/ local no tapa el paquete)."""
    backend = Path(__file__).resolve().parents[1]
    code = ("import json,sys; from alembic.config import Config; from alembic.script import ScriptDirectory; "
            "c=Config(sys.argv[1]); c.set_main_option('script_location', sys.argv[2]); "
            "print(json.dumps(sorted(ScriptDirectory.from_config(c).get_heads())))")
    out = subprocess.run([sys.executable, "-I", "-c", code, str(backend / "alembic.ini"), str(backend / "alembic")],
                         cwd=tmp_path, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-500:]
    assert json.loads(out.stdout.strip().splitlines()[-1]) == list(code_heads())


def test_health_reports_migrations_and_keeps_200():
    with TestClient(app) as c:
        r = c.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy" and body["service"] == "zeus-ia"
    m = body["migrations"]
    assert set(m) >= {"current", "head", "up_to_date"}
    assert m["head"] == code_heads()[0]
    # BD de tests creada con create_all, sin alembic_version: no hay revision aplicada -> no al dia
    assert m["current"] is None and m["up_to_date"] is False and "error" not in m


def test_unreachable_db_reports_error_class_only():
    eng = create_engine("postgresql://zeus_probe:secreto_no_debe_salir@127.0.0.1:1/nada",
                        poolclass=NullPool, connect_args={"connect_timeout": 2})
    m = migration_status(eng)
    assert m["up_to_date"] is False and m["current"] is None and m["head"] == code_heads()[0]
    assert m["error"] == "db: OperationalError"
    flat = repr(m)
    assert "secreto" not in flat and "zeus_probe" not in flat and "127.0.0.1" not in flat


def test_postgres_migrated_db_is_up_to_date():
    if not PG_URL:
        pytest.skip("ZEUS_TEST_PG_URL no definida (BD PostgreSQL migrada a head)")
    eng = create_engine(PG_URL, poolclass=NullPool, connect_args={"connect_timeout": 3})
    try:
        m = migration_status(eng)
    finally:
        eng.dispose()
    if m.get("error"):
        pytest.skip(f"PostgreSQL de ZEUS_TEST_PG_URL no disponible: {m['error']}")
    assert m["current"] == m["head"] == code_heads()[0] and m["up_to_date"] is True
