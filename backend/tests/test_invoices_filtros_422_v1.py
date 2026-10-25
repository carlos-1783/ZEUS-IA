"""GET /invoices/?status=... / ?invoice_type=...: un valor fuera del enum (en ingles) da 422, no 500.

Antes el filtro llegaba como `str` a la consulta: en PostgreSQL el literal no valido del tipo ENUM revienta
(DataError: invalid input value for enum) y el listado daba 500. Ahora se valida contra los valores del Enum
ANTES de consultar facturas y se responde 422 con la lista de valores validos. Para los valores validos el
contrato no cambia (y `?status=` vacio sigue sin filtrar).
Login real (register + /auth/login, Bearer) y TestClient sobre la app real.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.base import SessionLocal
from app.main import app
from app.models.company import UserCompany
from app.models.erp import Invoice, InvoiceStatus, InvoiceType
from app.models.user import User

pytestmark = pytest.mark.usefixtures("no_external_messaging")
API = settings.API_V1_STR


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _register_login(client):
    suf = uuid.uuid4().hex[:10]
    payload = {"email": f"invfil_{suf}@example.com", "password": "TestPass1", "full_name": "Titular Filtros",
               "phone": "612345678", "company_name": f"Empresa Filtros {suf}", "business_type": "restaurant"}
    r = client.post(f"{API}/auth/register", json=payload)
    if r.status_code != 201:
        pytest.skip(f"Registro no disponible: {r.status_code}")
    login = client.post(f"{API}/auth/login", data={"username": payload["email"], "password": payload["password"]})
    assert login.status_code == 200, login.text
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == payload["email"]).one()
        uc = db.query(UserCompany).filter(UserCompany.user_id == user.id).order_by(UserCompany.id.asc()).first()
        return {"Authorization": f"Bearer {login.json()['access_token']}"}, uc.company_id
    finally:
        db.close()


def _inv(cid, status, itype=InvoiceType.INVOICE):
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        inv = Invoice(invoice_number=f"F-{uuid.uuid4().hex[:10]}", company_id=cid, invoice_type=itype,
                      status=status, issue_date=now, due_date=now + timedelta(days=30), subtotal=10.0,
                      tax_amount=2.1, discount_amount=0.0, total=12.1, amount_paid=0.0, amount_due=12.1)
        db.add(inv)
        db.commit()
        return inv.id
    finally:
        db.close()


@pytest.fixture(scope="module")
def seeded(client):
    """Un titular y 4 facturas por modulo (/auth/register tiene limite de 10/min por IP)."""
    h, cid = _register_login(client)
    ids = {
        "paid": _inv(cid, InvoiceStatus.PAID),
        "draft": _inv(cid, InvoiceStatus.DRAFT),
        "sent": _inv(cid, InvoiceStatus.SENT),
        "proforma": _inv(cid, InvoiceStatus.DRAFT, InvoiceType.PROFORMA),
    }
    return h, ids


def _get(client, h, q):
    return client.get(f"{API}/invoices/{q}", headers=h)


@pytest.mark.parametrize("q,param", [
    ("?status=basura", "status"),
    ("?status=PAID", "status"),  # el contrato es en minusculas (valor del enum, en ingles)
    ("?status=pagada", "status"),
    ("?invoice_type=basura", "invoice_type"),
    ("?invoice_type=factura", "invoice_type"),
])
def test_invalid_enum_filter_is_422_with_valid_values(client, seeded, q, param):
    h, _ = seeded
    r = _get(client, h, q)
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert param in detail
    enum_cls = InvoiceStatus if param == "status" else InvoiceType
    for e in enum_cls:
        assert e.value in detail, (e.value, detail)


def test_status_paid_returns_only_paid(client, seeded):
    h, ids = seeded
    r = _get(client, h, "?status=paid")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert [d["id"] for d in data] == [ids["paid"]]
    assert r.json()["total"] == 1
    assert all(d["status"] == "paid" for d in data)


def test_status_draft_returns_only_drafts(client, seeded):
    h, ids = seeded
    r = _get(client, h, "?status=draft")
    assert r.status_code == 200, r.text
    assert {d["id"] for d in r.json()["data"]} == {ids["draft"], ids["proforma"]}


def test_invoice_type_invoice_and_proforma(client, seeded):
    h, ids = seeded
    r = _get(client, h, "?invoice_type=invoice")
    assert r.status_code == 200, r.text
    assert {d["id"] for d in r.json()["data"]} == {ids["paid"], ids["draft"], ids["sent"]}
    r = _get(client, h, "?invoice_type=proforma&status=draft")
    assert r.status_code == 200, r.text
    assert [d["id"] for d in r.json()["data"]] == [ids["proforma"]]


def test_empty_filter_still_means_no_filter(client, seeded):
    h, ids = seeded
    r = _get(client, h, "?status=&invoice_type=")
    assert r.status_code == 200, r.text
    assert {d["id"] for d in r.json()["data"]} == set(ids.values())


def test_invalid_filter_without_token_is_401(client):
    assert client.get(f"{API}/invoices/?status=basura").status_code == 401
