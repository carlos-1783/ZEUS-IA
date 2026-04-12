#!/usr/bin/env python3
"""
Verificación en 3 frentes (sin arrancar DB real si falla import):
1) Artefactos: Dockerfile, página PWA embebida, dist opcional.
2) Importación del app FastAPI.
3) TestClient: /clear-pwa-cache.html, /api/v1/health, SPA fallback HTML si no hay index.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# backend/ como cwd
ROOT = Path(__file__).resolve().parents[2]
BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault("ZEUS_SKIP_STARTUP_DB_INIT", "1")


def check_artifacts() -> list[str]:
    errs: list[str] = []
    df = ROOT / "Dockerfile"
    if not df.is_file():
        errs.append("Falta Dockerfile en la raíz del repo (build monolítico recomendado).")
    pwa = BACKEND / "app" / "static_pages" / "clear_pwa_cache.html"
    if not pwa.is_file():
        errs.append(f"Falta página embebida: {pwa}")
    return errs


def check_import() -> list[str]:
    errs: list[str] = []
    try:
        from app.main import app  # noqa: F401
    except Exception as e:
        errs.append(f"Import app.main falló: {e}")
    return errs


def check_http() -> list[str]:
    errs: list[str] = []
    try:
        from fastapi.testclient import TestClient
        from app.main import app
    except Exception as e:
        errs.append(f"No se pudo crear TestClient: {e}")
        return errs

    c = TestClient(app)
    r = c.get("/clear-pwa-cache.html")
    if r.status_code != 200 or "Limpiar Cache PWA" not in (r.text or ""):
        errs.append(f"/clear-pwa-cache.html inesperado: {r.status_code}")

    r2 = c.get("/api/v1/health")
    if r2.status_code not in (200, 503):
        errs.append(f"/api/v1/health status {r2.status_code}")

    r3 = c.get("/", headers={"Accept": "text/html,application/xhtml+xml"})
    if r3.status_code != 200:
        errs.append(f"GET / con Accept HTML → {r3.status_code}")
    elif "text/html" not in (r3.headers.get("content-type") or ""):
        errs.append("GET / no devolvió text/html (revisar STATIC_DIR / dist)")

    return errs


def main() -> int:
    all_errs: list[str] = []
    all_errs.extend(check_artifacts())
    all_errs.extend(check_import())
    all_errs.extend(check_http())
    if all_errs:
        print("ERRORES:")
        for e in all_errs:
            print(" -", e)
        return 1
    print("OK: artefactos, import y rutas críticas (clear-pwa, health, / HTML).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
