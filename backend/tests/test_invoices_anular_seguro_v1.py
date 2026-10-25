"""Tarea C (loop Facturas): anular / borrar facturas sin romper la normativa.

En España una factura EMITIDA no se anula ni se borra: se corrige con una factura rectificativa
(RD 1619/2012, art. 15). Regla:
  - borrador (draft): POST /void -> 200 (queda «void», conserva numero y lineas).
  - NO hay borrado fisico: DELETE /invoices/{id} -> 405 (la serie no tiene huecos y los registros de
    caja siguen apuntando a una fila que existe).
  - emitida (sent, paid, partially_paid, overdue): /void -> 409 con un detail que dice que requiere
    factura rectificativa (funcion futura). La BD no cambia: estado, totales, pagos, stock.
  - ya anulada (void): /void -> 409 sin escribir nada.
  - de otra empresa: 404 sin cambios. Sin token: 401. Usuario sin empresa: 403 (THALOS no_company).
Login real (Bearer via /auth/login), sin overrides de auth; la BD se relee tras cada llamada.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.base import SessionLocal
from app.main import app
from app.core.security import get_password_hash
from app.models.erp import Invoice, InvoiceItem, InventoryMovement, Payment, Product, InvoiceStatus
from app.models.thalos_security_event import ThalosSecurityEvent
from app.models.user import User

pytestmark = pytest.mark.usefixtures("no_external_messaging")
API = settings.API_V1_STR
EMITTED = ("sent", "paid", "partially_paid", "overdue")
_ES = {"sent": "enviada", "paid": "pagada", "partially_paid": "pagada en parte", "overdue": "vencida"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _login(client):
    suf = uuid.uuid4().hex[:10]
    payload = {
        "email": f"invanul_{suf}@example.com", "password": "TestPass1",
        "full_name": "Titular Anular", "phone": "612345678",
        "company_name": f"Empresa Anular {suf}", "business_type": "restaurant",
    }
    r = client.post(f"{API}/auth/register", json=payload)
    if r.status_code != 201:
        pytest.skip(f"Registro no disponible: {r.status_code}")
    login = client.post(f"{API}/auth/login", data={"username": payload["email"], "password": payload["password"]})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.fixture(scope="module")
def h_a(client):
    return _login(client)


@pytest.fixture(scope="module")
def h_b(client):
    return _login(client)


@pytest.fixture(scope="module")
def product_id(client, h_a):
    """Producto real de la empresa A con inventario (stock 10) para comprobar que no se mueve."""
    sku = f"ANU-{uuid.uuid4().hex[:8]}"
    r = client.post(f"{API}/products/", headers=h_a, json={
        "sku": sku, "name": f"Producto {sku}", "price": 50.0, "tax_rate": 21.0, "category": "goods", "status": "active",
    })
    assert r.status_code == 201, r.text
    pid = r.json()["data"]["id"]
    db = SessionLocal()
    try:
        p = db.query(Product).filter(Product.id == pid).one()
        p.track_inventory = True
        p.quantity_on_hand = 10.0
        db.commit()
    finally:
        db.close()
    return pid


def _create_draft(client, h, product_id=None):
    c = client.post(f"{API}/customers", headers=h, json={"name": "Cliente Anular", "email": f"cli_{uuid.uuid4().hex[:8]}@example.com"})
    assert c.status_code == 201, c.text
    item = {"description": "Servicio", "quantity": 2, "unit_price": 50.0, "tax_rate": 21.0}
    if product_id:
        item["product_id"] = product_id
    r = client.post(f"{API}/invoices/", headers=h, json={
        "customer_id": c.json()["data"]["id"], "invoice_type": "invoice", "status": "draft", "issue_date": "2026-01-10",
        "items": [item, {"description": "Desplazamiento", "quantity": 1, "unit_price": 10.0, "tax_rate": 21.0}],
    })
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["status"] == "draft"
    return data["id"]  # total = (100 + 10) * 1.21 = 133.1


def _pay(client, h, inv, amount):
    r = client.post(f"{API}/invoices/{inv}/payments", headers=h, json={
        "amount": amount, "payment_method": "cash", "status": "completed"})
    assert r.status_code == 201, r.text


def _make_emitted(client, h, state, product_id):
    """Factura en el estado emitido pedido, por la via real cuando existe (send / payments)."""
    inv = _create_draft(client, h, product_id)
    if state == "sent":
        assert client.post(f"{API}/invoices/{inv}/send", headers=h).status_code == 200
    elif state == "partially_paid":
        assert client.post(f"{API}/invoices/{inv}/send", headers=h).status_code == 200
        _pay(client, h, inv, 50.0)
    elif state == "paid":
        assert client.post(f"{API}/invoices/{inv}/send", headers=h).status_code == 200
        _pay(client, h, inv, 133.1)
    elif state == "overdue":
        # No hay endpoint que marque «vencida» (lo haria un proceso de vencimientos): se fija en BD.
        assert client.post(f"{API}/invoices/{inv}/send", headers=h).status_code == 200
        db = SessionLocal()
        try:
            db.query(Invoice).filter(Invoice.id == inv).one().status = InvoiceStatus.OVERDUE
            db.commit()
        finally:
            db.close()
    snap = _snapshot(inv, product_id)
    assert snap["status_api"] == state, snap
    return inv


def _snapshot(inv, product_id=None):
    """Foto de la BD de todo lo que /void (o un borrado fisico, que no existe) podria tocar."""
    db = SessionLocal()
    try:
        row = db.query(Invoice).filter(Invoice.id == inv).first()
        if row is None:
            return None
        return {
            "status_api": row.status.value,
            "status_db": row.status.value,
            "total": row.total, "amount_paid": row.amount_paid, "amount_due": row.amount_due,
            "updated_at": row.updated_at,
            "items": sorted((i.id, i.description, i.quantity) for i in
                            db.query(InvoiceItem).filter(InvoiceItem.invoice_id == inv).all()),
            "payments": sorted((p.id, p.amount, p.status.value) for p in
                               db.query(Payment).filter(Payment.invoice_id == inv).all()),
            "stock": (db.query(Product).filter(Product.id == product_id).one().quantity_on_hand
                      if product_id else None),
            "movements": (db.query(InventoryMovement).filter(InventoryMovement.product_id == product_id).count()
                          if product_id else None),
        }
    finally:
        db.close()


# ----------------------------------------------------------------------------------- borrador

def test_void_draft_becomes_void(client, h_a):
    inv = _create_draft(client, h_a)
    r = client.post(f"{API}/invoices/{inv}/void", headers=h_a)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "void"
    snap = _snapshot(inv)
    assert snap["status_api"] == "void" and snap["status_db"] == "void"
    assert len(snap["items"]) == 2  # anular no borra lineas


def test_delete_draft_not_allowed_405_and_invoice_kept(client, h_a):
    """No hay borrado fisico de facturas, tampoco de borradores: el numero de la serie no deja huecos
    y los registros de caja siguen apuntando a una fila que existe. El borrador solo se anula."""
    inv = _create_draft(client, h_a)
    before = _snapshot(inv)
    r = client.delete(f"{API}/invoices/{inv}", headers=h_a)
    assert r.status_code == 405, r.text
    assert _snapshot(inv) == before
    assert client.get(f"{API}/invoices/{inv}", headers=h_a).status_code == 200


def test_numbering_after_void_stays_unique_across_companies(client, h_a, h_b):
    """Regresion: la numeracion es count(Invoice.id)+1 global. Anular (no borrar) no baja el recuento,
    asi que la siguiente factura de otra empresa no repite numero (antes, con borrado fisico de un
    borrador que no era el ultimo -> IntegrityError UNIQUE invoice_number -> 500)."""
    first = _create_draft(client, h_a)
    second = _create_draft(client, h_a)
    assert client.post(f"{API}/invoices/{first}/void", headers=h_a).status_code == 200
    third = _create_draft(client, h_b)  # _create_draft ya exige 201
    db = SessionLocal()
    try:
        numbers = [db.query(Invoice).filter(Invoice.id == i).one().invoice_number for i in (first, second, third)]
        assert db.query(Invoice).filter(Invoice.id == first).one().status == InvoiceStatus.VOID
        all_numbers = [n for (n,) in db.query(Invoice.invoice_number).all()]
    finally:
        db.close()
    assert len(set(numbers)) == 3, numbers
    assert len(all_numbers) == len(set(all_numbers))


# ----------------------------------------------------------------------------------- emitidas

@pytest.mark.parametrize("state", EMITTED)
def test_emitted_invoice_cannot_be_voided(client, h_a, product_id, state):
    inv = _make_emitted(client, h_a, state, product_id)
    before = _snapshot(inv, product_id)
    assert before["status_db"] == state
    r = client.post(f"{API}/invoices/{inv}/void", headers=h_a)
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert "requiere una factura rectificativa (función futura)" in detail, detail
    assert "ya está emitida" in detail and f"estado: {_ES[state]}" in detail, detail
    after = _snapshot(inv, product_id)
    assert after == before  # estado, total, pagos, lineas, stock y movimientos intactos


# ----------------------------------------------------------------------------------- ya anulada

def test_already_void_rejected_without_writes(client, h_a):
    inv = _create_draft(client, h_a)
    assert client.post(f"{API}/invoices/{inv}/void", headers=h_a).status_code == 200
    before = _snapshot(inv)
    r = client.post(f"{API}/invoices/{inv}/void", headers=h_a)
    assert r.status_code == 409, r.text
    assert "ya está anulada" in r.json()["detail"]
    assert _snapshot(inv) == before


# ----------------------------------------------------------------------------------- tenant / auth

def test_other_company_gets_404_and_nothing_changes(client, h_a, h_b):
    inv = _create_draft(client, h_a)
    before = _snapshot(inv)
    assert client.post(f"{API}/invoices/{inv}/void", headers=h_b).status_code == 404
    assert _snapshot(inv) == before


def test_without_token_401_and_nothing_changes(client, h_a):
    inv = _create_draft(client, h_a)
    before = _snapshot(inv)
    assert client.post(f"{API}/invoices/{inv}/void").status_code == 401
    assert _snapshot(inv) == before


def test_user_without_company_403_by_thalos_and_nothing_changes(client, h_a):
    """Usuario real (login Bearer) sin empresa: THALOS lo para con 403 (regla no_company) antes del
    endpoint, y la factura no cambia."""
    inv = _create_draft(client, h_a)
    before = _snapshot(inv)
    suf = uuid.uuid4().hex[:8]
    db = SessionLocal()
    try:
        u = User(email=f"invanul_nocomp_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
                 full_name="Sin Empresa", is_active=True, is_superuser=False)
        db.add(u)
        db.commit()
        uid = u.id
    finally:
        db.close()
    login = client.post(f"{API}/auth/login", data={"username": f"invanul_nocomp_{suf}@example.test", "password": "TestPass1"})
    assert login.status_code == 200, login.text
    h = {"Authorization": f"Bearer {login.json()['access_token']}"}
    r = client.post(f"{API}/invoices/{inv}/void", headers=h)
    assert r.status_code == 403, r.text
    assert _snapshot(inv) == before
    db = SessionLocal()
    try:
        ev = db.query(ThalosSecurityEvent).filter(
            ThalosSecurityEvent.user_id == uid, ThalosSecurityEvent.event_type == "request_guard",
            ThalosSecurityEvent.action_taken == "deny").order_by(ThalosSecurityEvent.id).all()
        assert ev and ev[-1].decision_rule == "no_company"
    finally:
        db.close()
