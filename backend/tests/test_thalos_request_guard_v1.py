"""J5: guard THALOS por peticion + auditoria post-accion. Sin LLM ni red."""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from agents.zeus_core import ZeusCore
from app.api.v1.endpoints import chat as chat_endpoint
from app.core.auth import get_current_active_user
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.agent_activity import AgentActivity
from app.models.company import Company, UserCompany
from app.models.thalos_security_event import ThalosSecurityEvent
from app.models.user import User
from app.models.zeus_pending_approval import ZeusPendingApproval
from services.thalos_request_guard_v1 import (
    MAX_MESSAGE_CHARS,
    thalos_audit_result,
    thalos_request_guard,
)
from services.zeus_human_approval_v1 import request_approval

COMM = "/api/v1/chat/agents/communicate"
CHAT = "/api/v1/chat/PERSEO/chat"
RESOLVE = "/api/v1/zeus-core/approvals/{}/resolve"


class StubAgent:
    def __init__(self, name):
        self.name = name

    def set_zeus_core_ref(self, z):
        pass

    def process_request(self, ctx):
        return {"success": True, "content": "ok"}


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def client(monkeypatch):
    z = ZeusCore()
    ag = {n: StubAgent(n) for n in ("PERSEO", "RAFAEL", "THALOS", "JUSTICIA", "AFRODITA")}
    for a in ag.values():
        z.register_agent(a)
    monkeypatch.setattr(chat_endpoint, "ensure_agent_stack", lambda: None)
    monkeypatch.setattr(chat_endpoint, "zeus", z)
    monkeypatch.setattr(chat_endpoint, "AGENTS", {"ZEUS CORE": z, **ag})
    c = TestClient(app)
    try:
        yield c
    finally:
        app.dependency_overrides.clear()


def _user(db, company=None, with_company=True, superuser=False, active=True):
    suf = uuid.uuid4().hex[:8]
    if with_company and company is None:
        company = Company(company_name=f"J5 {suf}", slug=f"j5-{suf}")
        db.add(company)
        db.flush()
    u = User(email=f"j5_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
             full_name="J5", is_active=active, is_superuser=superuser)
    db.add(u)
    db.flush()
    if with_company:
        db.add(UserCompany(user_id=u.id, company_id=company.id, role="owner"))
    db.commit()
    db.refresh(u)
    return u, company


def _as(user):
    app.dependency_overrides[get_current_active_user] = lambda: user


def _events(db, user, event_type="request_guard"):
    db.expire_all()
    return (db.query(ThalosSecurityEvent)
            .filter(ThalosSecurityEvent.user_id == user.id, ThalosSecurityEvent.event_type == event_type)
            .order_by(ThalosSecurityEvent.id).all())


def _comm(c, message="hola"):
    return c.post(COMM, json={"from_agent": "PERSEO", "to_agent": "RAFAEL", "message": message})


# ------------------------------------------------------------------ guard entrada


def test_valid_request_records_allow_event_with_tenant(db, client):
    u, co = _user(db)
    _as(u)
    r = _comm(client)
    assert r.status_code == 200, r.text
    ev = _events(db, u)
    assert len(ev) == 1 and ev[0].action_taken == "allow"
    assert ev[0].company_id == co.id and ev[0].user_email == u.email
    d = json.loads(ev[0].details_json)
    assert d["route"].endswith("/agents/communicate") and d["decision"] == "allow"


def test_message_too_long_denied_and_logged(db, client):
    u, co = _user(db)
    _as(u)
    r = _comm(client, "x" * (MAX_MESSAGE_CHARS + 1))
    assert r.status_code == 413
    ev = _events(db, u)
    assert ev[-1].action_taken == "deny" and ev[-1].decision_rule == "message_too_long"
    assert ev[-1].company_id == co.id


def test_control_chars_denied_and_logged(db, client):
    u, _ = _user(db)
    _as(u)
    r = client.post(CHAT, json={"message": "hola\x00mundo"})
    assert r.status_code == 400
    ev = _events(db, u)
    assert ev[-1].action_taken == "deny" and ev[-1].decision_rule == "control_characters"


def test_control_chars_in_nested_context_denied(db, client):
    u, _ = _user(db)
    _as(u)
    r = client.post(CHAT, json={"message": "ok", "context": {"a": ["b\x07"]}})
    assert r.status_code == 400


def test_context_too_large_denied(db, client):
    u, _ = _user(db)
    _as(u)
    r = client.post(CHAT, json={"message": "ok", "context": {"k": "y" * 25000}})
    assert r.status_code == 413
    assert _events(db, u)[-1].decision_rule == "context_too_large"


def test_newlines_and_tabs_allowed(db, client):
    u, _ = _user(db)
    _as(u)
    assert _comm(client, "linea1\nlinea2\tfin").status_code == 200


def test_user_without_company_403_and_event(db, client):
    u, _ = _user(db, with_company=False)
    _as(u)
    r = _comm(client)
    assert r.status_code == 403
    ev = _events(db, u)
    assert ev[-1].action_taken == "deny" and ev[-1].decision_rule == "no_company"
    assert ev[-1].company_id is None


def test_blocked_inactive_user_403_and_event(db, client):
    u, co = _user(db, active=False)  # estado real de bloqueo THALOS: block_user -> is_active False
    _as(u)
    r = _comm(client)
    assert r.status_code == 403
    ev = _events(db, u)
    assert ev[-1].decision_rule == "user_inactive"


def test_superuser_without_company_not_denied_for_missing_company(db, client):
    u, _ = _user(db, with_company=False, superuser=True)
    _as(u)
    r = client.post(CHAT, json={"message": "hola\x00"})  # deny por contenido, no por empresa
    assert r.status_code == 400
    assert _events(db, u)[-1].decision_rule == "control_characters"


def test_guard_runs_with_default_flags(db, client):
    from app.core.config import settings

    assert settings.THALOS_AUTO_BLOCK is False  # flags por defecto
    u, _ = _user(db)
    _as(u)
    assert _comm(client).status_code == 200
    assert _events(db, u)


def test_six_endpoints_have_guard():
    wanted = {
        ("POST", "/api/v1/chat/{agent_name}/chat"),
        ("POST", "/api/v1/teamflow/execute-from-chat"),
        ("POST", "/api/v1/chat/agents/communicate"),
        ("POST", "/api/v1/chat/agents/coordinate"),
        ("POST", "/api/v1/zeus-core/agent/execute"),
        ("POST", "/api/v1/zeus-core/approvals/{approval_id}/resolve"),
    }

    def _calls(dep):
        yield dep.call
        for d in dep.dependencies:
            yield from _calls(d)

    found = set()
    for route in app.routes:
        methods = getattr(route, "methods", None) or set()
        path = getattr(route, "path", "")
        for m in methods:
            if (m, path) in wanted:
                found.add((m, path))
                assert thalos_request_guard in set(_calls(route.dependant)), (m, path)
    assert found == wanted, wanted - found


# ----------------------------------------------------------------- auditoria post


def _res(**kw):
    base = {"success": True, "executed": True, "message": "hecho"}
    base.update(kw)
    return base


def test_audit_pass_records_event_and_activity(db):
    u, co = _user(db)
    v = thalos_audit_result(db, user=u, company_id=co.id, agent="ZEUS", action="create_customer", result=_res())
    assert v == {"ok": True, "reason": "ok"}
    ev = _events(db, u, "post_action_audit")
    assert ev[-1].action_taken == "audit_pass" and ev[-1].company_id == co.id
    db.expire_all()
    act = (db.query(AgentActivity)
           .filter(AgentActivity.agent_name == "THALOS", AgentActivity.action_type == "thalos_audit_result",
                   AgentActivity.user_email == u.email).first())
    assert act is not None and act.status == "completed"


@pytest.mark.parametrize("result,reason", [
    (_res(company_id=999999), "tenant_mismatch_result"),
    (_res(data={"company_id": 999999}), "tenant_mismatch_result"),
    (_res(execution_mode="simulated"), "simulated_or_blocked"),
    (_res(executed=False), "not_executed"),
    (_res(success=False), "not_executed"),
    ({}, "empty_result"),
])
def test_audit_failures(db, result, reason):
    u, co = _user(db)
    v = thalos_audit_result(db, user=u, company_id=co.id, agent="ZEUS", action="create_customer", result=result)
    assert v["ok"] is False and v["reason"] == reason
    assert _events(db, u, "post_action_audit")[-1].action_taken == "audit_fail"


def test_audit_simulated_action_name_fails(db):
    u, co = _user(db)
    v = thalos_audit_result(db, user=u, company_id=co.id, agent="ZEUS", action="image_analyzer", result=_res())
    assert v["reason"] == "simulated_or_blocked"


def test_audit_tenant_of_other_company_fails(db):
    u, _ = _user(db)
    _, other = _user(db)
    v = thalos_audit_result(db, user=u, company_id=other.id, agent="ZEUS", action="x", result=_res())
    assert v["reason"] == "tenant_mismatch_user"


def test_execute_approval_audit_ok_executed(db, client, monkeypatch):
    u, co = _user(db)

    async def fake(db_, **kw):
        return _res(company_id=co.id)

    monkeypatch.setattr("services.zeus_agent_executor_v1.execute_agent_action", fake)
    row = request_approval(db, user=u, company_id=co.id, agent_name="RAFAEL",
                           action_type="generate_invoice", payload={"invoice_id": 1})
    _as(u)
    r = client.post(RESOLVE.format(row.id), json={"approve": True})
    assert r.status_code == 200 and r.json()["success"] is True
    db.expire_all()
    assert db.get(ZeusPendingApproval, row.id).status == "executed"
    assert _events(db, u, "post_action_audit")[-1].action_taken == "audit_pass"


@pytest.mark.parametrize("bad", [
    {"success": True, "executed": True, "company_id": 424242, "message": "hecho", "secret": "otra-empresa"},
    {"success": True, "executed": False, "execution_mode": "simulated", "message": "simulado"},
])
def test_execute_approval_audit_failure_not_executed(db, client, monkeypatch, bad):
    u, co = _user(db)

    async def fake(db_, **kw):
        return dict(bad)

    monkeypatch.setattr("services.zeus_agent_executor_v1.execute_agent_action", fake)
    row = request_approval(db, user=u, company_id=co.id, agent_name="RAFAEL",
                           action_type="generate_invoice", payload={"invoice_id": 1})
    _as(u)
    r = client.post(RESOLVE.format(row.id), json={"approve": True})
    assert r.status_code == 422
    body = r.json()
    assert body["success"] is False and body["status"] == "failed"
    assert "otra-empresa" not in r.text
    db.expire_all()
    assert db.get(ZeusPendingApproval, row.id).status == "failed"
    assert _events(db, u, "post_action_audit")[-1].action_taken == "audit_fail"
