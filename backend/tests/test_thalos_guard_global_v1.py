"""J5e: cobertura estructural THALOS de toda ruta mutante /api/*.

Sin red ni LLM. Si alguien anade una ruta POST/PUT/PATCH/DELETE y la cobertura global no se
instala (o la allowlist queda obsoleta), estos tests fallan."""

from __future__ import annotations

import uuid

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.company import Company, UserCompany
from app.models.thalos_security_event import ThalosSecurityEvent
from app.models.user import User
from services import thalos_request_guard_v1 as g

P = "/api/v1"


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


def _mk_user(db, with_company=True):
    suf = uuid.uuid4().hex[:8]
    company = None
    if with_company:
        company = Company(company_name=f"J5e {suf}", slug=f"j5e-{suf}")
        db.add(company)
        db.flush()
    u = User(email=f"j5e_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
             full_name="J5e", is_active=True, is_superuser=False)
    db.add(u)
    db.flush()
    if company:
        db.add(UserCompany(user_id=u.id, company_id=company.id, role="owner"))
    db.commit()
    db.refresh(u)
    return u, company


def _h(client, user):
    r = client.post(f"{P}/auth/login", data={"username": user.email, "password": "TestPass1"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _route_events(db, route, source=None):
    db.expire_all()
    q = db.query(ThalosSecurityEvent).filter(ThalosSecurityEvent.event_type == "request_guard")
    if source:
        q = q.filter(ThalosSecurityEvent.source == source)
    return [e for e in q.order_by(ThalosSecurityEvent.id).all() if route in str(e.details_json)]


def _mutating_routes():
    return [r for r in app.routes if isinstance(r, APIRoute) and r.path_format.startswith("/api/")
            and set(r.methods) & g.MUTATING_METHODS]


def _calls(dep):
    yield dep.call
    for d in dep.dependencies:
        yield from _calls(d)


def test_every_mutating_route_is_covered():
    routes = _mutating_routes()
    assert len(routes) > 150
    uncovered = [(sorted(r.methods), r.path_format) for r in routes if not g.route_is_thalos_covered(r)]
    assert not uncovered, f"Rutas mutantes sin cobertura THALOS: {uncovered}"


def test_allowlists_have_no_stale_entries_and_are_disjoint():
    paths = {r.path_format for r in _mutating_routes()}
    for allow in (g.ANON_BODY_ROUTES, g.ANON_EVENT_ONLY_ROUTES, g.AUTH_NO_COMPANY_ROUTES):
        assert allow <= paths, allow - paths
    assert not (g.ANON_BODY_ROUTES & g.ANON_EVENT_ONLY_ROUTES)
    assert not (g.ANON_BODY_ROUTES & g.AUTH_NO_COMPANY_ROUTES)
    assert not (g.ANON_EVENT_ONLY_ROUTES & g.AUTH_NO_COMPANY_ROUTES)


def test_allowlist_routes_use_expected_guard():
    by_path = {r.path_format: r for r in _mutating_routes()}
    for p in g.ANON_BODY_ROUTES:
        assert g.thalos_anonymous_guard in set(_calls(by_path[p].dependant)), p
    for p in g.ANON_EVENT_ONLY_ROUTES:
        assert g.thalos_anonymous_event_only_guard in set(_calls(by_path[p].dependant)), p
    for p in g.AUTH_NO_COMPANY_ROUTES:
        assert g.thalos_request_guard_no_company in set(_calls(by_path[p].dependant)), p


def test_install_covers_new_route_and_is_idempotent():
    tmp = FastAPI()
    r = APIRouter()

    @r.post("/nueva")
    def nueva():
        return {"ok": True}

    @r.get("/lectura")
    def lectura():
        return {"ok": True}

    tmp.include_router(r, prefix="/api/v1")
    before = [x for x in tmp.routes if isinstance(x, APIRoute) and x.path == "/api/v1/nueva"][0]
    assert not g.route_is_thalos_covered(before)
    assert g.install_global_thalos_guard(tmp) == 1
    assert g.route_is_thalos_covered(before)
    assert g.install_global_thalos_guard(tmp) == 0  # idempotente
    get_route = [x for x in tmp.routes if isinstance(x, APIRoute) and x.path == "/api/v1/lectura"][0]
    assert not g.route_is_thalos_covered(get_route)  # GET no se toca


def test_unguarded_route_now_logs_event_with_tenant(client, db):
    u, comp = _mk_user(db)
    r = client.post(f"{P}/crm/customers", json={"name": "Cliente J5e"}, headers=_h(client, u))
    assert r.status_code != 403
    ev = [e for e in _route_events(db, "/api/v1/crm/customers", "thalos_request_guard") if e.user_id == u.id]
    assert len(ev) == 1
    assert ev[0].action_taken == "allow" and ev[0].company_id == comp.id


def test_control_chars_rejected_on_previously_unguarded_route(client, db):
    u, _ = _mk_user(db)
    r = client.post(f"{P}/crm/customers", json={"name": "a\u0000b"}, headers=_h(client, u))
    assert r.status_code == 400
    ev = [e for e in _route_events(db, "/api/v1/crm/customers") if e.user_id == u.id]
    assert ev and ev[-1].action_taken == "deny" and ev[-1].decision_rule == "control_characters"


def test_no_company_denied_outside_allowlist(client, db):
    u, _ = _mk_user(db, with_company=False)
    r = client.post(f"{P}/crm/customers", json={"name": "X"}, headers=_h(client, u))
    assert r.status_code == 403
    ev = [e for e in _route_events(db, "/api/v1/crm/customers") if e.user_id == u.id]
    assert ev[-1].decision_rule == "no_company"


def test_user_without_company_passes_in_no_company_allowlist(client, db):
    u, _ = _mk_user(db, with_company=False)
    r = client.patch(f"{P}/settings", json={}, headers=_h(client, u))
    assert r.status_code != 403, r.text
    ev = [e for e in _route_events(db, "/api/v1/settings") if e.user_id == u.id]
    assert len(ev) == 1 and ev[0].action_taken == "allow" and ev[0].company_id is None


def test_no_double_event_on_already_guarded_route(client, db):
    u, _ = _mk_user(db)
    client.post(f"{P}/invoices/999999/send", headers=_h(client, u))
    ev = [e for e in _route_events(db, "/invoices/{invoice_id}/send") if e.user_id == u.id]
    assert len(ev) == 1


def test_anonymous_login_logs_event_and_passes(client, db):
    n0 = len(_route_events(db, "/api/v1/auth/login", "thalos_anonymous_guard"))
    r = client.post(f"{P}/auth/login", data={"username": "nadie@example.test", "password": "x"})
    assert r.status_code in (400, 401)  # rechaza el handler de auth, no THALOS
    ev = _route_events(db, "/api/v1/auth/login", "thalos_anonymous_guard")
    assert len(ev) == n0 + 1 and ev[-1].action_taken == "allow" and ev[-1].user_id is None


def test_anonymous_register_rejects_control_chars(client, db):
    r = client.post(f"{P}/auth/register", json={"email": "a\u0000@example.test", "password": "x"})
    assert r.status_code == 400
    ev = _route_events(db, "/api/v1/auth/register", "thalos_anonymous_guard")
    assert ev[-1].action_taken == "deny" and ev[-1].decision_rule == "control_characters"


def test_webhook_gets_event_only_and_body_is_untouched(client, db):
    n0 = len(_route_events(db, "/api/v1/webhooks/twilio", "thalos_anonymous_guard"))
    body = b'{"x": "a\\u0000b"}'  # JSON valido con NUL escapado: el guard no lo valida ni lo lee
    client.post(f"{P}/webhooks/twilio", content=body, headers={"content-type": "application/json"})
    ev = _route_events(db, "/api/v1/webhooks/twilio", "thalos_anonymous_guard")
    assert len(ev) == n0 + 1 and ev[-1].action_taken == "allow"
    assert ev[-1].decision_rule == "anonymous_route_allowlisted"
