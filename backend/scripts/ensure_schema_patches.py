"""Aplica parches idempotentes de esquema (legacy BD sin migraciones Alembic reales)."""
from __future__ import annotations

from app.db.base import ensure_schema_patches


def main() -> int:
    ensure_schema_patches()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
