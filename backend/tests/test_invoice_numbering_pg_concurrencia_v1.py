"""Numeracion INV bajo concurrencia REAL contra PostgreSQL (services/invoice_numbering_v1).

Peticion de Carlos: "test con dos creaciones concurrentes". SQLite no tiene concurrencia de escritura real ni
advisory locks, asi que este test usa un Postgres de verdad indicado en ZEUS_TEST_PG_URL, por ejemplo
    ZEUS_TEST_PG_URL=postgresql://postgres@localhost:55432/zeus_en0069
Si la variable no esta o el servidor no responde -> skip con el motivo.

Aislamiento: no toca las tablas de la BD indicada. Crea un esquema temporal propio con una tabla `invoices`
minima (id, invoice_number UNIQUE, como el indice global real) y cada conexion usa search_path a ese esquema;
asi no depende de datos previos y al final se hace DROP SCHEMA ... CASCADE.

Cada creacion: hilo propio, sesion/conexion propia, threading.Barrier para arrancar a la vez, y en UNA
transaccion next_invoice_number() + INSERT + commit (lo mismo que hacen POST /invoices/ y el escaneo QR).
Para que la carrera sea determinista se ensancha la ventana entre leer el maximo e insertar (sleep en un
envoltorio de _max_series_suffix, solo dentro del test).
  - test_concurrent_creations_get_distinct_numbers: con el bloqueo real -> N numeros distintos, 0 IntegrityError.
  - test_control_without_lock_collides: CONTROL. Con el bloqueo sustituido por un no-op (monkeypatch, solo en
    el test) -> se repite numero / IntegrityError. Demuestra que el test detecta el fallo y que lo que lo evita
    es el bloqueo.
"""
from __future__ import annotations

import os
import threading
import time
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

import services.invoice_numbering_v1 as numbering

PG_URL = os.environ.get("ZEUS_TEST_PG_URL", "").strip()
N = 6
WINDOW_S = 0.3


@pytest.fixture(scope="module")
def pg_engine():
    if not PG_URL:
        pytest.skip("ZEUS_TEST_PG_URL no definida: este test necesita un PostgreSQL real (p. ej. "
                    "postgresql://postgres@localhost:55432/zeus_en0069)")
    if not PG_URL.startswith("postgresql"):
        pytest.skip(f"ZEUS_TEST_PG_URL no es PostgreSQL: {PG_URL.split('@')[-1]}")
    schema = f"t_invnum_{uuid.uuid4().hex[:10]}"
    admin = create_engine(PG_URL, poolclass=NullPool, connect_args={"connect_timeout": 3})
    try:
        with admin.begin() as c:
            c.execute(text(f'CREATE SCHEMA "{schema}"'))
            c.execute(text(f'CREATE TABLE "{schema}".invoices (id serial PRIMARY KEY, '
                           f'invoice_number varchar(50) NOT NULL, company_id integer)'))
            c.execute(text(f'CREATE UNIQUE INDEX ON "{schema}".invoices (invoice_number)'))
    except OperationalError as e:
        admin.dispose()
        pytest.skip(f"PostgreSQL de ZEUS_TEST_PG_URL no responde: {str(e.orig).splitlines()[0]}")
    eng = create_engine(PG_URL, poolclass=NullPool,
                        connect_args={"connect_timeout": 3, "options": f"-csearch_path={schema}"})
    try:
        yield eng
    finally:
        eng.dispose()
        with admin.begin() as c:
            c.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def clean_table(pg_engine):
    with pg_engine.begin() as c:
        c.execute(text("TRUNCATE invoices RESTART IDENTITY"))
    yield pg_engine


def _widen_race_window(monkeypatch):
    real = numbering._max_series_suffix

    def slow(db):
        n = real(db)
        time.sleep(WINDOW_S)  # entre leer el maximo y que el llamador inserte
        return n

    monkeypatch.setattr(numbering, "_max_series_suffix", slow)


def _run_concurrent(engine):
    barrier = threading.Barrier(N)
    results, errors = [], []
    lock = threading.Lock()

    def worker(i):
        with Session(engine) as db:
            barrier.wait()
            try:
                num = numbering.next_invoice_number(db)
                db.execute(text("INSERT INTO invoices (invoice_number, company_id) VALUES (:n, :c)"),
                           {"n": num, "c": i % 2 + 1})  # dos empresas
                db.commit()
                with lock:
                    results.append(num)
            except IntegrityError as e:
                db.rollback()
                with lock:
                    errors.append(type(e.orig).__name__)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert not any(t.is_alive() for t in threads), "algun hilo no termino (bloqueo colgado?)"
    with engine.connect() as c:
        stored = c.execute(text("SELECT invoice_number FROM invoices")).scalars().all()
    return results, errors, stored


def test_concurrent_creations_get_distinct_numbers(clean_table, monkeypatch):
    _widen_race_window(monkeypatch)
    results, errors, stored = _run_concurrent(clean_table)
    print(f"[con bloqueo] numeros={sorted(results)} errores={errors} en_bd={len(stored)}")
    assert errors == []
    assert len(results) == N and len(set(results)) == N, results
    assert sorted(int(n.rsplit("-", 1)[1]) for n in results) == list(range(1, N + 1))
    assert sorted(stored) == sorted(results)


def test_control_without_lock_collides(clean_table, monkeypatch):
    """CONTROL: sin el advisory lock la misma carrera repite numero (IntegrityError en el UNIQUE)."""
    _widen_race_window(monkeypatch)
    monkeypatch.setattr(numbering, "_acquire_series_lock", lambda db: None)
    results, errors, stored = _run_concurrent(clean_table)
    print(f"[sin bloqueo] numeros={sorted(results)} errores={errors} en_bd={sorted(stored)}")
    assert errors, f"sin bloqueo se esperaba choque y no lo hubo: {results}"
    assert set(errors) == {"UniqueViolation"}
    assert len(stored) < N
