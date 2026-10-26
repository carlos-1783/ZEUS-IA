"""Una sola config de Railway: railway.toml (la que Railway usa y la unica que aplica migraciones).

railway.json (Nixpacks + uvicorn, sin migraciones) y railway-simple.toml (gunicorn sin migraciones) se
borraron: si reaparece otra config de Railway en la raiz, Railway podria arrancar sin `alembic upgrade`.
Ademas, el arranque de railway.toml y el CMD del Dockerfile deben ser la MISMA cadena (fail-closed).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# Nombres que Railway lee como config de despliegue (sensible a mayusculas, como en Linux).
_RAILWAY_CFG_RE = re.compile(r"^railway[^/]*\.(toml|json)$")


def _toml_value(key: str) -> str:
    m = re.search(rf'^{key}\s*=\s*(".*")\s*$', (REPO / "railway.toml").read_text(encoding="utf-8"), re.M)
    assert m, f"railway.toml sin {key}"
    return json.loads(m.group(1))


def test_only_railway_toml_at_repo_root():
    found = sorted(n for n in os.listdir(REPO) if _RAILWAY_CFG_RE.match(n))
    assert found == ["railway.toml"], f"config de Railway duplicada en la raiz: {found}"


def test_railway_toml_has_health_and_dockerfile_builder():
    text = (REPO / "railway.toml").read_text(encoding="utf-8")
    assert re.search(r'^builder\s*=\s*"DOCKERFILE"\s*$', text, re.M)
    assert _toml_value("healthcheckPath") == "/health"


def test_start_command_matches_dockerfile_cmd():
    start = _toml_value("startCommand")
    m = re.match(r"^sh -c '(.*)'$", start, re.S)
    assert m, start
    cmd_line = [ln for ln in (REPO / "Dockerfile").read_text(encoding="utf-8").splitlines()
                if ln.startswith("CMD ")]
    assert len(cmd_line) == 1, cmd_line
    cmd = json.loads(cmd_line[0][4:])
    assert cmd[:2] == ["sh", "-c"] and len(cmd) == 3
    assert cmd[2] == m.group(1)
    assert "alembic upgrade head" in cmd[2] and "exec gunicorn" in cmd[2]
