"""GET /invoices/{id}/payments: lista los pagos reales de la factura (antes 500 SIEMPRE).

list_invoice_payments cargaba la factura con get_invoice_or_404, que devuelve InvoiceInDB (Pydantic, sin
`.payments`): `invoice.payments` lanzaba AttributeError -> 500 en el 100 % de las llamadas. Ahora usa la
entidad ORM con el mismo filtro de tenant que /send y /void (get_invoice_orm_or_404).
Login real (register + /auth/login, Bearer) y TestClient sobre la app real; pagos creados por POST /payments.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import settings
from app.db.base import SessionLocal
from app.main import app
from app.models.user import User

pytestmark = pytest.mark.usefixtures("no_external_messaging")
API = settings.API_V1_STR


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _register_login(client):
    suf = uuid.uuid4().hex[:10]
    payload = {"email": f"invpay_{suf}@example.com", "password": "TestPass1", "full_name": "Titular Pagos",
               "phone": "612345678", "company_name": f"Empresa Pagos {suf}", "business_type": "restaurant"}
    r = client.post(f"{API}/auth/register", json=payload)
    if r.status_code != 201:
        pytest.skip(f"Registro no disponible: {r.status_code}")
    login = client.post(f"{API}/auth/login", data={"username": payload["email"], "password": payload["password"]})
    assert login.status_code == 200, login.text
    db = SessionLocal()
    try:
        uid = db.query(User).filter(User.email == payload["email"]).one().id
    finally:
        db.close()
    return {"Authorization": f"Bearer {login.json()['access_token']}"}, uid


def _create_invoice(client, h) -> int:
    c = client.post(f"{API}/customers", headers=h,
                    json={"name": "Cliente Pagos", "email": f"cl_{uuid.uuid4().hex[:8]}@example.com"})
    assert c.status_code == 201, c.text
    r = client.post(f"{API}/invoices/", headers=h, json={
        "customer_id": c.json()["data"]["id"], "invoice_type": "invoice", "status": "draft", "issue_date": "2026-10-20",
        "items": [{"description": "Servicio", "quantity": 1, "unit_price": 100.0, "tax_rate": 21.0}]})
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


@pytest.fixture(scope="module")
def user_a(client):
    """Titulares por modulo (no por test): /auth/register tiene limite de 10/min por IP."""
    return _register_login(client)


@pytest.fixture(scope="module")
def user_b(client):
    return _register_login(client)


def test_payments_empty_list(client, user_a):
    h, _ = user_a
    inv = _create_invoice(client, h)
    r = client.get(f"{API}/invoices/{inv}/payments", headers=h)
    assert r.status_code == 200, r.text
    assert r.json() == []


def test_payments_lists_real_payments(client, user_a):
    h, uid = user_a
    inv = _create_invoice(client, h)  # total 121
    created = []
    for amount, method in ((21.0, "cash"), (100.0, "bank_transfer")):
        r = client.post(f"{API}/invoices/{inv}/payments", headers=h,
                        json={"amount": amount, "payment_method": method, "status": "completed"})
        assert r.status_code == 201, r.text
        created.append(r.json()["data"]["id"])

    r = client.get(f"{API}/invoices/{inv}/payments", headers=h)
    assert r.status_code == 200, r.text
    got = r.json()
    assert [p["id"] for p in got] == created
    assert [(p["amount"], p["payment_method"], p["status"]) for p in got] == [
        (21.0, "cash", "completed"), (100.0, "bank_transfer", "completed")]
    assert all(p["invoice_id"] == inv and p["created_by"] == uid for p in got)
    # Coherente con lo que hay en BD (no un valor fijo).
    db = SessionLocal()
    try:
        n = db.execute(text("SELECT count(*) FROM payments WHERE invoice_id = :i"), {"i": inv}).scalar_one()
    finally:
        db.close()
    assert n == 2


def test_payments_other_company_is_404(client, user_a, user_b):
    h_a, _ = user_a
    h_b, _ = user_b
    inv = _create_invoice(client, h_a)
    r = client.post(f"{API}/invoices/{inv}/payments", headers=h_a,
                    json={"amount": 10.0, "payment_method": "cash", "status": "completed"})
    assert r.status_code == 201, r.text
    r = client.get(f"{API}/invoices/{inv}/payments", headers=h_b)
    assert r.status_code == 404, r.text
    assert "10.0" not in r.text


def test_payments_legacy_invoice_of_other_user_is_404(client, user_a, user_b):
    """Factura sin empresa (legacy) creada por A: solo A la ve; B -> 404."""
    h_a, uid_a = user_a
    h_b, _ = user_b
    num = f"LEG-{uuid.uuid4().hex[:10]}"
    db = SessionLocal()
    try:
        db.execute(text("INSERT INTO invoices (invoice_number, company_id, created_by) VALUES (:n, NULL, :u)"),
                   {"n": num, "u": uid_a})
        db.commit()
        inv = db.execute(text("SELECT id FROM invoices WHERE invoice_number = :n"), {"n": num}).scalar_one()
    finally:
        db.close()
    assert client.get(f"{API}/invoices/{inv}/payments", headers=h_a).status_code == 200
    assert client.get(f"{API}/invoices/{inv}/payments", headers=h_b).status_code == 404


def test_payments_missing_invoice_is_404(client, user_a):
    h, _ = user_a
    assert client.get(f"{API}/invoices/999999999/payments", headers=h).status_code == 404


def test_payments_without_token_is_401(client, user_a):
    h, _ = user_a
    inv = _create_invoice(client, h)
    r = client.get(f"{API}/invoices/{inv}/payments")
    assert r.status_code == 401, r.text
