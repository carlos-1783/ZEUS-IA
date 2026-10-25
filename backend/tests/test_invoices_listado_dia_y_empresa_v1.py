"""GET /invoices/: filtro de fechas por DIA LOCAL completo y scope por EMPRESA DE SESION.

Fija dos fallos del listado de facturas de la app:
  1. start_date/end_date comparaban la columna DateTime `issue_date` con un `date`: una factura
     emitida el ultimo dia del rango (p. ej. hoy a las 10:00) no entraba. Ahora el rango es el mismo
     que el de las lecturas de RAFAEL: [inicio del dia local start_date, inicio del dia local
     siguiente a end_date) en UTC naive (services.local_day_v1.local_days_range_utc_naive).
  2. Se listaban las facturas de TODAS las empresas del usuario. Ahora solo las de la empresa de
     sesion (crm_svc.primary_company_id, la misma con la que se crean y la que lee el chat);
     sin empresa -> lista vacia (fail-closed).
Login real (register + /auth/login, Bearer) y TestClient sobre la app real.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.base import SessionLocal
from app.main import app
from app.models.company import Company, UserCompany
from app.models.erp import Invoice, InvoiceStatus, InvoiceType
from app.models.user import User
from services.local_day_v1 import day_bounds_utc, today_local

pytestmark = pytest.mark.usefixtures("no_external_messaging")
API = settings.API_V1_STR


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _register_login(client):
    suf = uuid.uuid4().hex[:10]
    payload = {"email": f"invlist_{suf}@example.com", "password": "TestPass1", "full_name": "Titular Listado",
               "phone": "612345678", "company_name": f"Empresa Listado {suf}", "business_type": "restaurant"}
    r = client.post(f"{API}/auth/register", json=payload)
    if r.status_code != 201:
        pytest.skip(f"Registro no disponible: {r.status_code}")
    login = client.post(f"{API}/auth/login", data={"username": payload["email"], "password": payload["password"]})
    assert login.status_code == 200, login.text
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == payload["email"]).one()
        uc = (db.query(UserCompany).filter(UserCompany.user_id == user.id)
              .order_by(UserCompany.id.asc()).first())
        assert uc is not None, "el registro debe crear la empresa del titular"
        return {"Authorization": f"Bearer {login.json()['access_token']}"}, user.id, uc.company_id
    finally:
        db.close()


def _add_second_company(user_id):
    """Segunda empresa del MISMO usuario (UserCompany posterior: no es la de sesion)."""
    db = SessionLocal()
    try:
        suf = uuid.uuid4().hex[:8]
        c = Company(company_name=f"Segunda {suf}", slug=f"segunda-{suf}")
        db.add(c)
        db.flush()
        db.add(UserCompany(user_id=user_id, company_id=c.id, role="owner"))
        db.commit()
        return c.id
    finally:
        db.close()


def _inv(cid, issue, status=InvoiceStatus.SENT, total=121.0, created_by=None):
    db = SessionLocal()
    try:
        inv = Invoice(invoice_number=f"L-{uuid.uuid4().hex[:10]}", company_id=cid,
                      invoice_type=InvoiceType.INVOICE, status=status, issue_date=issue,
                      due_date=issue + timedelta(days=30), subtotal=100.0, tax_amount=21.0,
                      discount_amount=0.0, total=total, amount_paid=0.0, amount_due=total,
                      created_by=created_by)
        db.add(inv)
        db.commit()
        return inv.id
    finally:
        db.close()


def _today_bounds():
    """Una sola lectura del dia local (Europe/Madrid): limites naive UTC del dia de HOY."""
    today = today_local()
    start, end = day_bounds_utc(today)
    return today, start.replace(tzinfo=None), end.replace(tzinfo=None)


def _ids(client, h, query=""):
    r = client.get(f"{API}/invoices/{query}", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    ids = {d["id"] for d in body["data"]}
    assert body["total"] == len(ids)
    return ids


def test_issued_today_enters_filter_today_including_last_local_hour(client):
    h, uid, cid = _register_login(client)
    today, start, end = _today_bounds()
    first_minute = _inv(cid, start + timedelta(minutes=1))
    mid_day = _inv(cid, start + timedelta(hours=10))
    last_hour = _inv(cid, end - timedelta(minutes=30))  # ultima hora del dia LOCAL
    yesterday_late = _inv(cid, start - timedelta(minutes=1))  # 23:59 local de ayer
    tomorrow_early = _inv(cid, end)  # 00:00 local de manana

    d = today.isoformat()
    got = _ids(client, h, f"?start_date={d}&end_date={d}")
    assert {first_minute, mid_day, last_hour} <= got
    assert yesterday_late not in got and tomorrow_early not in got

    # Solo end_date=hoy: el dia de hoy entero entra, manana no.
    got_end = _ids(client, h, f"?end_date={d}")
    assert {first_minute, mid_day, last_hour, yesterday_late} <= got_end
    assert tomorrow_early not in got_end
    # Solo start_date=hoy: ayer fuera.
    got_start = _ids(client, h, f"?start_date={d}")
    assert {first_minute, mid_day, last_hour, tomorrow_early} <= got_start
    assert yesterday_late not in got_start

    # Rango de varios dias: ayer..hoy incluye ambos dias enteros.
    y = (today - timedelta(days=1)).isoformat()
    assert {yesterday_late, first_minute, last_hour} <= _ids(client, h, f"?start_date={y}&end_date={d}")


def test_invoice_created_via_api_for_today_listed_with_today_filter(client):
    """La factura creada por POST /invoices con issue_date=hoy aparece con start_date=end_date=hoy."""
    h, _, _ = _register_login(client)
    today = today_local()
    c = client.post(f"{API}/customers", headers=h,
                    json={"name": "Cliente Listado", "email": f"cl_{uuid.uuid4().hex[:8]}@example.com"})
    assert c.status_code == 201, c.text
    r = client.post(f"{API}/invoices/", headers=h, json={
        "customer_id": c.json()["data"]["id"], "invoice_type": "invoice", "status": "draft",
        "issue_date": today.isoformat(),
        "items": [{"description": "Servicio", "quantity": 1, "unit_price": 10.0, "tax_rate": 21.0}]})
    assert r.status_code == 201, r.text
    d = today.isoformat()
    assert r.json()["data"]["id"] in _ids(client, h, f"?start_date={d}&end_date={d}")


def test_user_with_two_companies_only_sees_session_company(client):
    h, uid, session_cid = _register_login(client)
    other_cid = _add_second_company(uid)
    assert other_cid != session_cid
    today, start, _ = _today_bounds()
    mine_sent = _inv(session_cid, start + timedelta(hours=9))
    mine_paid = _inv(session_cid, start + timedelta(hours=11), status=InvoiceStatus.PAID)
    other_sent = _inv(other_cid, start + timedelta(hours=9))
    other_paid = _inv(other_cid, start + timedelta(hours=11), status=InvoiceStatus.PAID)
    other_old = _inv(other_cid, start - timedelta(days=40))

    d = today.isoformat()
    foreign = {other_sent, other_paid, other_old}
    for q in ("", "?limit=1000", f"?start_date={d}&end_date={d}", "?status=sent",
              f"?status=sent&start_date={d}&end_date={d}", "?status=paid", "?invoice_type=invoice"):
        got = _ids(client, h, q)
        assert not (got & foreign), (q, got & foreign)
    assert _ids(client, h) == {mine_sent, mine_paid}
    assert _ids(client, h, f"?status=sent&start_date={d}&end_date={d}") == {mine_sent}
    assert _ids(client, h, "?status=paid") == {mine_paid}


def test_other_user_sees_nothing_foreign(client):
    h_a, _, cid_a = _register_login(client)
    h_b, _, cid_b = _register_login(client)
    today, start, _ = _today_bounds()
    a_inv = _inv(cid_a, start + timedelta(hours=8))
    b_inv = _inv(cid_b, start + timedelta(hours=8))
    d = today.isoformat()
    for q in ("", f"?start_date={d}&end_date={d}", "?status=sent"):
        assert _ids(client, h_b, q) == {b_inv}, q
        assert _ids(client, h_a, q) == {a_inv}, q
    assert client.get(f"{API}/invoices/{a_inv}", headers=h_b).status_code == 404


def test_user_without_company_gets_empty_list_fail_closed(client):
    """Sin empresa de sesion: lista vacia (aunque tenga facturas legacy sin empresa)."""
    suf = uuid.uuid4().hex[:10]
    email = f"invnocomp_{suf}@example.com"
    db = SessionLocal()
    try:
        u = User(email=email, hashed_password=get_password_hash("TestPass1"), is_active=True)
        db.add(u)
        db.commit()
        uid = u.id
    finally:
        db.close()
    login = client.post(f"{API}/auth/login", data={"username": email, "password": "TestPass1"})
    if login.status_code != 200:
        pytest.skip(f"Login sin empresa no disponible: {login.status_code}")
    h = {"Authorization": f"Bearer {login.json()['access_token']}"}
    _inv(None, datetime.utcnow(), created_by=uid)
    r = client.get(f"{API}/invoices/", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["data"] == [] and r.json()["total"] == 0


def test_list_requires_auth(client):
    assert client.get(f"{API}/invoices/").status_code == 401
