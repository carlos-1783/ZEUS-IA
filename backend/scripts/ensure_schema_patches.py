"""Aplica parches idempotentes de esquema (legacy BD sin migraciones Alembic reales)."""
from __future__ import annotations

import os
import sys


def _bootstrap_import_path() -> str:
    """Añade la raíz del backend (/app) a sys.path; el script vive en /app/scripts/."""
    env_root = (os.environ.get("ZEUS_APP_ROOT") or "").strip()
    if env_root and os.path.isfile(os.path.join(env_root, "alembic.ini")):
        backend_root = env_root
    else:
        backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)
    return backend_root


_bootstrap_import_path()

from app.db.base import ensure_schema_patches  # noqa: E402


def main() -> int:
    ensure_schema_patches()
    try:
        from services.fiscal_db_compat import fiscal_schema_gaps

        gaps = fiscal_schema_gaps()
        if gaps:
            print(f"[SCHEMA] Aviso: faltan {', '.join(gaps)}")
        else:
            print("[SCHEMA] Esquema fiscal OK")
    except Exception as exc:
        print(f"[SCHEMA] No se pudo verificar esquema fiscal: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
