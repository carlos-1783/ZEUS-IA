"""PUT /invoices/{id}: el vencimiento no puede quedar antes de la emision, y si se rechaza no se guarda nada.

Antes update_invoice asignaba cada campo segun lo leia y hacia commit sin comparar due_date con issue_date:
se podia guardar un vencimiento anterior a la emision (la regla de create no se aplicaba en la edicion).
Se fija:
  1. due_date < issue_date (issue_date de la fila) -> 422 y la fila de BD NO cambia (ni due_date ni notes ni
     customer_id que vinieran en el mismo PUT).
  2. Regla por DIA, como create: el mismo dia de emision es valido aunque la factura tenga hora (TPV 12:30).
  3. Casos validos siguen funcionando (posterior, null para quitarlo, notes sola) y se persisten.
  4. Factura legacy sin issue_date: no hay contra que comparar -> se acepta (no se inventa una fecha).
  5. due_date con formato o tipo invalido -> 422 sin guardar.
Login real (register + /auth/login, Bearer) y TestClient sobre la app real.
"""
from __future__ import annotations

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

pytestmark = pytest.mark.usefixtures("no_external_messaging")
API = settings.API_V1_STR


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def user(client):
    suf = uuid.uuid4().hex[:10]
    payload = {"email": f"invdue_{suf}@example.com", "password": "TestPass1", "full_name": "Titular Vencimiento",
               "phone": "612345678", "company_name": f"Empresa Venc {suf}", "business_type": "restaurant"}
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
def customers(client, user):
    h, _, _ = user
    out = []
    for n in ("Cliente Venc A", "Cliente Venc B"):
        r = client.post(f"{API}/customers", headers=h, json={"name": n, "email": f"cl_{uuid.uuid4().hex[:8]}@example.com"})
        assert r.status_code == 201, r.text
        out.append(r.json()["data"]["id"])
    return out


def _create(client, h, customer_id, **over):
    body = {"customer_id": customer_id, "invoice_type": "invoice", "status": "draft", "issue_date": "2026-10-20",
            "due_date": "2026-11-20", "notes": "original",
            "items": [{"description": "Servicio", "quantity": 1, "unit_price": 10.0, "tax_rate": 21.0}]}
    body.update(over)
    r = client.post(f"{API}/invoices/", headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


def _row(inv):
    db = SessionLocal()
    try:
        return db.execute(text("SELECT issue_date, due_date, notes, customer_id, updated_at FROM invoices WHERE id = :i"),
                          {"i": inv}).one()
    finally:
        db.close()


def _day(v):
    return str(v)[:10]


def test_due_before_issue_is_422_and_nothing_is_saved(client, user, customers):
    h, _, _ = user
    inv = _create(client, h, customers[0])
    before = _row(inv)
    r = client.put(f"{API}/invoices/{inv}", headers=h,
                   json={"due_date": "2026-10-19", "notes": "no debe guardarse", "customer_id": customers[1]})
    assert r.status_code == 422, r.text
    assert "Due date cannot be before issue date" in r.text
    assert _row(inv) == before  # ni due_date, ni notes, ni customer_id, ni updated_at
    assert _day(before.due_date) == "2026-11-20" and before.notes == "original"


def test_due_before_issue_with_time_is_422(client, user, customers):
    h, _, _ = user
    inv = _create(client, h, customers[0])
    before = _row(inv)
    r = client.put(f"{API}/invoices/{inv}", headers=h, json={"due_date": "2026-10-19T23:59:59"})
    assert r.status_code == 422, r.text
    assert _row(inv) == before


def test_same_day_is_valid_even_if_issued_with_time(client, user, customers):
    """Factura con hora (como las del TPV, issue_date = utcnow): vencer ese mismo dia es valido."""
    h, _, _ = user
    inv = _create(client, h, customers[0])
    db = SessionLocal()
    try:
        db.execute(text("UPDATE invoices SET issue_date = :d WHERE id = :i"), {"d": datetime(2026, 10, 20, 12, 30), "i": inv})
        db.commit()
    finally:
        db.close()
    r = client.put(f"{API}/invoices/{inv}", headers=h, json={"due_date": "2026-10-20"})
    assert r.status_code == 200, r.text
    assert _day(r.json()["data"]["due_date"]) == "2026-10-20"
    assert _day(_row(inv).due_date) == "2026-10-20"
    # y el dia anterior sigue rechazado
    assert client.put(f"{API}/invoices/{inv}", headers=h, json={"due_date": "2026-10-19"}).status_code == 422
    assert _day(_row(inv).due_date) == "2026-10-20"


def test_valid_updates_still_work(client, user, customers):
    h, _, _ = user
    inv = _create(client, h, customers[0])
    r = client.put(f"{API}/invoices/{inv}", headers=h,
                   json={"due_date": "2026-12-31", "notes": "nueva", "customer_id": customers[1]})
    assert r.status_code == 200, r.text
    row = _row(inv)
    assert (_day(row.due_date), row.notes, row.customer_id) == ("2026-12-31", "nueva", customers[1])
    r = client.put(f"{API}/invoices/{inv}", headers=h, json={"notes": "solo nota"})
    assert r.status_code == 200, r.text
    assert _day(_row(inv).due_date) == "2026-12-31" and _row(inv).notes == "solo nota"
    r = client.put(f"{API}/invoices/{inv}", headers=h, json={"due_date": None})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["due_date"] is None and _row(inv).due_date is None


def test_legacy_invoice_without_issue_date_accepts_due_date(client, user):
    h, uid, cid = user
    num = f"LEG-{uuid.uuid4().hex[:10]}"
    db = SessionLocal()
    try:
        db.execute(text("INSERT INTO invoices (invoice_number, company_id, created_by) VALUES (:n, :c, :u)"),
                   {"n": num, "c": cid, "u": uid})
        db.commit()
        inv = db.execute(text("SELECT id FROM invoices WHERE invoice_number = :n"), {"n": num}).scalar_one()
    finally:
        db.close()
    r = client.put(f"{API}/invoices/{inv}", headers=h, json={"due_date": "2020-01-01"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["issue_date"] is None and _day(_row(inv).due_date) == "2020-01-01"


@pytest.mark.parametrize("bad", ["no-es-fecha", "2026-13-01", 20261020, ["2026-10-20"]])
def test_invalid_due_date_is_422_without_saving(client, user, customers, bad):
    h, _, _ = user
    inv = _create(client, h, customers[0])
    before = _row(inv)
    r = client.put(f"{API}/invoices/{inv}", headers=h, json={"due_date": bad, "notes": "x"})
    assert r.status_code == 422, r.text
    assert _row(inv) == before


def test_status_still_400(client, user, customers):
    h, _, _ = user
    inv = _create(client, h, customers[0])
    assert client.put(f"{API}/invoices/{inv}", headers=h, json={"status": "paid"}).status_code == 400
