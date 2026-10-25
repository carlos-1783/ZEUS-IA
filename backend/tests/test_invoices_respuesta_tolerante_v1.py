"""GET /invoices/ y GET /invoices/{id}: la RESPUESTA no aplica reglas de negocio a lo ya guardado.

Antes, InvoiceInDB/InvoiceItemInDB heredaban de los schemas de ENTRADA (unit_price gt=0, quantity gt=0,
tax_rate le=100, description min_length=1, validador due_date >= issue_date, campos obligatorios). Una sola
fila que no cumpliera esas reglas -- p. ej. la linea a 0 EUR que el TPV persiste para una invitacion, o una
fila antigua con NULL -- hacia fallar la serializacion (ResponseValidationError) y GET /invoices/ devolvia
500 para TODA la empresa.

Se fija:
  1. Flujo real del TPV con un producto a 0 EUR -> venta -> POST /tpv/invoice -> la factura aparece en el
     listado y en GET /{id} con 200 y la linea a 0.
  2. Factura antigua con campos opcionales NULL (insertada por SQL) -> 200 y esos campos a null (nunca 0,
     "" ni fechas inventadas).
  3. Factura guardada con due_date < issue_date -> no rompe el listado.
  4. La ENTRADA sigue rechazando lo que debe (unit_price negativo, due_date < issue_date, quantity 0,
     description vacia, tax_rate > 100) y ahora acepta una linea a 0 EUR.
Login real (register + /auth/login, Bearer) y TestClient sobre la app real.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

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


def _register_login(client):
    suf = uuid.uuid4().hex[:10]
    payload = {"email": f"invtol_{suf}@example.com", "password": "TestPass1", "full_name": "Titular Tolerante",
               "phone": "612345678", "company_name": f"Bar Tolerante {suf}", "business_type": "restaurant"}
    r = client.post(f"{API}/auth/register", json=payload)
    if r.status_code != 201:
        pytest.skip(f"Registro no disponible: {r.status_code}")
    login = client.post(f"{API}/auth/login", data={"username": payload["email"], "password": payload["password"]})
    assert login.status_code == 200, login.text
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == payload["email"]).one()
        uc = db.query(UserCompany).filter(UserCompany.user_id == user.id).order_by(UserCompany.id.asc()).first()
        assert uc is not None
        return {"Authorization": f"Bearer {login.json()['access_token']}"}, user.id, uc.company_id
    finally:
        db.close()


def _list(client, h, query=""):
    r = client.get(f"{API}/invoices/{query}", headers=h)
    assert r.status_code == 200, r.text
    return {d["id"]: d for d in r.json()["data"]}


def _insert_invoice_sql(cid: int, uid: int, **cols) -> int:
    """Inserta una factura por SQL crudo (como una fila antigua/legacy), sin pasar por el ORM ni por defaults."""
    row = {"invoice_number": f"LEG-{uuid.uuid4().hex[:10]}", "company_id": cid, "created_by": uid}
    row.update(cols)
    names = ", ".join(row)
    params = ", ".join(f":{k}" for k in row)
    db = SessionLocal()
    try:
        db.execute(text(f"INSERT INTO invoices ({names}) VALUES ({params})"), row)
        db.commit()
        return db.execute(text("SELECT id FROM invoices WHERE invoice_number = :n"),
                          {"n": row["invoice_number"]}).scalar_one()
    finally:
        db.close()


def _insert_item_sql(invoice_id: int, **cols) -> int:
    row = {"invoice_id": invoice_id, "description": "Linea legacy", "unit_price": 1.0}
    row.update(cols)
    names = ", ".join(row)
    params = ", ".join(f":{k}" for k in row)
    db = SessionLocal()
    try:
        db.execute(text(f"INSERT INTO invoice_items ({names}) VALUES ({params})"), row)
        db.commit()
        return db.execute(text("SELECT max(id) FROM invoice_items WHERE invoice_id = :i"),
                          {"i": invoice_id}).scalar_one()
    finally:
        db.close()


@pytest.fixture(scope="module")
def user(client):
    """Un solo titular por modulo: /auth/register tiene limite de 10/min por IP (SecurityMiddleware)."""
    return _register_login(client)


# ---------------------------------------------------------------------------- 1. TPV a 0 EUR

def test_tpv_invoice_with_zero_euro_line_is_listed_and_readable(client, user):
    h, _, _ = user
    ids = []
    for name, price in (("Cafe", 1.5), ("Agua (invitacion)", 0.0)):
        r = client.post(f"{API}/tpv/products", headers=h,
                        json={"name": name, "price": price, "category": "Bebidas", "iva_rate": 10})
        assert r.status_code == 200, r.text
        ids.append(r.json()["product"]["id"])
    r = client.post(f"{API}/tpv/sale", headers=h, json={
        "payment_method": "efectivo", "cart_items": [{"product_id": i, "quantity": 1} for i in ids]})
    assert r.status_code == 200, r.text
    ticket_id = r.json()["ticket_id"]
    r = client.post(f"{API}/tpv/invoice", headers=h, json={"ticket_id": ticket_id})
    assert r.status_code == 200, r.text
    inv_id = r.json()["invoice"]["id"]

    listed = _list(client, h)
    assert inv_id in listed
    lines = {it["description"]: it for it in listed[inv_id]["items"]}
    assert lines["Agua (invitacion)"]["unit_price"] == 0.0
    assert lines["Cafe"]["unit_price"] == pytest.approx(1.5)
    assert listed[inv_id]["total"] == pytest.approx(1.65, abs=0.01)
    assert listed[inv_id]["status"] == "paid"

    one = client.get(f"{API}/invoices/{inv_id}", headers=h)
    assert one.status_code == 200, one.text
    assert {it["unit_price"] for it in one.json()["data"]["items"]} == {0.0, 1.5}


# ---------------------------------------------------------------------------- 2. NULLs legacy

def test_legacy_invoice_with_nulls_is_returned_with_nulls(client, user):
    h, uid, cid = user
    inv_id = _insert_invoice_sql(cid, uid)  # solo numero, empresa y autor: todo lo demas NULL
    item_null = _insert_item_sql(inv_id, description="", unit_price=0.0)  # quantity/updated_at/... NULL
    item_weird = _insert_item_sql(inv_id, description="Devolucion", quantity=-2.0, unit_price=3.0,
                                  tax_rate=150.0, discount=-1.0)
    item_zero_qty = _insert_item_sql(inv_id, description="Sin cantidad", quantity=0.0, unit_price=2.0)

    listed = _list(client, h)
    assert inv_id in listed
    d = listed[inv_id]
    for k in ("status", "invoice_type", "issue_date", "due_date", "subtotal", "tax_amount", "discount_amount",
              "total", "amount_paid", "amount_due", "created_at", "updated_at", "customer_id", "notes"):
        assert d[k] is None, (k, d[k])
    items = {it["id"]: it for it in d["items"]}
    n = items[item_null]
    assert n["description"] == "" and n["unit_price"] == 0.0
    for k in ("quantity", "tax_rate", "discount", "subtotal", "tax_amount", "total", "created_at", "updated_at"):
        assert n[k] is None, (k, n[k])
    w = items[item_weird]
    assert (w["quantity"], w["tax_rate"], w["discount"]) == (-2.0, 150.0, -1.0)
    assert items[item_zero_qty]["quantity"] == 0.0

    one = client.get(f"{API}/invoices/{inv_id}", headers=h)
    assert one.status_code == 200, one.text
    assert one.json()["data"]["total"] is None and one.json()["data"]["status"] is None


# ---------------------------------------------------------------------------- 3. due_date < issue_date guardado

def test_stored_due_date_before_issue_date_does_not_break_list(client, user):
    h, uid, cid = user
    issue = datetime.utcnow().replace(microsecond=0)
    inv_id = _insert_invoice_sql(cid, uid, invoice_type="invoice", status="sent", issue_date=issue,
                                 due_date=issue - timedelta(days=10), subtotal=10.0, tax_amount=2.1,
                                 discount_amount=0.0, total=12.1, amount_paid=0.0, amount_due=12.1,
                                 created_at=issue, updated_at=issue)
    good_id = _insert_invoice_sql(cid, uid, invoice_type="invoice", status="draft", issue_date=issue,
                                  due_date=issue + timedelta(days=30), subtotal=1.0, tax_amount=0.21,
                                  discount_amount=0.0, total=1.21, amount_paid=0.0, amount_due=1.21,
                                  created_at=issue, updated_at=issue)
    listed = _list(client, h)
    assert {inv_id, good_id} <= set(listed)
    assert listed[inv_id]["due_date"] < listed[inv_id]["issue_date"]
    assert client.get(f"{API}/invoices/{inv_id}", headers=h).status_code == 200


# ---------------------------------------------------------------------------- 4. la ENTRADA sigue validando

@pytest.fixture(scope="module")
def customer_id(client, user):
    """Cliente real de la empresa (create_invoice exige customer_id): asi el unico motivo de rechazo es el campo."""
    r = client.post(f"{API}/customers", headers=user[0],
                    json={"name": "Cliente Tolerante", "email": f"cl_{uuid.uuid4().hex[:8]}@example.com"})
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


def _create(client, h, customer_id, **over):
    body = {"customer_id": customer_id, "invoice_type": "invoice", "status": "draft", "issue_date": "2026-10-20",
            "items": [{"description": "Servicio", "quantity": 1, "unit_price": 10.0, "tax_rate": 21.0}]}
    item_over = over.pop("item", None)
    if item_over:
        body["items"][0].update(item_over)
    body.update(over)
    return client.post(f"{API}/invoices/", headers=h, json=body)


@pytest.mark.parametrize("item_over,field", [
    ({"unit_price": -1.0}, "unit_price"),
    ({"quantity": 0}, "quantity"),
    ({"quantity": -1}, "quantity"),
    ({"description": ""}, "description"),
    ({"tax_rate": 101}, "tax_rate"),
    ({"discount": -0.5}, "discount"),
])
def test_create_still_rejects_invalid_lines(client, user, customer_id, item_over, field):
    h, _, _ = user
    r = _create(client, h, customer_id, item=item_over)
    assert r.status_code == 422, r.text
    assert any(field in [str(p) for p in e.get("loc", [])] for e in r.json()["detail"]), r.text


def test_create_still_rejects_due_date_before_issue_date(client, user, customer_id):
    h, _, _ = user
    r = _create(client, h, customer_id, issue_date="2026-10-20", due_date="2026-10-10")
    assert r.status_code == 422, r.text
    assert "Due date cannot be before issue date" in r.text


def test_create_accepts_zero_euro_line(client, user, customer_id):
    h, _, _ = user
    r = _create(client, h, customer_id, items=[
        {"description": "Servicio", "quantity": 1, "unit_price": 10.0, "tax_rate": 21.0},
        {"description": "Invitacion", "quantity": 1, "unit_price": 0.0, "tax_rate": 21.0},
    ])
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert sorted(it["unit_price"] for it in data["items"]) == [0.0, 10.0]
    assert data["total"] == pytest.approx(12.1)
    assert data["id"] in _list(client, h)


def test_response_schemas_do_not_inherit_input_rules():
    """Los schemas de respuesta no heredan de los de entrada (que si llevan las reglas de negocio)."""
    from app.schemas.erp import InvoiceBase, InvoiceInDB, InvoiceItemBase, InvoiceItemInDB
    assert not issubclass(InvoiceInDB, InvoiceBase)
    assert not issubclass(InvoiceItemInDB, InvoiceItemBase)
    m = InvoiceInDB.model_validate({"id": 1, "invoice_number": "X", "status": None, "total": None,
                                    "issue_date": "2026-10-20T10:00:00", "due_date": "2026-10-01T00:00:00",
                                    "items": [{"id": 1, "invoice_id": 1, "unit_price": 0.0, "quantity": 0.0,
                                               "tax_rate": 200.0, "description": None}]})
    assert m.total is None and m.status is None and m.items[0].unit_price == 0.0
