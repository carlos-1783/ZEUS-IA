"""Numeracion de facturas INV-YYYYMMDD-N correlativa POR EMPRESA (services/invoice_numbering_v1, migracion 0070).

Antes N era global (max de todas las empresas + 1, leyendo saltandose la RLS) y el UNIQUE de invoice_number era
global. Ahora cada empresa tiene su contador en invoice_counters y el numero es unico por empresa. Aqui (SQLite)
se fija el contrato: contador por empresa, sin contar filas, rollback sin consumir numero, mismo numero
permitido en empresas distintas y la API y el escaneo QR comparten serie. La concurrencia REAL y la RLS se
prueban contra Postgres en test_invoice_numbering_pg_concurrencia_v1.py.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.db.base import SessionLocal
from app.main import app
from app.models.company import UserCompany
from app.models.user import User
from services.invoice_numbering_v1 import next_invoice_number

pytestmark = pytest.mark.usefixtures("no_external_messaging")
API = settings.API_V1_STR
FMT = re.compile(r"^INV-(\d{8})-([1-9]\d*)$")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _register(client):
    suf = uuid.uuid4().hex[:10]
    payload = {"email": f"invnum_{suf}@example.com", "password": "TestPass1", "full_name": "Titular Numeracion",
               "phone": "612345678", "company_name": f"Empresa Num {suf}", "business_type": "restaurant"}
    r = client.post(f"{API}/auth/register", json=payload)
    if r.status_code != 201:
        pytest.skip(f"Registro no disponible: {r.status_code}")
    login = client.post(f"{API}/auth/login", data={"username": payload["email"], "password": payload["password"]})
    assert login.status_code == 200, login.text
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.email == payload["email"]).one()
        cid = db.query(UserCompany).filter(UserCompany.user_id == u.id).order_by(UserCompany.id).first().company_id
    finally:
        db.close()
    return {"Authorization": f"Bearer {login.json()['access_token']}"}, u.id, cid


@pytest.fixture(scope="module")
def user(client):
    return _register(client)


@pytest.fixture(scope="module")
def other_user(client):
    return _register(client)


def _reserve(cid, *, commit=False):
    db = SessionLocal()
    try:
        number = next_invoice_number(db, cid, now=datetime(2026, 10, 25, 13, 0))
        if commit:
            db.commit()
        return number
    finally:
        db.rollback()
        db.close()


def _n(number):
    m = FMT.match(number)
    assert m, number
    return int(m.group(2))


def _counter(cid):
    db = SessionLocal()
    try:
        return db.execute(text("SELECT last_number FROM invoice_counters WHERE company_id = :c AND series = 'INV'"),
                          {"c": cid}).scalar()
    finally:
        db.close()


def test_company_id_is_required():
    db = SessionLocal()
    try:
        with pytest.raises(ValueError):
            next_invoice_number(db, None)
    finally:
        db.close()


def test_counter_per_company_and_rollback_does_not_consume(client, user, other_user):
    _, _, a = user
    _, _, b = other_user
    first_a = _n(_reserve(a, commit=True))
    assert _reserve(a) == f"INV-20261025-{first_a + 1}"         # sin commit -> rollback
    assert _reserve(a) == f"INV-20261025-{first_a + 1}"         # el numero no se consumio
    assert _counter(a) == first_a
    # Otra empresa lleva su propia serie: no se ve afectada por los numeros de A.
    first_b = _n(_reserve(b, commit=True))
    assert _n(_reserve(b, commit=True)) == first_b + 1
    assert _counter(a) == first_a


def test_counter_does_not_count_rows(client, user):
    """Filas existentes (otras series, numeros sueltos) no cambian N: manda el contador."""
    _, uid, cid = user
    base = _counter(cid) or 0
    db = SessionLocal()
    try:
        for num in (f"FRA-TICKET_{uuid.uuid4().hex[:12]}", f"INV-20200101-{base + 900}", "INV-XXXXXXXX-abc"):
            db.execute(text("INSERT INTO invoices (invoice_number, company_id) VALUES (:n, :c)"), {"n": num, "c": cid})
        db.commit()
    finally:
        db.close()
    assert _reserve(cid) == f"INV-20261025-{base + 1}"


def test_same_number_allowed_in_two_companies_but_unique_within_one(client, user, other_user):
    _, _, a = user
    _, _, b = other_user
    num = f"INV-20261025-{uuid.uuid4().int % 10 ** 8 + 10 ** 8}"
    db = SessionLocal()
    try:
        db.execute(text("INSERT INTO invoices (invoice_number, company_id) VALUES (:n, :c)"), {"n": num, "c": a})
        db.execute(text("INSERT INTO invoices (invoice_number, company_id) VALUES (:n, :c)"), {"n": num, "c": b})
        db.commit()
        with pytest.raises(IntegrityError):
            db.execute(text("INSERT INTO invoices (invoice_number, company_id) VALUES (:n, :c)"), {"n": num, "c": a})
            db.flush()
        db.rollback()
    finally:
        db.close()


def test_api_and_scan_flow_use_the_same_series(client, user):
    h, uid, cid = user
    c = client.post(f"{API}/customers", headers=h, json={"name": "Cliente Num", "email": f"cl_{uuid.uuid4().hex[:8]}@example.com"})
    assert c.status_code == 201, c.text
    cust = c.json()["data"]["id"]
    base = _counter(cid) or 0

    nums = []
    for _ in range(2):
        r = client.post(f"{API}/invoices/", headers=h, json={
            "customer_id": cust, "invoice_type": "invoice", "status": "draft", "issue_date": "2026-10-20",
            "items": [{"description": "Servicio", "quantity": 1, "unit_price": 10.0, "tax_rate": 21.0}]})
        assert r.status_code == 201, r.text
        nums.append(r.json()["data"]["invoice_number"])

    from services.scan_flow_service_v1 import _create_invoice_draft
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.id == uid).one()
        inv = _create_invoice_draft(db, u, company_id=cid, customer_id=cust, amount=12.1, description="QR")
        db.commit()
        nums.append(inv.invoice_number)
    finally:
        db.close()

    today = datetime.utcnow().strftime("%Y%m%d")
    assert [FMT.match(n).group(1) for n in nums] == [today] * 3
    assert [_n(n) for n in nums] == [base + 1, base + 2, base + 3]
    assert _counter(cid) == base + 3
