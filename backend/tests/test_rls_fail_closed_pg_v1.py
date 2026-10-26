"""RLS fail-closed (migracion 0071) contra un PostgreSQL REAL conectando como rol de aplicacion sin privilegios.

Necesita ZEUS_TEST_PG_URL (rol con permiso para sembrar datos, p. ej. postgres) de una BD migrada a 0071 y el rol
de aplicacion (por defecto zeus_app, sin SUPERUSER ni BYPASSRLS; ZEUS_TEST_PG_APP_ROLE para cambiarlo):
    ZEUS_TEST_PG_URL=postgresql://postgres@localhost:55432/<copia migrada a 0071>
Sin la variable, sin servidor, sin la migracion o sin el rol -> skip con el motivo.

Siembra dos empresas A y B (con su usuario) en tablas de cada grupo (CRM/clientes, productos/inventario,
TPV/ventas, facturas/cobros, gastos, documentos/ficheros, mensajes, aprobaciones, RRHH, flujos, transacciones)
con el rol administrador y comprueba, con las primitivas reales de app/db/rls_context.py:
- sin contexto no se ve ninguna fila; en modo system se ven todas;
- con el contexto de A solo se ven las de A, en la primera consulta, tras commit, tras error+rollback y tras
  escribir; las hijas sin company_id (lineas, cobros, variantes, contactos, lineas de ticket, eventos) siguen
  a su padre;
- escribir en B con el contexto de A falla (INSERT/UPDATE a B: error de policy; UPDATE de filas de B: 0 filas);
- las filas sin empresa con dueno solo las ve su dueno; users/companies/user_companies acotados;
- las funciones acotadas de login devuelven solo el id; contexto basura -> 0 filas sin error.
Al terminar borra lo sembrado.
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.db import rls_context as rc

PG_URL = os.environ.get("ZEUS_TEST_PG_URL", "").strip()
APP_ROLE = os.environ.get("ZEUS_TEST_PG_APP_ROLE", "zeus_app").strip()

# tabla -> SQL de insercion (admin) con :c empresa, :u usuario, :p padre, :k sufijo unico. Devuelve id.
SEED = {
    "customers": "INSERT INTO customers (name, company_id, owner_user_id) VALUES ('C '||:k, :c, :u) RETURNING id",
    "crm_leads": "INSERT INTO crm_leads (name, company_id) VALUES ('L '||:k, :c) RETURNING id",
    "products": "INSERT INTO products (sku, name, price, company_id) VALUES ('S'||:k, 'P', 1, :c) RETURNING id",
    "tpv_products": ("INSERT INTO tpv_products (user_id, company_id, name, product_id, price, category, price_with_iva) "
                     "VALUES (:u, :c, 'TP', 'TP'||:k, 1, 'g', 1.21) RETURNING id"),
    "tpv_sales": ("INSERT INTO tpv_sales (user_id, company_id, document_type, subtotal, total, tax_amount, ticket_id, "
                  "payment_method) VALUES (:u, :c, 'ticket', 1, 1.21, 0.21, 'TK'||:k, 'efectivo') RETURNING id"),
    "invoices": "INSERT INTO invoices (invoice_number, company_id, created_by) VALUES ('RLS-'||:k, :c, :u) RETURNING id",
    "expenses": ("INSERT INTO expenses (supplier_name, company_id, issue_date) VALUES ('Prov', :c, now()) RETURNING id"),
    "scan_events": "INSERT INTO scan_events (company_id, scan_type, raw_payload) VALUES (:c, 'qr', 'x') RETURNING id",
    "company_employees": ("INSERT INTO company_employees (company_id, employee_code, full_name) "
                          "VALUES (:c, 'E'||:k, 'Emp') RETURNING id"),
    "teamflow_items": ("INSERT INTO teamflow_items (owner_agent, title, public_id, user_id, company_id) "
                       "VALUES ('ZEUS', 'T', 'tf'||:k, :u, :c) RETURNING id"),
    "outbound_messages": ("INSERT INTO outbound_messages (status, channel, recipient_hash, purpose, company_id, user_id) "
                          "VALUES ('sent', 'email', 'h'||:k, 'direct', :c, :u) RETURNING id"),
    "zeus_transactions": "INSERT INTO zeus_transactions (transaction_id, company_id) VALUES ('tx'||:k, :c) RETURNING id",
}
CHILD_SEED = {  # hija -> (padre, SQL con :p)
    "invoice_items": ("invoices", "INSERT INTO invoice_items (invoice_id, description, unit_price) VALUES (:p, 'L', 1) RETURNING id"),
    "payments": ("invoices", "INSERT INTO payments (invoice_id, amount, payment_method) VALUES (:p, 1, 'cash') RETURNING id"),
    "product_variants": ("products", "INSERT INTO product_variants (product_id, name, sku) VALUES (:p, 'V', 'V'||:k) RETURNING id"),
    "customer_contacts": ("customers", "INSERT INTO customer_contacts (customer_id, name) VALUES (:p, 'Ct') RETURNING id"),
    "tpv_sale_items": ("tpv_sales", ("INSERT INTO tpv_sale_items (tpv_sale_id, product_id, product_name, quantity, unit_price, "
                                     "base_amount, tax_amount, tax_rate_snapshot) VALUES (:p, 'TP', 'TP', 1, 1, 1, 0.21, 0.21) RETURNING id")),
    "teamflow_events": ("teamflow_items", ("INSERT INTO teamflow_events (event_type, owner_agent, public_id, item_id) "
                                           "VALUES ('created', 'ZEUS', 'te'||:k, :p) RETURNING id")),
}


def _k():
    return uuid.uuid4().hex[:10]


@pytest.fixture(scope="module")
def pg():
    if not PG_URL:
        pytest.skip("ZEUS_TEST_PG_URL no definida: este test necesita un PostgreSQL real migrado a 0071")
    if not PG_URL.startswith("postgresql"):
        pytest.skip(f"ZEUS_TEST_PG_URL no es PostgreSQL: {PG_URL.split('@')[-1]}")
    admin = create_engine(PG_URL, poolclass=NullPool, connect_args={"connect_timeout": 3})
    try:
        with admin.connect() as c:
            if c.execute(text("SELECT to_regprocedure('public.app_ctx_company_ids()')")).scalar() is None:
                pytest.skip("la BD de ZEUS_TEST_PG_URL no tiene la migracion 0071")
            role = c.execute(text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = :r"), {"r": APP_ROLE}).first()
            if role is None:
                pytest.skip(f"no existe el rol de aplicacion {APP_ROLE!r}")
            assert tuple(role) == (False, False), f"{APP_ROLE} no debe ser SUPERUSER ni BYPASSRLS"
    except OperationalError as e:
        admin.dispose()
        pytest.skip(f"PostgreSQL de ZEUS_TEST_PG_URL no responde: {str(e.orig).splitlines()[0]}")

    ids = {"A": {}, "B": {}}
    with admin.begin() as c:
        for side in ("A", "B"):
            k = _k()
            cid = c.execute(text("INSERT INTO companies (company_name, slug, status, currency) VALUES (:n, :s, 'active', 'EUR') "
                                 "RETURNING id"), {"n": f"RLS {side} {k}", "s": f"rls-{side.lower()}-{k}"}).scalar_one()
            uid = c.execute(text("INSERT INTO users (email, hashed_password, is_active) VALUES (:e, 'x', true) RETURNING id"),
                            {"e": f"rls_{side.lower()}_{k}@example.com"}).scalar_one()
            c.execute(text("INSERT INTO user_companies (user_id, company_id, role) VALUES (:u, :c, 'company_admin')"),
                      {"u": uid, "c": cid})
            ids[side].update(company=cid, user=uid, email=f"rls_{side.lower()}_{k}@example.com", slug=f"rls-{side.lower()}-{k}")
            for t, sql in SEED.items():
                ids[side][t] = [c.execute(text(sql), {"c": cid, "u": uid, "k": _k()}).scalar_one()]
            for t, (parent, sql) in CHILD_SEED.items():
                ids[side][t] = [c.execute(text(sql), {"p": ids[side][parent][0], "k": _k()}).scalar_one()]
            # fila SIN empresa con dueno (patron legacy): solo la ve su dueno
            ids[side]["document_approvals_null"] = c.execute(text(
                "INSERT INTO document_approvals (user_id, agent_name, document_type, document_payload_json, company_id) "
                "VALUES (:u, 'RAFAEL', 'informe', '{}', NULL) RETURNING id"), {"u": uid}).scalar_one()
    app_eng = create_engine(PG_URL, poolclass=NullPool, connect_args={"connect_timeout": 3, "options": f"-c role={APP_ROLE}"})
    try:
        yield admin, app_eng, ids
    finally:
        app_eng.dispose()
        with admin.begin() as c:
            for side in ("A", "B"):
                for t in CHILD_SEED:
                    c.execute(text(f"DELETE FROM {t} WHERE id = ANY(:i)"), {"i": ids[side][t]})
                for t in SEED:
                    c.execute(text(f"DELETE FROM {t} WHERE id = ANY(:i)"), {"i": ids[side][t]})
                c.execute(text("DELETE FROM document_approvals WHERE id = :i"), {"i": ids[side]["document_approvals_null"]})
                c.execute(text("DELETE FROM user_companies WHERE user_id = :u"), {"u": ids[side]["user"]})
                c.execute(text("DELETE FROM users WHERE id = :u"), {"u": ids[side]["user"]})
                c.execute(text("DELETE FROM companies WHERE id = :c"), {"c": ids[side]["company"]})
        admin.dispose()


TABLES = list(SEED) + list(CHILD_SEED)


def _seen(db, ids):
    """{tabla: (filas de A visibles, filas de B visibles)} solo sobre lo sembrado."""
    out = {}
    for t in TABLES:
        a = db.execute(text(f"SELECT count(*) FROM {t} WHERE id = ANY(:i)"), {"i": ids["A"][t]}).scalar()
        b = db.execute(text(f"SELECT count(*) FROM {t} WHERE id = ANY(:i)"), {"i": ids["B"][t]}).scalar()
        out[t] = (a, b)
    return out


def test_role_is_app_role(pg):
    _, app_eng, _ = pg
    with app_eng.connect() as c:
        assert c.execute(text("SELECT current_user")).scalar() == APP_ROLE


def test_no_context_sees_nothing(pg):
    _, app_eng, ids = pg
    with Session(app_eng) as db:
        assert _seen(db, ids) == {t: (0, 0) for t in TABLES}
        assert db.execute(text("SELECT count(*) FROM companies")).scalar() == 0
        assert db.execute(text("SELECT count(*) FROM users")).scalar() == 0


def test_company_a_sees_only_a_first_query_commit_rollback_write(pg):
    _, app_eng, ids = pg
    want = {t: (1, 0) for t in TABLES}
    with Session(app_eng) as db:
        rc.set_tenant_context(db, ids["A"]["company"], user_id=ids["A"]["user"], user_email=ids["A"]["email"])
        assert _seen(db, ids) == want                                  # primera consulta
        db.commit()
        assert _seen(db, ids) == want                                  # tras commit
        with pytest.raises(DBAPIError):
            db.execute(text("SELECT 1/0"))
        db.rollback()
        assert _seen(db, ids) == want                                  # tras error + rollback
        db.execute(text("UPDATE customers SET name = name || '.' WHERE id = ANY(:i)"), {"i": ids["A"]["customers"]})
        db.commit()
        assert _seen(db, ids) == want                                  # tras escribir
        assert db.execute(text("SELECT count(*) FROM companies")).scalar() == 1
        assert db.execute(text("SELECT id FROM companies")).scalar() == ids["A"]["company"]
        assert set(db.execute(text("SELECT id FROM users WHERE id = ANY(:i)"),
                              {"i": [ids["A"]["user"], ids["B"]["user"]]}).scalars()) == {ids["A"]["user"]}
        assert db.execute(text("SELECT count(*) FROM user_companies WHERE user_id = :u"), {"u": ids["B"]["user"]}).scalar() == 0


@pytest.mark.parametrize("stmt", [
    "INSERT INTO customers (name, company_id) VALUES ('hack', :b)",
    "INSERT INTO crm_leads (name, company_id) VALUES ('hack', :b)",
    "INSERT INTO expenses (supplier_name, company_id, issue_date) VALUES ('hack', :b, now())",
    "INSERT INTO scan_events (company_id, scan_type, raw_payload) VALUES (:b, 'qr', 'x')",
    "INSERT INTO user_companies (user_id, company_id, role) VALUES (:ua, :b, 'company_admin')",
    "INSERT INTO invoice_items (invoice_id, description, unit_price) VALUES (:binv, 'hack', 1)",
    "INSERT INTO payments (invoice_id, amount, payment_method) VALUES (:binv, 1, 'cash')",
    "UPDATE customers SET company_id = :b WHERE id = :acust",
    "UPDATE invoices SET company_id = :b WHERE id = :ainv",
])
def test_write_into_company_b_with_context_a_is_rejected(pg, stmt):
    _, app_eng, ids = pg
    params = {"b": ids["B"]["company"], "ua": ids["A"]["user"], "binv": ids["B"]["invoices"][0],
              "acust": ids["A"]["customers"][0], "ainv": ids["A"]["invoices"][0]}
    with Session(app_eng) as db:
        rc.set_tenant_context(db, ids["A"]["company"], user_id=ids["A"]["user"])
        with pytest.raises(DBAPIError, match="row-level security"):
            db.execute(text(stmt), {k: v for k, v in params.items() if f":{k}" in stmt})
        db.rollback()


def test_updates_on_b_rows_affect_nothing(pg):
    _, app_eng, ids = pg
    with Session(app_eng) as db:
        rc.set_tenant_context(db, ids["A"]["company"], user_id=ids["A"]["user"])
        for t in TABLES:
            n = db.execute(text(f"UPDATE {t} SET id = id WHERE id = ANY(:i)"), {"i": ids["B"][t]}).rowcount
            assert n == 0, t
            n = db.execute(text(f"DELETE FROM {t} WHERE id = ANY(:i)"), {"i": ids["B"][t]}).rowcount
            assert n == 0, t
        db.rollback()


def test_rows_without_company_only_for_their_owner(pg):
    _, app_eng, ids = pg
    da, db_ = ids["A"]["document_approvals_null"], ids["B"]["document_approvals_null"]
    q = text("SELECT id FROM document_approvals WHERE id = ANY(:i)")
    with Session(app_eng) as db:
        rc.set_tenant_context(db, ids["A"]["company"], user_id=ids["A"]["user"])
        assert set(db.execute(q, {"i": [da, db_]}).scalars()) == {da}
        rc.set_tenant_context(db, ids["A"]["company"])           # empresa sin usuario: no ve filas sin empresa
        assert list(db.execute(q, {"i": [da, db_]}).scalars()) == []


def test_system_mode_sees_everything(pg):
    _, app_eng, ids = pg
    with Session(app_eng) as db:
        rc.set_system_context(db, "test_rls_fail_closed_pg_v1")
        assert _seen(db, ids) == {t: (1, 1) for t in TABLES}


def test_bounded_lookups_return_only_ids_without_context(pg):
    _, app_eng, ids = pg
    with Session(app_eng) as db:
        assert rc.lookup_user_id_by_email(db, ids["A"]["email"].upper()) == ids["A"]["user"]
        assert rc.lookup_user_id_by_email(db, "nadie-" + _k() + "@example.com") is None
        assert rc.company_slug_taken(db, ids["B"]["slug"]) is True
        assert db.execute(text("SELECT count(*) FROM users")).scalar() == 0  # el lookup no abre la tabla


def test_garbage_context_sees_nothing_without_error(pg):
    _, app_eng, ids = pg
    with Session(app_eng) as db:
        db.execute(text("SELECT set_config('app.current_company_ids', '1,abc', true), "
                        "set_config('app.current_company_id', 'x;drop', true), set_config('app.rls_mode', 'System', true)"))
        assert _seen(db, ids) == {t: (0, 0) for t in TABLES}


def test_guard_every_company_table_has_forced_rls_and_a_policy(pg):
    """Guardia contra tablas nuevas fail-open: TODA tabla de public con columna company_id debe tener
    ENABLE + FORCE ROW LEVEL SECURITY y al menos una policy. Una tabla nueva con datos de empresa que se
    cree sin su policy hace fallar este test (y la migracion que la crea debe anadirla)."""
    admin, _, _ = pg
    with admin.connect() as c:
        rows = c.execute(text(
            "SELECT cl.relname, cl.relrowsecurity, cl.relforcerowsecurity, "
            "       (SELECT count(*) FROM pg_policy p WHERE p.polrelid = cl.oid) "
            "FROM pg_class cl JOIN pg_attribute a ON a.attrelid = cl.oid AND a.attname = 'company_id' "
            "AND NOT a.attisdropped "
            "WHERE cl.relkind IN ('r', 'p') AND cl.relnamespace = 'public'::regnamespace ORDER BY 1")).all()
    assert rows, "no hay tablas con company_id: BD inesperada"
    missing = [(t, bool(e), bool(f), int(n)) for t, e, f, n in rows if not (e and f and n > 0)]
    assert missing == [], f"tablas con company_id sin ENABLE+FORCE RLS o sin policy: {missing}"
