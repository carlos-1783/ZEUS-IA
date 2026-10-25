"""Numeracion de facturas INV-YYYYMMDD-N (services/invoice_numbering_v1): max(N)+1, formato intacto.

Antes POST /invoices/ y el escaneo QR usaban count(*)+1: con huecos (o bajo RLS, o en concurrencia) repetia un
numero ya usado y el UNIQUE global de invoice_number devolvia 500. Aqui (SQLite) se fija el calculo y que ambos
creadores usan el helper; la concurrencia REAL se prueba contra Postgres con el script del scratchpad
(pg_t4_concurrencia.py), porque SQLite no tiene advisory locks ni concurrencia de escritura real.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import settings
from app.db.base import SessionLocal
from app.main import app
from app.models.company import UserCompany
from app.models.user import User
from services.invoice_numbering_v1 import INVOICE_NUMBER_LOCK_KEY, next_invoice_number

pytestmark = pytest.mark.usefixtures("no_external_messaging")
API = settings.API_V1_STR
FMT = re.compile(r"^INV-(\d{8})-([1-9]\d*)$")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def user(client):
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


def _insert_numbers(*numbers):
    db = SessionLocal()
    try:
        for n in numbers:
            db.execute(text("INSERT INTO invoices (invoice_number) VALUES (:n)"), {"n": n})
        db.commit()
    finally:
        db.close()


def _next():
    db = SessionLocal()
    try:
        return next_invoice_number(db, now=datetime(2026, 10, 25, 13, 0))
    finally:
        db.rollback()
        db.close()


def _n(number):
    m = FMT.match(number)
    assert m, number
    return int(m.group(2))


def test_lock_key_is_a_signed_bigint():
    assert -(2 ** 63) <= INVOICE_NUMBER_LOCK_KEY < 2 ** 63


def test_next_is_max_suffix_plus_one_not_count(client):
    base = _n(_next()) - 1
    big = base + 1000
    # Otra serie, sufijos no numericos, ceros a la izquierda y otra fecha: no cuentan / no rompen.
    _insert_numbers(f"INV-20200101-{big}", f"INV-20261024-{big - 5}", f"FRA-TICKET_{uuid.uuid4().hex[:12]}",
                    f"INV-20200101-{big + 7}x", f"INV-2020-{big + 9}", f"INV-20200101-0{big + 11}")
    got = _next()
    assert got == f"INV-20261025-{big + 1}"  # el maximo vale aunque sea de otro dia: N es global


def test_paging_skips_many_malformed_rows(client):
    base = _n(_next()) - 1
    # 205 filas mal formadas MAS largas que cualquier numero valido: ocupan la primera pagina (200).
    _insert_numbers(*[f"INV-XXXXXXXX-{uuid.uuid4().hex}{i:04d}" for i in range(205)])
    assert _next() == f"INV-20261025-{base + 1}"


def test_api_and_scan_flow_use_the_same_series(client, user):
    h, uid, cid = user
    c = client.post(f"{API}/customers", headers=h, json={"name": "Cliente Num", "email": f"cl_{uuid.uuid4().hex[:8]}@example.com"})
    assert c.status_code == 201, c.text
    cust = c.json()["data"]["id"]
    base = _n(_next()) - 1 + 500
    _insert_numbers(f"INV-20200101-{base}")

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
