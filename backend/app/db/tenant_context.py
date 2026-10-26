"""
Aislamiento multi-tenant a nivel de base de datos (Row Level Security) -- fachada de compatibilidad.

Desde la migracion 0071 las policies son FAIL-CLOSED (sin contexto no se ve ninguna fila de empresa) y
cubren las tablas con datos de empresa (ver alembic/versions/0071_rls_fail_closed_zeus_app.py). El
contexto lo fija `app.core.auth.get_current_user` en la sesion compartida de cada peticion autenticada y
las rutas sin usuario lo fijan de forma explicita (app/db/rls_context.py, donde viven las primitivas y el
evento after_begin que lo re-aplica en cada transaccion). Este modulo re-exporta esas primitivas para los
imports existentes y mantiene `get_db_scoped`.

La RLS solo actua si la app conecta con un rol sin SUPERUSER ni BYPASSRLS (zeus_app): Postgres exime
siempre a los superusuarios. Con la app conectada como postgres todo se comporta exactamente como antes.
No aplica nada en SQLite.
"""
from __future__ import annotations

import logging

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User

# Las primitivas viven en app.db.rls_context (sin dependencias de auth, para que app.core.auth pueda
# usarlas sin import circular). Se re-exportan aqui por compatibilidad con los imports existentes.
from app.db.rls_context import (  # noqa: F401
    RLS_INFO_KEY as _RLS_INFO_KEY,
    _SET_CONTEXT_SQL,
    _context_params,
    _reapply_rls_context as _reapply_tenant_context,
    bind_user_context,
    set_system_context,
    set_tenant_context,
    system_db,
    tenant_db,
)

logger = logging.getLogger(__name__)


def get_db_scoped(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Session:
    """Dependency compatible con los endpoints que ya la usaban. Desde 0071 el contexto RLS lo fija
    `app.core.auth.get_current_user` en la sesion compartida de TODA peticion autenticada (usuario + sus
    empresas; superusuario -> modo system auditado), asi que aqui solo se re-afirma por si la sesion
    llego por otra via. Idempotente."""
    bind_user_context(db, current_user)
    return db
