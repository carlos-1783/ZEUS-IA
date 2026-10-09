"""J5c: guard THALOS en rutas de impacto, marketing con autenticacion y auth/debug restringido.
Sin red ni LLM: los servicios externos de ads se sustituyen por dobles locales."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.company import Company, UserCompany
from app.models.crm_office import CustomerRecord
from app.models.customer import Customer
from app.models.erp import Invoice, InvoiceStatus
from app.models.thalos_security_event import ThalosSecurityEvent
from app.models.user import User
from services.marketing_service import marketing_service
from services.thalos_request_guard_v1 import thalos_request_guard

P = "/api/v1"

GUARDED = {
    ("POST", "/marketing/google-ads/campaign"),
    ("GET", "/marketing/google-ads/performance"),
    ("POST", "/marketing/google-ads/optimize"),
    ("POST", "/marketing/meta-ads/campaign"),
    ("GET", "/marketing/meta-ads/insights"),
    ("POST", "/marketing/analytics/data"),
    ("GET", "/marketing/report"),
    ("GET", "/marketing/status"),
    ("PUT", "/marketing/integrations"),
    ("POST", "/integrations/hacienda/factura"),
    ("POST", "/integrations/hacienda/modelo-303"),
    ("POST", "/integrations/stripe/payment-intent"),
    ("POST", "/google/gmail/send"),
    ("POST", "/google/drive/upload"),
    ("POST", "/google/calendar/event"),
    ("POST", "/google/sheets/create"),
    ("POST", "/google/sheets/write"),
    ("POST", "/google/sheets/read"),
    ("POST", "/perseo/v2/publish"),
    ("POST", "/perseo/v2/pipeline/run"),
    ("PUT", "/invoices/{invoice_id}"),
    ("POST", "/invoices/{invoice_id}/send"),
    ("POST", "/invoices/{invoice_id}/void"),
    ("POST", "/invoices/{invoice_id}/payments"),
    ("POST", "/crm/records/{record_id}/charge"),
    ("POST", "/tpv/sale"),
    ("POST", "/tpv/sell"),
    ("POST", "/tpv/invoice"),
    ("POST", "/tpv/close-register"),
    ("POST", "/zeus/transactions"),
    ("POST", "/zeus-core/leads/{lead_id}/convert"),
    ("POST", "/workspace/playbooks/run"),
    ("POST", "/api-keys"),
    ("POST", "/user/api-keys"),
    ("POST", "/workspaces/thalos/credential-revoker"),
    ("POST", "/thalos/alerts/{alert_id}/resolve"),
}


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def client():
    return TestClient(app)


def _mk_user(db, superuser=False, with_company=True):
    suf = uuid.uuid4().hex[:8]
    company = None
    if with_company:
        company = Company(company_name=f"J5c {suf}", slug=f"j5c-{suf}")
        db.add(company)
        db.flush()
    u = User(email=f"j5c_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
             full_name="J5c", is_active=True, is_superuser=superuser)
    db.add(u)
    db.flush()
    if company:
        db.add(UserCompany(user_id=u.id, company_id=company.id, role="owner"))
    db.commit()
    db.refresh(u)
    return u, company


def _h(client, user):
    """Token real via login (sin overrides de autenticacion)."""
    r = client.post(f"{P}/auth/login", data={"username": user.email, "password": "TestPass1"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _events(db, user, decision=None):
    db.expire_all()
    q = db.query(ThalosSecurityEvent).filter(
        ThalosSecurityEvent.user_id == user.id, ThalosSecurityEvent.event_type == "request_guard")
    if decision:
        q = q.filter(ThalosSecurityEvent.action_taken == decision)
    return q.order_by(ThalosSecurityEvent.id).all()


def _calls(dep):
    yield dep.call
    for d in dep.dependencies:
        yield from _calls(d)


def test_all_impact_routes_have_guard():
    found = set()
    for route in app.routes:
        path = getattr(route, "path", "")
        if not path.startswith(P):
            continue
        short = path[len(P):]
        for m in getattr(route, "methods", None) or set():
            if (m, short) in GUARDED:
                found.add((m, short))
                assert thalos_request_guard in set(_calls(route.dependant)), (m, short)
    assert found == GUARDED, GUARDED - found


# --------------------------------------------------------------- marketing


def test_marketing_requires_authentication(client):
    body = {"campaign_name": "x", "budget_amount": 1, "target_locations": [], "keywords": [], "ad_text": {}}
    assert client.post(f"{P}/marketing/google-ads/campaign", json=body).status_code == 401
    assert client.post(f"{P}/marketing/google-ads/campaign", json={}).status_code == 401
    assert client.post(f"{P}/marketing/google-ads/optimize", json={"campaign_id": "1"}).status_code == 401
    assert client.post(f"{P}/marketing/meta-ads/campaign", json={}).status_code == 401
    assert client.post(f"{P}/marketing/analytics/data", json={}).status_code == 401
    assert client.get(f"{P}/marketing/google-ads/performance").status_code == 401
    assert client.get(f"{P}/marketing/meta-ads/insights").status_code == 401
    assert client.get(f"{P}/marketing/report").status_code == 401
    assert client.get(f"{P}/marketing/status").status_code == 401


def test_marketing_platform_ads_forbidden_for_company_user_and_allowed_for_superuser(client, db, monkeypatch):
    calls = []

    async def fake_create(**kw):
        calls.append(kw)
        return {"success": True, "campaign_id": "local-double"}

    monkeypatch.setattr(marketing_service, "create_google_ads_campaign", fake_create)
    body = {"campaign_name": "x", "budget_amount": 5, "target_locations": ["ES"], "keywords": ["k"], "ad_text": {}}

    owner, _ = _mk_user(db)
    r = client.post(f"{P}/marketing/google-ads/campaign", json=body, headers=_h(client, owner))
    assert r.status_code == 403
    assert calls == []  # el servicio de pago NO se invoco

    sup, _ = _mk_user(db, superuser=True, with_company=False)
    r = client.post(f"{P}/marketing/google-ads/campaign", json=body, headers=_h(client, sup))
    assert r.status_code == 200 and r.json()["campaign_id"] == "local-double"
    assert len(calls) == 1
    assert _events(db, sup, "allow")


# --------------------------------------------------------------- sin empresa


@pytest.mark.parametrize("method,path,body", [
    ("POST", "/invoices/1/send", None),
    ("POST", "/crm/records/1/charge", {"base_amount": 10, "payment_method": "cash"}),
    ("POST", "/tpv/sale", {}),
    ("POST", "/google/gmail/send", {}),
    ("POST", "/perseo/v2/publish", {}),
    ("POST", "/workspace/playbooks/run", {}),
    ("POST", "/zeus/transactions", {}),
    ("POST", "/api-keys", None),
])
def test_user_without_company_denied_with_event(client, db, method, path, body):
    u, _ = _mk_user(db, with_company=False)
    kw = {"json": body} if body is not None else {}
    r = client.request(method, f"{P}{path}", headers=_h(client, u), **kw)
    assert r.status_code == 403, (path, r.status_code, r.text)
    ev = _events(db, u, "deny")
    assert ev and ev[-1].decision_rule == "no_company"


# --------------------------------------------------------------- cross-tenant


def test_invoice_send_and_void_cross_tenant(client, db):
    a, _ = _mk_user(db)
    b, comp_b = _mk_user(db)
    inv = Invoice(invoice_number=f"J5C-{uuid.uuid4().hex[:10]}", company_id=comp_b.id,
                  status=InvoiceStatus.DRAFT, created_by=b.id)
    db.add(inv)
    db.commit()
    db.refresh(inv)

    ha, hb = _h(client, a), _h(client, b)
    assert client.post(f"{P}/invoices/{inv.id}/send", headers=ha).status_code == 404
    assert client.post(f"{P}/invoices/{inv.id}/void", headers=ha).status_code == 404
    db.expire_all()
    assert db.get(Invoice, inv.id).status == InvoiceStatus.DRAFT

    # control positivo: la empresa propietaria SI supera guard y filtro de tenant (no 403/404).
    # El 500 posterior es un bug previo e independiente de send_invoice (muta un modelo
    # Pydantic InvoiceInDB: "no field sent_at"); se reporta aparte y no se enmascara aqui.
    r = client.post(f"{P}/invoices/{inv.id}/send", headers=hb)
    assert r.status_code not in (401, 403, 404), r.text
    assert _events(db, b, "allow")


def test_crm_record_charge_cross_tenant(client, db):
    a, _ = _mk_user(db)
    b, comp_b = _mk_user(db)
    cust = Customer(name="Cliente B", company_id=comp_b.id, owner_user_id=b.id)
    db.add(cust)
    db.flush()
    rec = CustomerRecord(company_id=comp_b.id, customer_id=cust.id, title="Exp B")
    db.add(rec)
    db.commit()
    db.refresh(rec)

    r = client.post(f"{P}/crm/records/{rec.id}/charge", headers=_h(client, a),
                    json={"base_amount": 10, "payment_method": "cash"})
    assert r.status_code in (403, 404), r.text


# --------------------------------------------------------------- multipart


def test_drive_upload_multipart_not_broken_by_guard(client, db):
    u, _ = _mk_user(db)
    r = client.post(f"{P}/google/drive/upload", headers=_h(client, u),
                    files={"file": ("a.txt", b"hola", "text/plain")})
    # El guard deja pasar el multipart (no lo parsea como JSON); lo rechaza la validacion
    # del propio endpoint (espera JSON), nunca el guard (400 invalid_json / 413).
    assert r.status_code == 422, r.text
    ev = _events(db, u, "allow")
    assert ev and ev[-1].decision_rule == "request_validated"


# --------------------------------------------------------------- auth/debug


def test_debug_verify_token_restricted(client, db):
    u, _ = _mk_user(db)
    assert client.post(f"{P}/auth/debug/verify-token", json={"token": "x"}).status_code == 401
    assert client.post(f"{P}/auth/debug/verify-token", json={"token": "x"}, headers=_h(client, u)).status_code == 403
    sup, _ = _mk_user(db, superuser=True, with_company=False)
    r = client.post(f"{P}/auth/debug/verify-token", json={"token": "x"}, headers=_h(client, sup))
    assert r.status_code == 200
