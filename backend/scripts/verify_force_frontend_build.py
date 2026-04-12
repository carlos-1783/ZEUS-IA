#!/usr/bin/env python3
"""
FORCE_FRONTEND_BUILD_PRODUCTION — comprobaciones locales (sin Railway):
- frontend/package.json: script build → Vite (salida dist/)
- backend/static/index.html opcional (commit o post-build)
- TestClient: GET / devuelve HTML; con ZEUS_FRONTEND_STATUS=1, /_zeus/frontend-status
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FRONTEND = REPO / "frontend"
BACKEND = REPO / "backend"


def main() -> int:
    errs: list[str] = []

    pkg = FRONTEND / "package.json"
    if not pkg.is_file():
        errs.append("No existe frontend/package.json")
    else:
        raw = pkg.read_text(encoding="utf-8", errors="replace")
        if '"vite build"' not in raw and "'vite build'" not in raw:
            errs.append("package.json: no se encontró script build con vite build")
        if "dist" not in raw.lower() and "vite" in raw:
            pass  # Vite default outDir dist

    dist = FRONTEND / "dist"
    idx_dist = dist / "index.html"
    if not idx_dist.is_file():
        errs.append(
            "No hay frontend/dist/index.html (ejecuta: cd frontend && npm ci && npm run build). "
            "En Docker el stage frontend-builder lo genera."
        )

    static_idx = BACKEND / "static" / "index.html"
    if not static_idx.is_file():
        print("AVISO: backend/static/index.html ausente en working tree (normal si solo construyes en Docker).")

    sys.path.insert(0, str(BACKEND))
    os.environ.setdefault("ZEUS_SKIP_STARTUP_DB_INIT", "1")
    os.environ["ZEUS_FRONTEND_STATUS"] = "1"
    try:
        from fastapi.testclient import TestClient
        from app.main import app

        c = TestClient(app)
        r = c.get("/")
        ct = r.headers.get("content-type", "")
        if r.status_code != 200:
            errs.append(f"GET / → {r.status_code}")
        elif "text/html" not in ct:
            errs.append(f"GET / content-type inesperado: {ct}")

        s = c.get("/_zeus/frontend-status")
        if s.status_code != 200:
            errs.append(f"/_zeus/frontend-status → {s.status_code}")
        elif not s.json().get("framework"):
            errs.append("frontend-status sin campo framework")
    except Exception as e:
        errs.append(f"TestClient: {e}")

    if errs:
        print("FALLOS:")
        for e in errs:
            print(" -", e)
        return 1
    print("OK: Vite/dist, GET / HTML, /_zeus/frontend-status con ZEUS_FRONTEND_STATUS=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
