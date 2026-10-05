"""J5d: send/void/update/payments de facturas persisten de verdad (antes mutaban
un objeto pydantic y devolvian 500) y respetan el aislamiento por empresa."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.base import SessionLocal
from app.main import app
from app.models.erp import Invoice, InvoiceStatus

pytestmark = pytest.mark.usefixtures("no_external_messaging")
API = settings.API_V1_STR


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _login(client):
    suf = uuid.uuid4().hex[:10]
    payload = {
        "email": f"invsv_{suf}@example.com", "password": "TestPass1",
        "full_name": "Titular Inv", "phone": "612345678",
        "company_name": f"Empresa Inv {suf}", "business_type": "restaurant",
    }
    r = client.post(f"{API}/auth/register", json=payload)
    if r.status_code != 201:
        pytest.skip(f"Registro no disponible: {r.status_code}")
    login = client.post(f"{API}/auth/login", data={"username": payload["email"], "password": payload["password"]})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _create_invoice(client, h):
    c = client.post(f"{API}/customers", headers=h, json={"name": "Cliente Real Test", "email": f"cli_{uuid.uuid4().hex[:8]}@example.com"})
    assert c.status_code == 201, c.text
    r = client.post(f"{API}/invoices/", headers=h, json={
        "customer_id": c.json()["data"]["id"], "invoice_type": "invoice", "status": "draft", "issue_date": "2026-01-10",
        "items": [{"description": "Servicio", "quantity": 2, "unit_price": 50.0, "tax_rate": 21.0}],
    })
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


def _db_status(inv_id):
    db = SessionLocal()
    try:
        return db.query(Invoice).filter(Invoice.id == inv_id).one().status
    finally:
        db.close()


def test_send_persists_for_owner_and_only_drafts(client):
    h = _login(client)
    inv = _create_invoice(client, h)
    r = client.post(f"{API}/invoices/{inv}/send", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "sent"
    assert _db_status(inv) == InvoiceStatus.SENT
    # segunda vez: ya no es borrador
    assert client.post(f"{API}/invoices/{inv}/send", headers=h).status_code == 400


def test_send_and_void_other_company_404_without_change(client):
    h_a, h_b = _login(client), _login(client)
    inv = _create_invoice(client, h_a)
    assert client.post(f"{API}/invoices/{inv}/send", headers=h_b).status_code == 404
    assert client.post(f"{API}/invoices/{inv}/void", headers=h_b).status_code == 404
    assert client.put(f"{API}/invoices/{inv}", headers=h_b, json={"notes": "x"}).status_code == 404
    assert _db_status(inv) == InvoiceStatus.DRAFT


def test_void_sent_persists_and_double_void_rejected(client):
    h = _login(client)
    inv = _create_invoice(client, h)
    assert client.post(f"{API}/invoices/{inv}/send", headers=h).status_code == 200
    r = client.post(f"{API}/invoices/{inv}/void", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "void"
    assert _db_status(inv) == InvoiceStatus.VOID
    assert client.post(f"{API}/invoices/{inv}/void", headers=h).status_code == 400


def test_void_paid_invoice_rejected_and_unchanged(client):
    h = _login(client)
    inv = _create_invoice(client, h)
    db = SessionLocal()
    try:
        row = db.query(Invoice).filter(Invoice.id == inv).one()
        row.status = InvoiceStatus.PAID
        db.commit()
    finally:
        db.close()
    r = client.post(f"{API}/invoices/{inv}/void", headers=h)
    assert r.status_code == 400
    assert _db_status(inv) == InvoiceStatus.PAID


def test_update_persists_whitelisted_fields_and_ignores_company_id(client):
    h = _login(client)
    inv = _create_invoice(client, h)
    db = SessionLocal()
    try:
        cid_before = db.query(Invoice).filter(Invoice.id == inv).one().company_id
    finally:
        db.close()
    r = client.put(f"{API}/invoices/{inv}", headers=h, json={"notes": "nota real", "company_id": 999999})
    assert r.status_code == 200, r.text
    db = SessionLocal()
    try:
        row = db.query(Invoice).filter(Invoice.id == inv).one()
        assert row.notes == "nota real"
        assert row.company_id == cid_before
    finally:
        db.close()


def test_update_cannot_change_status_via_put(client):
    h = _login(client)
    inv = _create_invoice(client, h)
    for st in ("paid", "void", "bogus"):
        assert client.put(f"{API}/invoices/{inv}", headers=h, json={"status": st}).status_code == 400
    assert _db_status(inv) == InvoiceStatus.DRAFT


def test_update_customer_of_other_company_404_unchanged(client):
    h_a, h_b = _login(client), _login(client)
    inv = _create_invoice(client, h_a)
    other = client.post(f"{API}/customers", headers=h_b, json={"name": "Cliente Ajeno", "email": f"aj_{uuid.uuid4().hex[:8]}@example.com"})
    assert other.status_code == 201, other.text
    db = SessionLocal()
    try:
        before = db.query(Invoice).filter(Invoice.id == inv).one().customer_id
    finally:
        db.close()
    r = client.put(f"{API}/invoices/{inv}", headers=h_a, json={"customer_id": other.json()["data"]["id"]})
    assert r.status_code == 404, r.text
    db = SessionLocal()
    try:
        assert db.query(Invoice).filter(Invoice.id == inv).one().customer_id == before
    finally:
        db.close()


def test_payment_persists_and_marks_paid(client):
    h = _login(client)
    inv = _create_invoice(client, h)  # total 121
    r = client.post(f"{API}/invoices/{inv}/payments", headers=h, json={
        "amount": 121.0, "payment_method": "cash", "status": "completed",
    })
    assert r.status_code == 201, r.text
    assert _db_status(inv) == InvoiceStatus.PAID
