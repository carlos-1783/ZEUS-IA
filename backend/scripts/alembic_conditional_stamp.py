"""
Railway / legacy Postgres: tablas ya creadas sin Alembic (alembic_version vacío o ausente).
Sin esto, `alembic upgrade head` intenta reaplicar 0001 y falla con "relation users already exists".

Solo hace `alembic stamp head` cuando hay tabla `users` y no hay revisión registrada.
Bases nuevas (sin `users`): no toca nada; las migraciones crean el esquema con normalidad.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

# No usar `python -m alembic`: en /app la carpeta local `alembic/` (migraciones) oculta el paquete
# instalado y Python no encuentra __main__.py.


def _alembic_cwd() -> str:
    """Directorio con alembic.ini (WORKDIR del contenedor = backend)."""
    env_root = (os.environ.get("ZEUS_APP_ROOT") or "").strip()
    if env_root and os.path.isfile(os.path.join(env_root, "alembic.ini")):
        return env_root
    cwd = os.getcwd()
    if os.path.isfile(os.path.join(cwd, "alembic.ini")):
        return cwd
    # Si el script se lanza desde otro cwd
    here = os.path.dirname(os.path.abspath(__file__))
    backend_root = os.path.dirname(here)
    if os.path.isfile(os.path.join(backend_root, "alembic.ini")):
        return backend_root
    return cwd


def _run_stamp_head() -> int:
    exe = shutil.which("alembic")
    if not exe:
        print("alembic_conditional_stamp: no hay ejecutable 'alembic' en PATH")
        return 1
    cwd = _alembic_cwd()
    return subprocess.call([exe, "stamp", "head"], cwd=cwd)


def _bootstrap_import_path() -> str:
    env_root = (os.environ.get("ZEUS_APP_ROOT") or "").strip()
    if env_root and os.path.isfile(os.path.join(env_root, "alembic.ini")):
        backend_root = env_root
    else:
        backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)
    return backend_root


def _apply_runtime_schema_patches() -> None:
    try:
        _bootstrap_import_path()
        from app.db.base import ensure_schema_patches

        ensure_schema_patches()
        from services.fiscal_db_compat import fiscal_schema_gaps

        gaps = fiscal_schema_gaps()
        if gaps:
            print(f"alembic_conditional_stamp: aviso esquema fiscal: {', '.join(gaps)}")
    except Exception as exc:
        print(f"alembic_conditional_stamp: ensure_schema_patches falló: {exc}")


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
                "alembic_conditional_stamp: legacy — users existe, sin alembic_version -> parches + stamp head"
            )
            _apply_runtime_schema_patches()
            return _run_stamp_head()

        n = conn.execute(text("SELECT COUNT(*) FROM alembic_version")).scalar()
        if n == 0:
            print(
                "alembic_conditional_stamp: legacy — alembic_version vacío -> parches + stamp head"
            )
            _apply_runtime_schema_patches()
            return _run_stamp_head()

    _apply_runtime_schema_patches()
    print("alembic_conditional_stamp: alembic_version ya definida; sin stamp")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
