"""Cashflow con ?company_id de otra empresa contra PostgreSQL REAL, conectando como el rol de aplicacion (zeus_app).

Con RLS (0071) la consulta sobre la empresa B ya no devolvia filas, pero el endpoint respondia 200 con saldo 0
(lo inaceptable: parece un dato real). Ahora la empresa sale de la sesion y una ajena es 403
(crm_office_service.resolve_company_for_user). Se ejecutan las funciones REALES de los endpoints sobre una
sesion conectada como zeus_app con el contexto RLS que fija la autenticacion (rls_context.bind_user_id_context).
Necesita ZEUS_TEST_PG_URL (rol que pueda sembrar, p. ej. postgres) de una BD migrada a 0071; sin ella, skip.
"""
from __future__ import annotations

import os
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.api.v1.endpoints.cashflow import cashflow_balance, cashflow_summary
from app.db import rls_context as rc

PG_URL = os.environ.get("ZEUS_TEST_PG_URL", "").strip()
APP_ROLE = os.environ.get("ZEUS_TEST_PG_APP_ROLE", "zeus_app").strip()


@pytest.fixture(scope="module")
def pg():
    if not PG_URL or not PG_URL.startswith("postgresql"):
        pytest.skip("ZEUS_TEST_PG_URL (PostgreSQL migrado a 0071) no definida")
    admin = create_engine(PG_URL, poolclass=NullPool, connect_args={"connect_timeout": 3})
    try:
        with admin.connect() as c:
            if c.execute(text("SELECT to_regprocedure('public.app_ctx_company_ids()')")).scalar() is None:
                pytest.skip("la BD de ZEUS_TEST_PG_URL no tiene la migracion 0071")
            role = c.execute(text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = :r"), {"r": APP_ROLE}).first()
            if role is None:
                pytest.skip(f"no existe el rol {APP_ROLE!r}")
            assert tuple(role) == (False, False)
    except OperationalError as e:
        admin.dispose()
        pytest.skip(f"PostgreSQL no responde: {str(e.orig).splitlines()[0]}")
    ids = {}
    with admin.begin() as c:
        for side, amount in (("a", 123.5), ("b", 777.0)):
            k = uuid.uuid4().hex[:10]
            cid = c.execute(text("INSERT INTO companies (company_name, slug, status, currency) VALUES (:n, :s, 'active', 'EUR') "
                                 "RETURNING id"), {"n": f"CFPG {side} {k}", "s": f"cfpg-{side}-{k}"}).scalar_one()
            uid = c.execute(text("INSERT INTO users (email, hashed_password, is_active) VALUES (:e, 'x', true) RETURNING id"),
                            {"e": f"cfpg_{side}_{k}@example.com"}).scalar_one()
            c.execute(text("INSERT INTO user_companies (user_id, company_id, role) VALUES (:u, :c, 'company_admin')"),
                      {"u": uid, "c": cid})
            c.execute(text("INSERT INTO cashflow_ledger (company_id, amount, direction, source) VALUES (:c, :a, 'in', 'test_pg')"),
                      {"c": cid, "a": amount})
            ids[side] = (cid, uid)
    app_eng = create_engine(PG_URL, poolclass=NullPool, connect_args={"connect_timeout": 3, "options": f"-c role={APP_ROLE}"})
    try:
        yield app_eng, ids
    finally:
        app_eng.dispose()
        with admin.begin() as c:
            for cid, uid in ids.values():
                c.execute(text("DELETE FROM cashflow_ledger WHERE company_id = :c"), {"c": cid})
                c.execute(text("DELETE FROM user_companies WHERE user_id = :u"), {"u": uid})
                c.execute(text("DELETE FROM users WHERE id = :u"), {"u": uid})
                c.execute(text("DELETE FROM companies WHERE id = :c"), {"c": cid})
        admin.dispose()


def _session_as(app_eng, uid):
    db = Session(app_eng)
    user = rc.bind_user_id_context(db, uid)  # lo mismo que hace get_current_user en cada peticion
    assert user is not None
    assert db.execute(text("SELECT current_user")).scalar() == APP_ROLE
    return db, user


@pytest.mark.parametrize("endpoint", ["balance", "summary"])
def test_other_company_is_403_as_app_role(pg, endpoint):
    app_eng, ids = pg
    db, user_a = _session_as(app_eng, ids["a"][1])
    try:
        with pytest.raises(HTTPException) as e:
            if endpoint == "balance":
                cashflow_balance(company_id=ids["b"][0], current_user=user_a, db=db)
            else:
                cashflow_summary(company_id=ids["b"][0], days=30, current_user=user_a, db=db)
        assert e.value.status_code == 403
    finally:
        db.close()


def test_own_company_returns_real_balance_as_app_role(pg):
    app_eng, ids = pg
    db, user_a = _session_as(app_eng, ids["a"][1])
    try:
        own = cashflow_balance(company_id=ids["a"][0], current_user=user_a, db=db)
        default = cashflow_balance(company_id=None, current_user=user_a, db=db)
        summary = cashflow_summary(company_id=None, days=30, current_user=user_a, db=db)
    finally:
        db.close()
    assert own == default == {"success": True, "company_id": ids["a"][0], "balance": 123.5}
    assert summary["success"] is True
