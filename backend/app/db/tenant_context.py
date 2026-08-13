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
"""
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
    """Establece las variables de sesión Postgres que leen las RLS policies,
    con alcance a la transacción actual (set_config con is_local=true — se
    resetea sola al hacer commit/rollback, no hace falta limpiarla a mano).
    No-op fuera de Postgres."""
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
    manejan datos por tenant. Además de dar la sesión, fija el contexto de
    empresa/usuario para que las RLS policies (ver alembic/versions/
    0047_row_level_security.py) filtren de verdad en Postgres."""
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
        # acceso total del superusuario no depende de ese detalle.
        set_tenant_context(db, None, user_id=current_user.id, user_email=current_user.email)
        return db

    company_id = crm_svc.primary_company_id(db, current_user)
    set_tenant_context(db, company_id, user_id=current_user.id, user_email=current_user.email)
    return db
