"""RLS: el contexto de empresa sobrevive a los commits de la peticion (app/db/tenant_context.py).

Antes: set_tenant_context / get_db_scoped hacian `set_config(..., true)` (local a la transaccion). Tras el
primer `db.commit()` de la peticion el contexto desaparecia y, con la policy fail-open de 0047, el resto de la
peticion veia facturas de TODAS las empresas. Ahora el contexto se guarda en `Session.info` y un evento
`after_begin` lo re-fija en cada transaccion.

Necesita un PostgreSQL real (RLS no existe en SQLite) indicado en ZEUS_TEST_PG_URL con un rol capaz de crear
esquemas y de hacer SET ROLE al rol de aplicacion (por defecto zeus_app, sin SUPERUSER ni BYPASSRLS; se puede
cambiar con ZEUS_TEST_PG_APP_ROLE). Por ejemplo:
    ZEUS_TEST_PG_URL=postgresql://postgres@localhost:55432/zeus_en0069
Si falta la variable, el servidor no responde o el rol no existe -> skip con el motivo.

Aislamiento: no toca las tablas de la BD. Crea un esquema temporal con una tabla `invoices` minima y le aplica
la MISMA expresion de policy que tiene `public.invoices` en esa BD (leida de pg_policies: se prueba la policy
real migrada, no una copia escrita a mano), ENABLE + FORCE RLS, y se conecta como el rol de aplicacion.
  - CONTROL: sin el evento after_begin el contexto se pierde tras commit (el test detecta el fallo).

Desde 0071 la policy es FAIL-CLOSED: sin contexto no se ve nada (antes, 0047: se veia todo). Los tests leen la
policy real y comprueban el comportamiento de la generacion migrada en esa BD.
"""
from __future__ import annotations

import os
import threading
import uuid

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool, QueuePool

import app.db.tenant_context as tc

PG_URL = os.environ.get("ZEUS_TEST_PG_URL", "").strip()
APP_ROLE = os.environ.get("ZEUS_TEST_PG_APP_ROLE", "zeus_app").strip()
A, B = 101, 202
ROWS = {A: 3, B: 5}
POLICY = {"fail_closed": None}  # se rellena con la policy real leida de la BD


@pytest.fixture(scope="module")
def schema():
    if not PG_URL:
        pytest.skip("ZEUS_TEST_PG_URL no definida: este test necesita un PostgreSQL real con RLS")
    if not PG_URL.startswith("postgresql"):
        pytest.skip(f"ZEUS_TEST_PG_URL no es PostgreSQL: {PG_URL.split('@')[-1]}")
    admin = create_engine(PG_URL, poolclass=NullPool, connect_args={"connect_timeout": 3})
    name = f"t_rlsctx_{uuid.uuid4().hex[:10]}"
    try:
        with admin.begin() as c:
            role = c.execute(text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = :r"),
                             {"r": APP_ROLE}).first()
            if role is None:
                pytest.skip(f"no existe el rol de aplicacion {APP_ROLE!r} en esa BD")
            assert role == (False, False), f"{APP_ROLE} no debe ser SUPERUSER ni BYPASSRLS: {tuple(role)}"
            qual = c.execute(text("SELECT qual FROM pg_policies WHERE schemaname = 'public' "
                                  "AND tablename = 'invoices' AND policyname = 'tenant_isolation_invoices'")).scalar()
            if not qual:
                pytest.skip("public.invoices no tiene la policy tenant_isolation_invoices (BD sin 0047)")
            POLICY["fail_closed"] = "app_ctx_company_ids" in qual  # 0071
            c.execute(text(f'CREATE SCHEMA "{name}"'))
            c.execute(text(f'CREATE TABLE "{name}".invoices (id serial PRIMARY KEY, company_id integer, '
                           f'created_by integer, invoice_number varchar(50))'))
            for cid, n in ROWS.items():
                for i in range(n):
                    c.execute(text(f'INSERT INTO "{name}".invoices (company_id, invoice_number) VALUES (:c, :n)'),
                              {"c": cid, "n": f"T-{cid}-{i}"})
            c.execute(text(f'ALTER TABLE "{name}".invoices ENABLE ROW LEVEL SECURITY'))
            c.execute(text(f'ALTER TABLE "{name}".invoices FORCE ROW LEVEL SECURITY'))
            c.execute(text(f'CREATE POLICY p ON "{name}".invoices USING ({qual})'))
            c.execute(text(f'GRANT USAGE ON SCHEMA "{name}" TO {APP_ROLE}'))
            c.execute(text(f'GRANT SELECT, INSERT, UPDATE, DELETE ON "{name}".invoices TO {APP_ROLE}'))
            c.execute(text(f'GRANT USAGE ON ALL SEQUENCES IN SCHEMA "{name}" TO {APP_ROLE}'))
    except OperationalError as e:
        admin.dispose()
        pytest.skip(f"PostgreSQL de ZEUS_TEST_PG_URL no responde: {str(e.orig).splitlines()[0]}")
    try:
        yield name
    finally:
        with admin.begin() as c:
            c.execute(text(f'DROP SCHEMA "{name}" CASCADE'))
        admin.dispose()


def _engine(schema, **kw):
    return create_engine(PG_URL, connect_args={"connect_timeout": 3,
                                               "options": f"-c role={APP_ROLE} -c search_path={schema}"}, **kw)


@pytest.fixture
def engine(schema):
    eng = _engine(schema, poolclass=NullPool)
    yield eng
    eng.dispose()


Q = "SELECT count(*), count(DISTINCT company_id), min(company_id), current_user FROM invoices"


def _see(db):
    n, companies, cid, role = db.execute(text(Q)).one()
    assert role == APP_ROLE
    return n, companies, cid


def test_role_is_not_superuser_and_behaviour_without_context(engine):
    """Sin contexto: 0071 (fail-closed) no deja ver ninguna fila; 0047 (fail-open) dejaba ver todas."""
    with Session(engine) as db:
        if POLICY["fail_closed"]:
            assert _see(db) == (0, 0, None)
        else:
            assert _see(db) == (sum(ROWS.values()), 2, A)


def test_company_a_never_sees_b_first_query_and_after_commit(engine):
    with Session(engine) as db:
        tc.set_tenant_context(db, A, user_id=1, user_email="a@example.test")
        assert _see(db) == (ROWS[A], 1, A)          # primera consulta
        db.commit()
        assert _see(db) == (ROWS[A], 1, A)          # tras commit (antes: veia A+B)
        db.execute(text("INSERT INTO invoices (company_id, invoice_number) VALUES (:c, 'T-new')"), {"c": A})
        db.commit()
        assert _see(db) == (ROWS[A] + 1, 1, A)      # tras un segundo commit con escritura
        with pytest.raises(ProgrammingError):
            db.execute(text("SELECT no_existe FROM invoices"))
        db.rollback()
        assert _see(db) == (ROWS[A] + 1, 1, A)      # tras error + rollback
        db.execute(text("DELETE FROM invoices WHERE invoice_number = 'T-new'"))
        db.commit()


def test_write_to_other_company_is_rejected_after_commit(engine):
    with Session(engine) as db:
        tc.set_tenant_context(db, A, user_id=1)
        db.commit()
        assert db.execute(text("UPDATE invoices SET invoice_number = invoice_number WHERE company_id = :b"),
                          {"b": B}).rowcount == 0
        with pytest.raises(ProgrammingError, match="row-level security"):
            db.execute(text("INSERT INTO invoices (company_id, invoice_number) VALUES (:b, 'T-x')"), {"b": B})
        db.rollback()


def test_pooled_connection_does_not_leak_context(schema):
    """Misma conexion fisica reutilizada (pool de 1): la sesion siguiente sin contexto no hereda el de A."""
    eng = _engine(schema, poolclass=QueuePool, pool_size=1, max_overflow=0)
    try:
        with Session(eng) as db:
            tc.set_tenant_context(db, A, user_id=1)
            db.commit()
            pid_a = db.execute(text("SELECT pg_backend_pid()")).scalar()
            assert _see(db)[2] == A
        with Session(eng) as db:
            pid, setting = db.execute(text(
                "SELECT pg_backend_pid(), current_setting('app.current_company_id', true)")).one()
            assert pid == pid_a
            assert setting in ("", None)
        with Session(eng) as db:
            tc.set_tenant_context(db, B, user_id=2)
            db.commit()
            assert _see(db) == (ROWS[B], 1, B)
    finally:
        eng.dispose()


def test_concurrent_sessions_a_and_b_never_cross(schema):
    eng = _engine(schema, poolclass=QueuePool, pool_size=4, max_overflow=0)
    errors, barrier = [], threading.Barrier(4)

    def worker(cid):
        with Session(eng) as db:
            tc.set_tenant_context(db, cid, user_id=cid)
            barrier.wait()
            for i in range(25):
                got = _see(db)
                if got != (ROWS[cid], 1, cid):
                    errors.append((cid, i, got))
                db.commit()

    threads = [threading.Thread(target=worker, args=(c,)) for c in (A, B, A, B)]
    try:
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        assert not any(t.is_alive() for t in threads)
    finally:
        eng.dispose()
    assert errors == []


def test_control_without_after_begin_context_is_lost_after_commit(engine):
    """CONTROL: sin el evento el contexto se pierde tras commit (fuga con 0047, vacio con 0071)."""
    event.remove(Session, "after_begin", tc._reapply_tenant_context)
    try:
        with Session(engine) as db:
            tc.set_tenant_context(db, A, user_id=1)
            assert _see(db) == (ROWS[A], 1, A)
            db.commit()
            # contexto perdido: fail-open (0047) veia A y B; fail-closed (0071) no ve nada (sin fuga)
            expected = (0, 0, None) if POLICY["fail_closed"] else (sum(ROWS.values()), 2, A)
            assert _see(db) == expected
    finally:
        event.listen(Session, "after_begin", tc._reapply_tenant_context)
    with Session(engine) as db:
        tc.set_tenant_context(db, A, user_id=1)
        db.commit()
        assert _see(db) == (ROWS[A], 1, A)
