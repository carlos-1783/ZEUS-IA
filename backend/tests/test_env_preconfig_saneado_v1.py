"""Saneado del entorno en los ficheros que leen variables ANTES de importar app.core.config.

gunicorn.conf.py y scripts/alembic_conditional_stamp.py (primer paso del startCommand de Railway) leian
os.environ crudo: un valor pegado en el panel con comillas o espacios (`"2"`, `  "postgresql://..."  `)
llegaba tal cual. Ahora ambos llaman a app.core.env_sanitize.sanitize_environ() antes de leer nada (mismo
modulo y regla que la app). El log de saneado da solo NOMBRES, nunca valores. Cada caso en un subproceso
propio (entorno aislado del de los tests).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
SECRET = "s3cr3t-valor-que-no-debe-salir"


def _env(**extra):
    env = {k: v for k, v in os.environ.items() if k not in ("DATABASE_URL", "DATABASE_MIGRATION_URL")}
    env.update(extra)
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def test_gunicorn_config_receives_clean_values():
    code = (
        "import json, runpy; cfg = runpy.run_path('gunicorn.conf.py'); "
        "print(json.dumps({'bind': cfg['bind'], 'workers': cfg['workers'], 'timeout': cfg['timeout']}))"
    )
    r = subprocess.run(
        [sys.executable, "-c", code], cwd=BACKEND, capture_output=True, text=True, timeout=120,
        env=_env(PORT=" '8123' ", WEB_CONCURRENCY='  "2"\n', GUNICORN_TIMEOUT=' "77" ',
                 ZEUS_TEST_SECRET_PRECONFIG=f' "{SECRET}" '),
    )
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out == {"bind": "0.0.0.0:8123", "workers": 2, "timeout": 77}
    assert "WEB_CONCURRENCY" in r.stderr and "ZEUS_TEST_SECRET_PRECONFIG" in r.stderr  # nombres, si
    assert SECRET not in r.stderr and SECRET not in r.stdout                            # valores, nunca


def test_stamp_script_reads_clean_database_url():
    # Se ejecuta el main() REAL del script; solo se intercepta create_engine para ver la URL que le llega
    # (sin conectar a ninguna BD).
    code = "\n".join([
        "import json, runpy, sqlalchemy",
        "seen = []",
        "class Stop(Exception): pass",
        "def fake(url, *a, **k):",
        "    seen.append(url); raise Stop()",
        "sqlalchemy.create_engine = fake",
        "mod = runpy.run_path('scripts/alembic_conditional_stamp.py', run_name='stamp_test')",
        "try:",
        "    mod['main']()",
        "except Stop:",
        "    pass",
        "print(json.dumps(seen))",
    ])
    r = subprocess.run(
        [sys.executable, "-c", code], cwd=BACKEND, capture_output=True, text=True, timeout=120,
        env=_env(DATABASE_URL=f'  "postgresql://u:{SECRET}@db.invalid:5432/x"  '),
    )
    assert r.returncode == 0, r.stderr
    seen = json.loads(r.stdout.strip().splitlines()[-1])
    assert seen == [f"postgresql://u:{SECRET}@db.invalid:5432/x"]
    assert "DATABASE_URL" in r.stderr and SECRET not in r.stderr
