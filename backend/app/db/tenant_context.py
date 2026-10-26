"""
Aislamiento multi-tenant a nivel de base de datos (Row Level Security).

Hallazgo de la auditoría feature/auditoria-real-nucleo: el aislamiento entre
empresas dependía por completo de que cada endpoint recordara filtrar por
company_id en su query — un solo endpoint que se olvide (o un bug futuro) es
una fuga de datos entre clientes. Este módulo añade una segunda capa de
protección real a nivel de PostgreSQL (RLS) que no depende de que el código
de la aplicación acierte siempre.

Diseño deliberadamente conservador ("fail-open cuando no hay contexto"):
las policies de RLS solo restringen filas cuando la variable de sesión
`app.current_company_id` está establecida para la transacción actual. Si
ningún código la establece (scripts internos, tests, endpoints todavía sin
migrar a `get_db_scoped`, migraciones de Alembic, workers de fondo), las
queries siguen viendo exactamente lo mismo que antes de activar RLS — no se
puede romper nada que no esté ya usando `get_db_scoped`. Sí es responsabili-
dad de cada endpoint sensible usar `get_db_scoped` en vez de `get_db` para
obtener la protección real; ver AUDIT_FIX_BLOQUE2.md para qué endpoints ya
se migraron en este bloque y cuáles quedan pendientes.

No aplica nada en SQLite (RLS no existe ahí) — local/tests siguen exactamente
igual que hoy, sin ningún cambio de comportamiento.

Extensión (AUDIT_THALOS_ESTRUCTURAL.md, paso 2, consolidada aquí en el
mismo módulo en vez de duplicarlo): las 4 tablas de logs de seguridad de
THALOS (`thalos_events`, `thalos_alerts`, `thalos_security_events`,
`thalos_login_attempts`) reutilizan exactamente este mismo mecanismo de
`get_db_scoped`/`set_tenant_context` — ver
`alembic/versions/0047_thalos_row_level_security.py` para sus policies
específicas. Es responsabilidad de cada endpoint que lea esas 4 tablas usar
`get_db_scoped`, ADEMÁS del gate de superusuario ya aplicado a nivel de
aplicación en las 6 vueltas de `AUDIT_FIX_THALOS_SHIELD.md` (RLS es defensa
en profundidad, no sustituye esos gates).

IMPORTANTE (ver también el docstring de la migración 0047): este mecanismo
NO se ha podido verificar contra un PostgreSQL real en esta sesión de
consolidación (solo SQLite disponible aquí). El hallazgo crítico de
`dec54c0` (rama `multi-tenant-bd`) fue que RLS queda completamente inerte
si la conexión de la aplicación usa un rol superusuario de Postgres
(Postgres exime siempre a los superusuarios de RLS, con independencia de
`FORCE ROW LEVEL SECURITY`) -- antes de confiar en este mecanismo en
producción, verificar explícitamente que la `DATABASE_URL` de runtime de
la aplicación usa un rol sin `SUPERUSER` ni `BYPASSRLS` (ver recomendación
de `zeus_app` en `dec54c0`).
"""
from __future__ import annotations

from typing import Optional

import logging

from fastapi import Depends
from sqlalchemy import event, text
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User

logger = logging.getLogger(__name__)

# Clave en `Session.info` donde se guarda el contexto RLS de la sesión. Vive lo
# mismo que el objeto Session (una petición), nunca en la conexión del pool.
_RLS_INFO_KEY = "rls_tenant_context"

_SET_CONTEXT_SQL = text(
    "SELECT set_config('app.current_company_id', :company_id, true), "
    "set_config('app.current_user_id', :user_id, true), "
    "set_config('app.current_user_email', :user_email, true)"
)


def _context_params(ctx: dict) -> dict:
    return {
        "company_id": str(ctx["company_id"]) if ctx.get("company_id") is not None else "",
        "user_id": str(ctx["user_id"]) if ctx.get("user_id") is not None else "",
        "user_email": ctx.get("user_email") or "",
    }


@event.listens_for(Session, "after_begin")
def _reapply_tenant_context(session: Session, transaction, connection) -> None:
    """Re-fija el contexto RLS al empezar CADA transacción de una sesión que ya
    lo tenía (set_tenant_context). Antes el contexto era `set_config(..., true)`
    (local a la transacción) y desaparecía en el primer commit/rollback de la
    petición: todo lo que la petición consultaba después (refresh, lecturas
    posteriores) iba SIN empresa y, con las policies fail-open de 0047, veía
    datos de todas las empresas.

    Se sigue usando alcance LOCAL a la transacción (no set_config de sesión):
    el valor muere solo en commit/rollback, así que una conexión devuelta al
    pool nunca arrastra el contexto de otra petición, sin depender de un
    reset en checkin. Sesiones sin contexto (workers, scripts, SQLite) -> no-op."""
    ctx = session.info.get(_RLS_INFO_KEY)
    if ctx is None or connection.dialect.name != "postgresql":
        return
    connection.execute(_SET_CONTEXT_SQL, _context_params(ctx))


def set_tenant_context(
    db: Session,
    company_id: Optional[int],
    user_id: Optional[int] = None,
    user_email: Optional[str] = None,
) -> None:
    """Fija el contexto de empresa/usuario que leen las RLS policies para TODA
    la vida de la sesión `db`: se aplica ya a la transacción actual y el evento
    `after_begin` lo vuelve a aplicar en cada transacción nueva (tras commit o
    rollback). Alcance de cada set_config: la transacción (is_local=true).
    No-op fuera de Postgres."""
    if db.bind is None or db.bind.dialect.name != "postgresql":
        return
    ctx = {"company_id": company_id, "user_id": user_id, "user_email": user_email}
    db.info[_RLS_INFO_KEY] = ctx
    db.execute(_SET_CONTEXT_SQL, _context_params(ctx))
    logger.debug("rls_context set company_id=%s user_id=%s", company_id, user_id)


def get_db_scoped(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Session:
    """Dependency drop-in para reemplazar `Depends(get_db)` en endpoints que
    manejan datos por tenant, incluidas las 4 tablas de logs de seguridad de
    THALOS. Además de dar la sesión, fija el contexto de empresa/usuario para
    que las RLS policies (ver alembic/versions/0047_row_level_security.py y
    0047_thalos_row_level_security.py) filtren de verdad en Postgres."""
    import services.crm_office_service as crm_svc

    if getattr(current_user, "is_superuser", False):
        # Bypass explícito para superusuarios, a nivel de aplicación (NO en
        # el rol de conexión de Postgres — zeus_app sigue sin ser
        # superusuario ni tener BYPASSRLS). No se fija ningún company_id de
        # tenant, así que las policies de RLS (fail-open cuando no hay
        # contexto) dejan ver todo. Deliberadamente independiente de si el
        # superusuario tiene o no una fila en user_companies: antes de este
        # fix, un admin sin empresa asignada "veía todo" solo por
        # coincidencia (primary_company_id devolvía None); si en el futuro
        # se le asignara una empresa, habría quedado restringido a esa única
        # empresa como cualquier usuario normal. Con el check explícito, el
        # acceso total del superusuario no depende de ese detalle — y es
        # coherente con que los 17+ gates de superusuario de
        # AUDIT_FIX_THALOS_SHIELD.md ya asumen que un superusuario ve el
        # subsistema de seguridad completo.
        set_tenant_context(db, None, user_id=current_user.id, user_email=current_user.email)
        return db

    company_id = crm_svc.primary_company_id(db, current_user)
    set_tenant_context(db, company_id, user_id=current_user.id, user_email=current_user.email)
    return db
