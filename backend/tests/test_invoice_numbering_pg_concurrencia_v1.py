"""Numeracion INV por empresa bajo concurrencia REAL contra PostgreSQL (services/invoice_numbering_v1 + 0070).

SQLite no tiene concurrencia de escritura real ni plpgsql, asi que este test usa un Postgres de verdad YA
MIGRADO a 0070 (tabla invoice_counters + funcion invoice_next_number), indicado en ZEUS_TEST_PG_URL, por ej.
    ZEUS_TEST_PG_URL=postgresql://postgres@localhost:55432/<copia de zeus_en0069 migrada a 0070>
El rol de ZEUS_TEST_PG_URL crea/borra dos empresas de prueba; las altas se hacen como el rol de aplicacion
(ZEUS_TEST_PG_APP_ROLE, por defecto zeus_app: sin SUPERUSER ni BYPASSRLS, con DML sobre companies/invoices/
invoice_counters) y con el contexto RLS de su empresa, igual que POST /invoices/.
Si falta la variable, el servidor no responde, la BD no esta en 0070 o el rol no existe/no tiene permisos
-> skip con el motivo. Al final se borran las facturas, contadores y empresas de prueba.

Cada creacion: hilo propio, sesion/conexion propia, threading.Barrier para arrancar a la vez, y en UNA
transaccion next_invoice_number() + (pausa) + INSERT + commit/rollback. La pausa ensancha la ventana entre
reservar el numero y confirmar, para que la carrera sea determinista.
  - misma empresa, N altas simultaneas -> numeros consecutivos sin repetir y 0 errores;
  - altas que hacen rollback -> no consumen numero (sin huecos);
  - dos empresas a la vez -> cada una su serie, y no se bloquean entre si;
  - con contexto RLS de A no se puede mover el contador de B;
  - sin la funcion SQL (migracion no aplicada) -> HTTPException 503 clara, no un 500 opaco;
  - CONTROL: leyendo el contador sin bloquearlo (leer + escribir, como el antiguo count/max + 1) la misma
    carrera repite numero -> UniqueViolation en uq_invoices_company_id_invoice_number.
"""
from __future__ import annotations

import os
import threading
import time
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

import services.invoice_numbering_v1 as numbering
from app.db.tenant_context import set_tenant_context

PG_URL = os.environ.get("ZEUS_TEST_PG_URL", "").strip()
APP_ROLE = os.environ.get("ZEUS_TEST_PG_APP_ROLE", "zeus_app").strip()
N = 6
WINDOW_S = 0.4


@pytest.fixture(scope="module")
def pg():
    if not PG_URL:
        pytest.skip("ZEUS_TEST_PG_URL no definida: este test necesita un PostgreSQL real migrado a 0070")
    if not PG_URL.startswith("postgresql"):
        pytest.skip(f"ZEUS_TEST_PG_URL no es PostgreSQL: {PG_URL.split('@')[-1]}")
    admin = create_engine(PG_URL, poolclass=NullPool, connect_args={"connect_timeout": 3})
    try:
        with admin.connect() as c:
            if c.execute(text("SELECT to_regprocedure('public.invoice_next_number(integer, varchar)')")).scalar() is None:
                pytest.skip("la BD de ZEUS_TEST_PG_URL no tiene la migracion 0070 (invoice_next_number)")
            role = c.execute(text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = :r"),
                             {"r": APP_ROLE}).first()
            if role is None:
                pytest.skip(f"no existe el rol de aplicacion {APP_ROLE!r}")
            assert tuple(role) == (False, False), f"{APP_ROLE} no debe ser SUPERUSER ni BYPASSRLS"
            for table, priv in (("invoices", "INSERT"), ("invoice_counters", "UPDATE"), ("companies", "SELECT")):
                if not c.execute(text("SELECT has_table_privilege(:r, :t, :p)"),
                                 {"r": APP_ROLE, "t": table, "p": priv}).scalar():
                    pytest.skip(f"{APP_ROLE} no tiene {priv} sobre {table} en esa BD")
    except OperationalError as e:
        admin.dispose()
        pytest.skip(f"PostgreSQL de ZEUS_TEST_PG_URL no responde: {str(e.orig).splitlines()[0]}")
    tag = uuid.uuid4().hex[:8]
    with admin.begin() as c:
        ids = [c.execute(text(
            "INSERT INTO companies (company_name, slug, status, currency) "
            "VALUES (:n, :s, 'active', 'EUR') RETURNING id"), {"n": f"Num PG {tag} {k}", "s": f"num-pg-{tag}-{k}"}
        ).scalar_one() for k in ("a", "b")]
    app_eng = create_engine(PG_URL, poolclass=NullPool,
                            connect_args={"connect_timeout": 3, "options": f"-c role={APP_ROLE}"})
    try:
        yield admin, app_eng, ids[0], ids[1]
    finally:
        app_eng.dispose()
        with admin.begin() as c:
            c.execute(text("DELETE FROM invoices WHERE company_id = ANY(:ids)"), {"ids": ids})
            c.execute(text("DELETE FROM invoice_counters WHERE company_id = ANY(:ids)"), {"ids": ids})
            c.execute(text("DELETE FROM companies WHERE id = ANY(:ids)"), {"ids": ids})
        admin.dispose()


def _counter(admin, cid):
    with admin.connect() as c:
        return c.execute(text("SELECT coalesce(max(last_number), 0) FROM invoice_counters "
                              "WHERE company_id = :c AND series = 'INV'"), {"c": cid}).scalar()


def _stored(admin, cid):
    with admin.connect() as c:
        return c.execute(text("SELECT invoice_number FROM invoices WHERE company_id = :c"), {"c": cid}).scalars().all()


def _n(number):
    return int(number.rsplit("-", 1)[1])


def _run(app_eng, jobs):
    """jobs: lista de (company_id, rollback?). Devuelve (numeros confirmados por empresa, errores, segundos)."""
    barrier = threading.Barrier(len(jobs))
    done, errors, lock = {}, [], threading.Lock()

    def worker(cid, rollback):
        with Session(app_eng) as db:
            set_tenant_context(db, cid, user_id=None)
            barrier.wait()
            try:
                num = numbering.next_invoice_number(db, cid)
                time.sleep(WINDOW_S)  # entre reservar el numero y confirmar la factura
                db.execute(text("INSERT INTO invoices (invoice_number, company_id) VALUES (:n, :c)"),
                           {"n": num, "c": cid})
                if rollback:
                    db.rollback()  # la creacion falla despues de reservar numero
                    return
                db.commit()
                with lock:
                    done.setdefault(cid, []).append(num)
            except (IntegrityError, DBAPIError) as e:
                db.rollback()
                with lock:
                    errors.append(type(e.orig).__name__)

    threads = [threading.Thread(target=worker, args=job) for job in jobs]
    t0 = time.monotonic()
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=90)
    elapsed = time.monotonic() - t0
    assert not any(t.is_alive() for t in threads), "algun hilo no termino (bloqueo colgado?)"
    return done, errors, elapsed


def test_same_company_concurrent_creations_are_consecutive(pg):
    admin, app_eng, a, _ = pg
    start = _counter(admin, a)
    done, errors, _ = _run(app_eng, [(a, False)] * N)
    print(f"[misma empresa] {sorted(done.get(a, []), key=_n)} errores={errors}")
    assert errors == []
    assert sorted(_n(x) for x in done[a]) == list(range(start + 1, start + N + 1))
    assert _counter(admin, a) == start + N
    assert sorted(_stored(admin, a)) == sorted(done[a])


def test_rolled_back_creations_do_not_consume_numbers(pg):
    admin, app_eng, a, _ = pg
    start = _counter(admin, a)
    before = set(_stored(admin, a))
    jobs = [(a, i % 3 == 0) for i in range(N)]  # 2 de 6 hacen rollback tras reservar
    done, errors, _ = _run(app_eng, jobs)
    ok = N - sum(1 for _, rb in jobs if rb)
    print(f"[rollback] confirmadas={sorted(done.get(a, []), key=_n)} errores={errors}")
    assert errors == []
    assert sorted(_n(x) for x in done[a]) == list(range(start + 1, start + ok + 1))  # sin huecos
    assert _counter(admin, a) == start + ok
    assert set(_stored(admin, a)) - before == set(done[a])


def test_two_companies_get_independent_series_without_blocking_each_other(pg):
    admin, app_eng, a, b = pg
    sa, sb = _counter(admin, a), _counter(admin, b)
    per = 3
    done, errors, elapsed = _run(app_eng, [(a, False)] * per + [(b, False)] * per)
    print(f"[dos empresas] A={sorted(done[a], key=_n)} B={sorted(done[b], key=_n)} {elapsed:.2f}s")
    assert errors == []
    assert sorted(_n(x) for x in done[a]) == list(range(sa + 1, sa + per + 1))
    assert sorted(_n(x) for x in done[b]) == list(range(sb + 1, sb + per + 1))
    # Dentro de una empresa las altas se serializan (per * WINDOW_S); si ademas se bloquearan entre empresas
    # tardaria >= 2 * per * WINDOW_S.
    assert elapsed < 2 * per * WINDOW_S * 0.9, f"las empresas parecen bloquearse entre si ({elapsed:.2f}s)"


def test_rls_context_of_a_cannot_bump_counter_of_b(pg):
    admin, app_eng, a, b = pg
    sb = _counter(admin, b)
    with Session(app_eng) as db:
        set_tenant_context(db, a, user_id=None)
        with pytest.raises(DBAPIError, match="row-level security"):
            numbering.next_invoice_number(db, b)
    assert _counter(admin, b) == sb


def test_control_unlocked_read_then_write_collides(pg, monkeypatch):
    """CONTROL: leer el contador y escribirlo despues, sin bloquear la fila, repite numero."""
    admin, app_eng, a, _ = pg

    def unlocked(db, cid, series):
        n = db.execute(text("SELECT coalesce(max(last_number), 0) + 1 FROM invoice_counters "
                            "WHERE company_id = :c AND series = :s"), {"c": cid, "s": series}).scalar_one()
        time.sleep(WINDOW_S)
        db.execute(text("UPDATE invoice_counters SET last_number = :n WHERE company_id = :c AND series = :s"),
                   {"n": n, "c": cid, "s": series})
        return int(n)

    monkeypatch.setattr(numbering, "_next_counter_value_pg", unlocked)
    done, errors, _ = _run(app_eng, [(a, False)] * N)
    print(f"[CONTROL sin bloqueo] confirmadas={sorted(done.get(a, []), key=_n)} errores={errors}")
    assert errors, "sin bloqueo se esperaba choque y no lo hubo"
    assert set(errors) == {"UniqueViolation"}


def test_missing_function_gives_clear_503_not_opaque_500(pg):
    """BD sin la funcion de 0070 (upgrade fallido + arranque igualmente): error claro 503, sin crear nada.
    Se borra la funcion DENTRO de una transaccion que el propio helper deshace (DDL transaccional en Postgres)."""
    from fastapi import HTTPException

    admin, _, a, _ = pg
    start = _counter(admin, a)
    with Session(admin) as db:
        db.execute(text("DROP FUNCTION invoice_next_number(integer, varchar)"))
        with pytest.raises(HTTPException) as exc:
            numbering.next_invoice_number(db, a)
    assert exc.value.status_code == 503
    assert exc.value.detail["error"] == "invoice_numbering_unavailable"
    with admin.connect() as c:  # el rollback del helper devolvio la funcion
        assert c.execute(text("SELECT to_regprocedure('public.invoice_next_number(integer, varchar)')")).scalar()
    assert _counter(admin, a) == start
