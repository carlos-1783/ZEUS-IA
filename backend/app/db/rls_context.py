"""Contexto RLS de una sesion SQLAlchemy: QUIEN consulta (usuario, empresas) o modo `system` explicito.

Las policies de PostgreSQL (migracion 0071) son fail-closed: sin contexto no se ve ni se escribe ninguna
fila de las tablas con datos de empresa. Este modulo es el UNICO sitio que fija ese contexto:

- `bind_user_context(db, user)`: peticion autenticada. Empresas = las del usuario en user_companies
  (resueltas en servidor, nunca de un parametro del cliente). Superusuario -> modo system auditado.
- `set_tenant_context(db, company_id, ...)`: proceso que SABE su empresa (worker que recorre empresas,
  pagina publica de un negocio, token firmado ligado a una empresa, registro de una empresa nueva).
- `set_system_context(db, reason)` / `system_db(reason)` / `open_system_session(reason)`: vision global,
  SOLO donde hace falta de verdad (arranque, superadmin, jobs entre empresas). Registra el motivo.
- Funciones SQL acotadas (SECURITY DEFINER, 0071) para lo que se hace antes de saber quien es el usuario:
  `lookup_user_id_by_email` (login, reset), `company_slug_taken`, `public_site_user_id_by_slug`.

Alcance de cada valor: la TRANSACCION (`set_config(..., true)`). El contexto vive en `Session.info` y el
evento `after_begin` lo vuelve a aplicar al empezar cada transaccion de esa sesion (tras commit/rollback),
asi que no se pierde a mitad de peticion y una conexion devuelta al pool nunca arrastra el de otra.

Variables (las leen las policies): app.current_user_id, app.current_user_email, app.current_company_id
(empresa primaria; la usan las policies de seguros de 0049/0055), app.current_company_ids (todas las del
usuario, "1,7"), app.rls_mode ('' o 'system').

Limite honesto: cualquier codigo que ejecute SQL con esta conexion puede llamar a set_config y ponerse en
modo system. La RLS protege contra el filtro olvidado o el bug de un endpoint, no contra codigo de la app
comprometido o una inyeccion SQL. Endurecerlo exige separar roles de BD (ver informe).

Fuera de PostgreSQL (SQLite de tests/local) todo es no-op salvo los lookups, que caen a una query normal.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator, List, Optional, Sequence

from sqlalchemy import event, text
from sqlalchemy.orm import Session

logger = logging.getLogger("zeus.rls")

# Clave en `Session.info`: vive lo mismo que el objeto Session, nunca en la conexion del pool.
RLS_INFO_KEY = "rls_tenant_context"
MODE_TENANT = ""
MODE_SYSTEM = "system"

_SET_CONTEXT_SQL = text(
    "SELECT set_config('app.current_company_id', :company_id, true), "
    "set_config('app.current_company_ids', :company_ids, true), "
    "set_config('app.current_user_id', :user_id, true), "
    "set_config('app.current_user_email', :user_email, true), "
    "set_config('app.rls_mode', :mode, true)"
)


def _context_params(ctx: dict) -> dict:
    ids = [int(c) for c in (ctx.get("company_ids") or []) if c is not None]
    return {
        "company_id": str(ctx["company_id"]) if ctx.get("company_id") is not None else "",
        "company_ids": ",".join(str(c) for c in ids),
        "user_id": str(ctx["user_id"]) if ctx.get("user_id") is not None else "",
        "user_email": ctx.get("user_email") or "",
        "mode": ctx.get("mode") or MODE_TENANT,
    }


@event.listens_for(Session, "after_begin")
def _reapply_rls_context(session: Session, transaction, connection) -> None:
    """Re-fija el contexto al empezar CADA transaccion de una sesion que ya lo tenia. Sesiones sin
    contexto (o SQLite) -> no-op: en Postgres no ven filas de empresa (fail-closed)."""
    ctx = session.info.get(RLS_INFO_KEY)
    if ctx is None or connection.dialect.name != "postgresql":
        return
    connection.execute(_SET_CONTEXT_SQL, _context_params(ctx))


def is_postgres(db: Session) -> bool:
    try:
        bind = db.get_bind()
    except Exception:
        return False
    return bind is not None and bind.dialect.name == "postgresql"


def _apply(db: Session, ctx: dict) -> None:
    if not is_postgres(db):
        return
    db.info[RLS_INFO_KEY] = ctx
    db.execute(_SET_CONTEXT_SQL, _context_params(ctx))


def current_context(db: Session) -> Optional[dict]:
    ctx = db.info.get(RLS_INFO_KEY)
    return dict(ctx) if ctx else None


def set_tenant_context(
    db: Session,
    company_id: Optional[int],
    user_id: Optional[int] = None,
    user_email: Optional[str] = None,
    company_ids: Optional[Sequence[int]] = None,
) -> None:
    """Contexto de empresa (y opcionalmente usuario) para TODA la vida de `db`. `company_ids` por defecto
    es solo `company_id`. company_id None y sin company_ids = solo usuario (sus propias filas)."""
    ids: List[int] = [int(c) for c in (company_ids or []) if c is not None]
    if company_id is not None and int(company_id) not in ids:
        ids.insert(0, int(company_id))
    _apply(db, {
        "company_id": company_id if company_id is not None else (ids[0] if ids else None),
        "company_ids": ids,
        "user_id": user_id,
        "user_email": user_email,
        "mode": MODE_TENANT,
    })
    logger.debug("rls_context tenant company_ids=%s user_id=%s", ids, user_id)


def set_system_context(db: Session, reason: str, *, user_id: Optional[int] = None,
                       user_email: Optional[str] = None) -> None:
    """Vision global EXPLICITA y auditada. `reason` obligatorio: queda en el log (zeus.rls)."""
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("set_system_context requiere un motivo")
    if not is_postgres(db):
        return
    _apply(db, {"company_id": None, "company_ids": [], "user_id": user_id, "user_email": user_email,
                "mode": MODE_SYSTEM, "reason": reason})
    logger.info("rls_system_context reason=%s user_id=%s", reason, user_id)


def clear_context(db: Session) -> None:
    """Vuelve a 'sin contexto' (fail-closed) en la transaccion actual y en las siguientes."""
    if not is_postgres(db):
        return
    db.info.pop(RLS_INFO_KEY, None)
    db.execute(_SET_CONTEXT_SQL, _context_params({}))


def _new_session() -> Session:
    # Atributo del modulo en tiempo de llamada (mismo SessionLocal que get_db; respeta los parches de tests).
    from app.db import session as _session_module

    return _session_module.SessionLocal()


def open_system_session(reason: str) -> Session:
    """SessionLocal() en modo system (el llamador hace close())."""
    db = _new_session()
    try:
        set_system_context(db, reason)
    except Exception:
        db.close()
        raise
    return db


def open_tenant_session(company_id: Optional[int], *, user_id: Optional[int] = None,
                        user_email: Optional[str] = None,
                        company_ids: Optional[Sequence[int]] = None) -> Session:
    """SessionLocal() con contexto de UNA empresa (o del usuario si company_id es None)."""
    db = _new_session()
    try:
        set_tenant_context(db, company_id, user_id=user_id, user_email=user_email, company_ids=company_ids)
    except Exception:
        db.close()
        raise
    return db


def open_user_session(user_id: Optional[int]) -> Session:
    """SessionLocal() con el contexto completo de un usuario (sus empresas; system si es superusuario).
    Para hilos de fondo lanzados por una peticion de ese usuario. Sin usuario (None) o si no existe:
    sesion sin contexto (fail-closed)."""
    db = _new_session()
    if user_id in (None, ""):
        return db
    try:
        bind_user_id_context(db, int(user_id))
    except Exception:
        db.close()
        raise
    return db


@contextmanager
def system_db(reason: str) -> Iterator[Session]:
    db = open_system_session(reason)
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def tenant_db(company_id: Optional[int], *, user_id: Optional[int] = None,
              user_email: Optional[str] = None) -> Iterator[Session]:
    db = open_tenant_session(company_id, user_id=user_id, user_email=user_email)
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# --------------------------------------------------------------------------- usuario autenticado

def user_company_ids(db: Session, user_id: int) -> List[int]:
    """Empresas del usuario, primaria primero (mismo orden que primary_company_id). Requiere que el
    contexto ya identifique al usuario (la policy de user_companies deja ver sus propias filas)."""
    from app.models.company import UserCompany

    rows = (
        db.query(UserCompany.company_id)
        .filter(UserCompany.user_id == user_id)
        .order_by(UserCompany.id.asc())
        .all()
    )
    out: List[int] = []
    for (cid,) in rows:
        if cid is not None and int(cid) not in out:
            out.append(int(cid))
    return out


def bind_principal(db: Session, user_id: int, user_email: Optional[str] = None) -> None:
    """Paso previo a cargar al usuario autenticado (id sacado del JWT, del refresh token o del lookup
    acotado de login): contexto SOLO de ese usuario, sin empresas. La policy de users le deja leer su
    propia fila y la de user_companies sus vinculos; nada de ninguna empresa."""
    set_tenant_context(db, None, user_id=int(user_id), user_email=user_email)


def bind_user_context(db: Session, user) -> None:
    """Contexto definitivo de una peticion autenticada: usuario + todas sus empresas (primaria primero).
    Superusuario -> modo system con motivo (equivale al bypass de aplicacion de get_db_scoped)."""
    if not is_postgres(db):
        return
    uid = int(user.id)
    email = getattr(user, "email", None)
    if getattr(user, "is_superuser", False):
        set_system_context(db, f"superuser user_id={uid}", user_id=uid, user_email=email)
        return
    bind_principal(db, uid, email)
    ids = user_company_ids(db, uid)
    set_tenant_context(db, ids[0] if ids else None, user_id=uid, user_email=email, company_ids=ids)


def bind_user_id_context(db: Session, user_id: int):
    """bind_principal + carga del usuario + bind_user_context. Devuelve el User o None."""
    from app.models.user import User

    bind_principal(db, user_id)
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        clear_context(db)
        return None
    bind_user_context(db, user)
    return user


def bind_user_single_company(db: Session, user_id: int):
    """Contexto para una ruta SIN autenticar que actua en nombre de un usuario identificado por un dato
    acotado (web publica por slug, webhook firmado de Stripe): ese usuario y SOLO su empresa primaria.
    Nunca sus otras empresas y nunca modo system, aunque el usuario sea superusuario: la peticion la
    origina un tercero, no el usuario. Devuelve el User o None (contexto limpio)."""
    from app.models.user import User

    bind_principal(db, user_id)
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        clear_context(db)
        return None
    ids = user_company_ids(db, int(user_id)) if is_postgres(db) else []
    set_tenant_context(db, ids[0] if ids else None, user_id=int(user_id),
                       user_email=getattr(user, "email", None))
    return user


# --------------------------------------------------------------------------- lookups acotados (0071)

def lookup_user_id_by_email(db: Session, email: str) -> Optional[int]:
    """Id del usuario con ese email (normalizado) o None. En Postgres via auth_user_id_by_email()
    (SECURITY DEFINER: devuelve solo el id, no expone ninguna otra columna ni fila)."""
    e = (email or "").strip()
    if not e:
        return None
    if is_postgres(db):
        uid = db.execute(text("SELECT auth_user_id_by_email(:e)"), {"e": e}).scalar()
        return int(uid) if uid is not None else None
    from app.models.user import User

    row = db.query(User.id).filter(User.email == e.lower()).first() or \
        db.query(User.id).filter(User.email == e).first()
    return int(row[0]) if row else None


def company_slug_taken(db: Session, slug: str) -> bool:
    """El slug de empresa es UNICO GLOBAL: comprobarlo requiere ver todas las empresas. En Postgres via
    company_slug_taken() (SECURITY DEFINER, devuelve solo un booleano)."""
    if is_postgres(db):
        return bool(db.execute(text("SELECT company_slug_taken(:s)"), {"s": slug}).scalar())
    from app.models.company import Company

    return db.query(Company.id).filter(Company.slug == slug).first() is not None


def public_site_user_id_by_slug(db: Session, slug: str) -> Optional[int]:
    """Titular de la web publica `slug` (activa y habilitada) o None. Postgres: public_site_user_id_by_slug()."""
    if is_postgres(db):
        uid = db.execute(text("SELECT public_site_user_id_by_slug(:s)"), {"s": slug}).scalar()
        return int(uid) if uid is not None else None
    from app.models.user import User

    row = db.query(User.id).filter(
        User.public_site_slug == slug, User.public_site_enabled == True, User.is_active == True,  # noqa: E712
    ).first()
    return int(row[0]) if row else None


def preallocate_id(db: Session, table: str) -> Optional[int]:
    """Reserva el id de una fila NUEVA antes del INSERT (nextval de su secuencia), para poder fijar el
    contexto de esa fila (registro: usuario y empresa nuevos) antes de escribirla. None fuera de Postgres."""
    if not is_postgres(db):
        return None
    if table not in ("users", "companies"):
        raise ValueError(f"preallocate_id: tabla no prevista {table}")
    return int(db.execute(text(f"SELECT nextval(pg_get_serial_sequence('{table}', 'id'))")).scalar())


def prepare_new_company(db: Session, company) -> None:
    """Antes de db.add(Company(...)) de una empresa NUEVA: reserva su id y lo anade a las empresas del
    contexto, para que la policy (WITH CHECK id en las empresas del contexto) deje insertarla a ella, a su
    vinculo user_companies y a sus datos semilla, y nada de ninguna otra empresa. En modo system o fuera
    de Postgres no hace nada."""
    if not is_postgres(db):
        return
    ctx = current_context(db) or {}
    if ctx.get("mode") == MODE_SYSTEM:
        return
    cid = preallocate_id(db, "companies")
    company.id = cid
    ids = [int(c) for c in (ctx.get("company_ids") or [])]
    ids.append(cid)
    set_tenant_context(
        db,
        ctx.get("company_id") if ctx.get("company_id") is not None else cid,
        user_id=ctx.get("user_id"),
        user_email=ctx.get("user_email"),
        company_ids=ids,
    )


def open_activity_session(activity) -> Session:
    """Sesion para ejecutar una AgentActivity fuera de una peticion (executor, handlers). Actua como el
    USUARIO de la actividad (email fijado por el servidor al crearla; lookup acotado + sus empresas;
    superusuario -> system auditado). Sin usuario resoluble: contexto de la empresa de la actividad. Sin
    ninguno de los dos: sin contexto (fail-closed: no ve datos de ninguna empresa)."""
    db = _new_session()
    try:
        if not is_postgres(db):
            return db
        email = (getattr(activity, "user_email", None) or "").strip()
        uid = lookup_user_id_by_email(db, email) if email else None
        if uid is not None and bind_user_id_context(db, uid) is not None:
            return db
        cid = getattr(activity, "company_id", None)
        if cid is not None:
            set_tenant_context(db, int(cid), user_email=email or None)
        return db
    except Exception:
        db.close()
        raise
