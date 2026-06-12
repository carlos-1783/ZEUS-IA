"""Aplica parches idempotentes de esquema (legacy BD sin migraciones Alembic reales)."""
from __future__ import annotations

from app.db.base import ensure_schema_patches


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
