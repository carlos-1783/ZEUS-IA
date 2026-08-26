"""
Aislamiento multi-tenant a nivel de base de datos (Row Level Security).

AUDIT_THALOS_ESTRUCTURAL.md, paso 2. Mismo patrón, mismo diseño, ya
validado contra un PostgreSQL real de Railway en `feature/multi-tenant-bd`
(`app/db/tenant_context.py`, commit `6173852`, corregido en `dec54c0` tras
encontrar que RLS quedaba inerte si la app conectaba como superusuario de
Postgres). Esa rama no está fusionada aquí -- este módulo es una
adaptación propia para el subsistema de logs de seguridad de THALOS
(`thalos_events`, `thalos_alerts`, `thalos_security_events`,
`thalos_login_attempts`), reutilizando exactamente el mismo mecanismo.

Diseño deliberadamente conservador ("fail-open cuando no hay contexto"):
las policies de RLS (ver `alembic/versions/0047_thalos_row_level_security.py`)
solo restringen filas cuando la variable de sesión
`app.current_company_id` está fijada para la transacción actual. Si ningún
código la establece (scripts internos, tests, endpoints todavía sin migrar
a `get_db_scoped`, workers de fondo, Alembic mismo), las queries siguen
viendo exactamente lo mismo que antes de activar RLS -- no se puede romper
nada que no esté ya usando `get_db_scoped`. Es responsabilidad de cada
endpoint que lea las 4 tablas de THALOS usar `get_db_scoped` en vez de
`get_db` para obtener la protección real de base de datos, ADEMÁS del gate
de superusuario ya aplicado a nivel de aplicación en las 6 vueltas de
`AUDIT_FIX_THALOS_SHIELD.md` (RLS es defensa en profundidad, no sustituye
esos gates).

No aplica nada en SQLite (RLS no existe ahí) -- local/tests siguen
exactamente igual que antes de este módulo, sin ningún cambio de
comportamiento.

IMPORTANTE (ver también el docstring de la migración 0047): este mecanismo
NO se ha podido verificar contra un PostgreSQL real en esta sesión de
desarrollo (solo SQLite disponible, sin Postgres/Docker de prueba con
credenciales conocidas). El hallazgo crítico de `dec54c0` en la rama
hermana fue que RLS queda completamente inerte si la conexión de la
aplicación usa un rol superusuario de Postgres (Postgres exime siempre a
los superusuarios de RLS, con independencia de `FORCE ROW LEVEL SECURITY`)
-- antes de confiar en este mecanismo en producción, verificar
explícitamente que la `DATABASE_URL` de runtime de la aplicación usa un rol
sin `SUPERUSER` ni `BYPASSRLS` (ver recomendación de `zeus_app` en
`dec54c0`).
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User


def set_tenant_context(
    db: Session,
    company_id: Optional[int],
    user_id: Optional[int] = None,
    user_email: Optional[str] = None,
) -> None:
    """Establece las variables de sesión Postgres que leen las policies de
    RLS, con alcance a la transacción actual (`set_config(..., is_local=true)`
    -- se resetea sola al hacer commit/rollback, no hace falta limpiarla a
    mano). No-op fuera de Postgres."""
    if db.bind is None or db.bind.dialect.name != "postgresql":
        return
    db.execute(
        text("SELECT set_config('app.current_company_id', :value, true)"),
        {"value": str(company_id) if company_id is not None else ""},
    )
    db.execute(
        text("SELECT set_config('app.current_user_id', :value, true)"),
        {"value": str(user_id) if user_id is not None else ""},
    )
    db.execute(
        text("SELECT set_config('app.current_user_email', :value, true)"),
        {"value": user_email or ""},
    )


def get_db_scoped(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Session:
    """Dependency drop-in para reemplazar `Depends(get_db)` en endpoints que
    leen las 4 tablas de logs de seguridad de THALOS. Además de dar la
    sesión, fija el contexto de empresa/usuario para que las policies de RLS
    (ver `alembic/versions/0047_thalos_row_level_security.py`) filtren de
    verdad en Postgres."""
    from services.workspace_deliverables import primary_company_id_for_user

    if getattr(current_user, "is_superuser", False):
        # Bypass explícito a nivel de APLICACIÓN para superusuarios -- NO en
        # el rol de conexión de Postgres (que debe seguir sin SUPERUSER ni
        # BYPASSRLS, ver docstring del módulo). No se fija ningún
        # company_id de tenant, así que las policies (fail-open cuando no
        # hay contexto) dejan ver todo -- coherente con que los 17+ gates de
        # superusuario de AUDIT_FIX_THALOS_SHIELD.md ya asumen que un
        # superusuario ve el subsistema de seguridad completo.
        set_tenant_context(db, None, user_id=current_user.id, user_email=current_user.email)
        return db

    company_id = primary_company_id_for_user(db, current_user)
    set_tenant_context(db, company_id, user_id=current_user.id, user_email=current_user.email)
    return db
