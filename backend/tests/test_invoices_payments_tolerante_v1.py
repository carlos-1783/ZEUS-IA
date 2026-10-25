"""GET /invoices/{id}/payments y POST /payments: la RESPUESTA aguanta pagos antiguos con NULLs.

PaymentInDB heredaba de PaymentBase (ENTRADA: amount gt=0, status/payment_date obligatorios,
transaction_id max_length=100). En BD status, payment_date y created_at admiten NULL: un solo pago antiguo
con NULL o con importe 0 hacia fallar la serializacion y la lista de pagos de la factura daba 500.
Se fija:
  1. Pago antiguo (INSERT por SQL) con NULLs, amount 0 y transaction_id de 100 caracteres -> 200 y null.
  2. POST /payments sigue creando y devolviendo el pago real.
  3. La ENTRADA (PaymentCreate) sigue rechazando amount 0 / negativo, metodo invalido y transaction_id > 100.
  4. Otra empresa sigue sin ver los pagos (404).
Login real (register + /auth/login, Bearer) y TestClient sobre la app real.
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
    payload = {"email": f"paytol_{suf}@example.com", "password": "TestPass1", "full_name": "Titular Pagos Tol",
               "phone": "612345678", "company_name": f"Empresa PagosTol {suf}", "business_type": "restaurant"}
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


@pytest.fixture(scope="module")
def user_a(client):
    return _register_login(client)


@pytest.fixture(scope="module")
def user_b(client):
    return _register_login(client)


@pytest.fixture(scope="module")
def invoice_id(client, user_a):
    h, _ = user_a
    c = client.post(f"{API}/customers", headers=h,
                    json={"name": "Cliente PagosTol", "email": f"cl_{uuid.uuid4().hex[:8]}@example.com"})
    assert c.status_code == 201, c.text
    r = client.post(f"{API}/invoices/", headers=h, json={
        "customer_id": c.json()["data"]["id"], "invoice_type": "invoice", "status": "draft", "issue_date": "2026-10-20",
        "items": [{"description": "Servicio", "quantity": 1, "unit_price": 100.0, "tax_rate": 21.0}]})
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


@pytest.fixture(scope="module")
def legacy_payment(invoice_id):
    """Pago antiguo: solo factura, importe 0, metodo y transaction_id largo; status/fechas/autor NULL."""
    db = SessionLocal()
    try:
        db.execute(text("INSERT INTO payments (invoice_id, amount, payment_method, transaction_id) "
                        "VALUES (:i, 0, 'cash', :t)"), {"i": invoice_id, "t": "T" * 100})
        db.commit()
        return db.execute(text("SELECT max(id) FROM payments WHERE invoice_id = :i"), {"i": invoice_id}).scalar_one()
    finally:
        db.close()


def test_legacy_payment_with_nulls_is_listed(client, user_a, invoice_id, legacy_payment):
    h, _ = user_a
    r = client.get(f"{API}/invoices/{invoice_id}/payments", headers=h)
    assert r.status_code == 200, r.text
    p = {x["id"]: x for x in r.json()}[legacy_payment]
    assert p["amount"] == 0.0 and p["payment_method"] == "cash" and p["transaction_id"] == "T" * 100
    for k in ("status", "payment_date", "created_at", "created_by", "reference", "notes"):
        assert p[k] is None, (k, p[k])


def test_post_payment_still_works_and_is_listed(client, user_a, invoice_id, legacy_payment):
    h, uid = user_a
    r = client.post(f"{API}/invoices/{invoice_id}/payments", headers=h,
                    json={"amount": 21.0, "payment_method": "bank_transfer", "status": "completed",
                          "transaction_id": "TX-1"})
    assert r.status_code == 201, r.text
    d = r.json()["data"]
    assert (d["amount"], d["payment_method"], d["status"], d["transaction_id"], d["created_by"]) == (
        21.0, "bank_transfer", "completed", "TX-1", uid)
    assert d["payment_date"] is not None and d["created_at"] is not None
    listed = client.get(f"{API}/invoices/{invoice_id}/payments", headers=h).json()
    assert [x["id"] for x in listed] == sorted([legacy_payment, d["id"]])


@pytest.mark.parametrize("over,field", [
    ({"amount": 0}, "amount"),
    ({"amount": -5}, "amount"),
    ({"payment_method": "bitcoin"}, "payment_method"),
    ({"transaction_id": "X" * 101}, "transaction_id"),
    ({"status": "unknown"}, "status"),
])
def test_payment_input_still_strict(client, user_a, invoice_id, over, field):
    h, _ = user_a
    body = {"amount": 1.0, "payment_method": "cash", "status": "completed"}
    body.update(over)
    r = client.post(f"{API}/invoices/{invoice_id}/payments", headers=h, json=body)
    assert r.status_code == 422, r.text
    assert any(field in [str(p) for p in e.get("loc", [])] for e in r.json()["detail"]), r.text


def test_other_company_still_404(client, user_b, invoice_id, legacy_payment):
    h, _ = user_b
    assert client.get(f"{API}/invoices/{invoice_id}/payments", headers=h).status_code == 404


def test_payment_response_does_not_inherit_input_rules():
    from app.schemas.erp import PaymentBase, PaymentCreate, PaymentInDB
    assert not issubclass(PaymentInDB, PaymentBase)
    m = PaymentInDB.model_validate({"id": 1, "invoice_id": 2, "amount": 0.0, "transaction_id": "x" * 300})
    assert m.status is None and m.payment_date is None and m.amount == 0.0
    with pytest.raises(Exception):
        PaymentCreate.model_validate({"amount": 0, "payment_method": "cash"})
