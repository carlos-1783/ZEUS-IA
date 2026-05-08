"""
Railway / legacy Postgres: tablas ya creadas sin Alembic (alembic_version vacío o ausente).
Sin esto, `alembic upgrade head` intenta reaplicar 0001 y falla con "relation users already exists".

Solo hace `alembic stamp head` cuando hay tabla `users` y no hay revisión registrada.
Bases nuevas (sin `users`): no toca nada; las migraciones crean el esquema con normalidad.
"""
from __future__ import annotations

import os
import subprocess
import sys


def _run_stamp_head() -> int:
    return subprocess.call([sys.executable, "-m", "alembic", "stamp", "head"])


def main() -> int:
    url = os.environ.get("DATABASE_URL") or os.environ.get("SQLALCHEMY_DATABASE_URI")
    if not url:
        print("alembic_conditional_stamp: sin DATABASE_URL, omitiendo")
        return 0

    try:
        from sqlalchemy import create_engine, text
    except ImportError:
        print("alembic_conditional_stamp: sqlalchemy no disponible, omitiendo")
        return 0

    engine = create_engine(url)
    with engine.connect() as conn:
        has_users = conn.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'users')"
            )
        ).scalar()

        if not has_users:
            print("alembic_conditional_stamp: sin tabla users (BD nueva); sin stamp")
            return 0

        has_av = conn.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'alembic_version')"
            )
        ).scalar()

        if not has_av:
            print(
                "alembic_conditional_stamp: legacy — users existe, sin alembic_version -> stamp head"
            )
            return _run_stamp_head()

        n = conn.execute(text("SELECT COUNT(*) FROM alembic_version")).scalar()
        if n == 0:
            print(
                "alembic_conditional_stamp: legacy — alembic_version vacío -> stamp head"
            )
            return _run_stamp_head()

    print("alembic_conditional_stamp: alembic_version ya definida; sin stamp")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
