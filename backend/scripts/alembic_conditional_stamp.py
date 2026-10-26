"""
Railway / legacy Postgres: tablas ya creadas sin Alembic (alembic_version vacío o ausente).
Sin esto, `alembic upgrade head` intenta reaplicar 0001 y falla con "relation users already exists".

Solo hace `alembic stamp` cuando hay tabla `users` y no hay revisión registrada.
Bases nuevas (sin `users`): no toca nada; las migraciones crean el esquema con normalidad.

Revisión del stamp: `0069` (LEGACY_STAMP_REVISION), NO `head`. Una BD legacy la construyó `create_all` desde
los modelos: tiene las tablas, pero no los objetos que solo crean las migraciones (funciones SQL, policies,
GRANT). Con `stamp head` la 0070 se daría por aplicada sin ejecutarse y faltaría la función
`invoice_next_number` (toda alta de factura fallaría). Sellando 0069, el `alembic upgrade head` que viene
justo después en el arranque ejecuta 0070 en adelante, y esas migraciones son idempotentes (crean solo lo
que falta). Regla para migraciones nuevas (0071+): deben ser idempotentes, porque también correrán sobre
BD legacy construidas por create_all.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

# Última revisión cuyas migraciones NO son idempotentes (0001..0069 crean tablas que create_all ya creó).
LEGACY_STAMP_REVISION = "0069"

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


def _run_stamp_legacy() -> int:
    exe = shutil.which("alembic")
    if not exe:
        print("alembic_conditional_stamp: no hay ejecutable 'alembic' en PATH")
        return 1
    cwd = _alembic_cwd()
    print(f"alembic_conditional_stamp: stamp {LEGACY_STAMP_REVISION} (el upgrade head posterior aplica el resto)")
    return subprocess.call([exe, "stamp", LEGACY_STAMP_REVISION], cwd=cwd)


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
    # Saneado CENTRAL del entorno antes de leer DATABASE_*: este script corre ANTES de importar la app
    # (primer paso del startCommand). Mismo modulo que app/core/config.py; el log solo da NOMBRES.
    _bootstrap_import_path()
    from app.core.env_sanitize import sanitize_environ

    sanitize_environ()
    # Misma URL que alembic/env.py: la privilegiada si existe (stamp y parches son DDL), si no DATABASE_URL.
    url = (
        (os.environ.get("DATABASE_MIGRATION_URL") or "").strip()
        or os.environ.get("DATABASE_URL")
        or os.environ.get("SQLALCHEMY_DATABASE_URI")
    )
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
                "alembic_conditional_stamp: legacy — users existe, sin alembic_version -> parches + stamp legacy"
            )
            _apply_runtime_schema_patches()
            return _run_stamp_legacy()

        n = conn.execute(text("SELECT COUNT(*) FROM alembic_version")).scalar()
        if n == 0:
            print(
                "alembic_conditional_stamp: legacy — alembic_version vacío -> parches + stamp legacy"
            )
            _apply_runtime_schema_patches()
            return _run_stamp_legacy()

    _apply_runtime_schema_patches()
    print("alembic_conditional_stamp: alembic_version ya definida; sin stamp")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
