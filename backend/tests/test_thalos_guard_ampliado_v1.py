"""J5b: guard THALOS ampliado, company_id real en la auditoria del chat y estado audit_failed.
Sin LLM ni red."""

from __future__ import annotations

import asyncio
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_active_user
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.company import Company, UserCompany
from app.models.thalos_security_event import ThalosSecurityEvent
from app.models.user import User
from app.models.zeus_pending_approval import ZeusPendingApproval
from services import zeus_orchestrator_service as orch
from services.thalos_request_guard_v1 import thalos_request_guard
from services.zeus_human_approval_v1 import request_approval

RESOLVE = "/api/v1/zeus-core/approvals/{}/resolve"
CMD = "/api/v1/commands/execute"


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
    c = TestClient(app)
    try:
        yield c
    finally:
        app.dependency_overrides.clear()


def _user(db, superuser=False, with_company=True, company=None):
    suf = uuid.uuid4().hex[:8]
    if with_company and company is None:
        company = Company(company_name=f"J5b {suf}", slug=f"j5b-{suf}")
        db.add(company)
        db.flush()
    u = User(email=f"j5b_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
             full_name="J5b", is_active=True, is_superuser=superuser)
    db.add(u)
    db.flush()
    if with_company:
        db.add(UserCompany(user_id=u.id, company_id=company.id, role="owner"))
    db.commit()
    db.refresh(u)
    return u, company


def _as(user):
    app.dependency_overrides[get_current_active_user] = lambda: user


def _events(db, user, event_type):
    db.expire_all()
    return (db.query(ThalosSecurityEvent)
            .filter(ThalosSecurityEvent.user_id == user.id, ThalosSecurityEvent.event_type == event_type)
            .order_by(ThalosSecurityEvent.id).all())


# ------------------------------------------------------------------ rutas con guard


def _calls(dep):
    yield dep.call
    for d in dep.dependencies:
        yield from _calls(d)


def test_added_routes_have_guard():
    wanted = {
        ("POST", "/api/v1/commands/execute"),
        ("POST", "/api/v1/teamflow/workflows/{workflow_id}/run"),
        ("POST", "/api/v1/thalos/v1/execute"),
        ("POST", "/api/v1/documents/approve"),
        ("POST", "/api/v1/zeus/transactions/{transaction_id}/execute"),
        ("POST", "/api/v1/actions/execute"),
        ("POST", "/api/v1/justice/sign"),
        ("POST", "/api/v1/perseo/v2/ads/create"),
        ("POST", "/api/v1/integrations/whatsapp/send"),
        ("POST", "/api/v1/integrations/email/send"),
    }
    found = set()
    for route in app.routes:
        path = getattr(route, "path", "")
        for m in getattr(route, "methods", None) or set():
            if (m, path) in wanted:
                found.add((m, path))
                assert thalos_request_guard in set(_calls(route.dependant)), (m, path)
    assert found == wanted, wanted - found


def test_commands_execute_no_longer_uses_local_get_current_user():
    from app.api.v1.endpoints import commands as cmd

    seen = False
    for route in app.routes:
        if getattr(route, "path", "") == CMD:
            seen = True
            assert cmd.get_current_user not in set(_calls(route.dependant))
    assert seen


# ------------------------------------------------------------------ commands/execute


def test_commands_execute_requires_auth(client):
    r = client.post(CMD, json={"command": "estado"})
    assert r.status_code == 401


def test_commands_execute_regular_user_403(db, client):
    u, _ = _user(db)
    _as(u)
    r = client.post(CMD, json={"command": "estado"})
    assert r.status_code == 403
    assert _events(db, u, "request_guard")  # el guard corrio antes de la comprobacion de rol


def test_commands_execute_superuser_estado_ok_and_event(db, client):
    u, _ = _user(db, superuser=True, with_company=False)
    _as(u)
    r = client.post(CMD, json={"command": "estado"})
    assert r.status_code == 200 and r.json()["status"] == "success"
    assert _events(db, u, "request_guard")[-1].action_taken == "allow"


def test_commands_execute_unknown_command_is_400_not_500(db, client):
    u, _ = _user(db, superuser=True, with_company=False)
    _as(u)
    r = client.post(CMD, json={"command": "comando-inexistente"})
    assert r.status_code == 400 and "no reconocido" in r.json()["detail"]


def test_commands_execute_activar_empty_is_400(db, client):
    u, _ = _user(db, superuser=True, with_company=False)
    _as(u)
    r = client.post(CMD, json={"command": "activar:"})
    assert r.status_code == 400


def test_commands_execute_guard_denies_control_chars(db, client):
    u, _ = _user(db, superuser=True, with_company=False)
    _as(u)
    r = client.post(CMD, json={"command": "estado\u0000"})
    assert r.status_code == 400
    assert _events(db, u, "request_guard")[-1].action_taken == "deny"


def test_guard_non_json_body_is_not_rejected_as_invalid_json(db, client):
    u, _ = _user(db, superuser=True, with_company=False)
    _as(u)
    r = client.post(CMD, content=b"--x\r\nContent-Disposition: form-data; name=a\r\n\r\nb\r\n--x--\r\n",
                    headers={"content-type": "multipart/form-data; boundary=x"})
    assert r.status_code == 422  # lo rechaza FastAPI por forma, no el guard como invalid_json
    assert _events(db, u, "request_guard")[-1].action_taken == "allow"


def test_guarded_added_route_denies_user_without_company(db, client):
    u, _ = _user(db, with_company=False)
    _as(u)
    r = client.post("/api/v1/zeus/transactions/abc/execute")
    assert r.status_code == 403
    assert _events(db, u, "request_guard")[-1].action_taken == "deny"


# --------------------------------------------------- auditoria de tenant, rama directa


def test_execute_action_fills_company_id(db):
    from app.schemas.zeus_action import ZeusAction

    u, co = _user(db)
    action = ZeusAction(action_type="list_customers", user_id=u.id, company_id=None, payload={})
    res = asyncio.run(orch.execute_action(db, u, action))
    assert res.company_id == co.id


def _direct_chat(db, monkeypatch, result_company):
    from app.schemas.zeus_task import ZeusExecutionResult

    u, co = _user(db)

    async def fake_exec(db_, user, action, *, force_execute=False):
        return ZeusExecutionResult(success=True, intent="list_customers_summary", message="Tienes 3 clientes",
                                   executed=True, company_id=result_company(co))

    monkeypatch.setattr(orch, "execute_action", fake_exec)
    out = asyncio.run(orch.try_handle_zeus_chat(db, u, "cuantos clientes tengo"))
    return u, co, out


def test_direct_branch_audit_passes_with_own_company(db, monkeypatch):
    u, co, out = _direct_chat(db, monkeypatch, lambda c: c.id)
    assert out and out["success"] is True and out["executed"] is True
    assert _events(db, u, "post_action_audit")[-1].action_taken == "audit_pass"


def test_direct_branch_audit_fails_with_foreign_company(db, monkeypatch):
    u, co, out = _direct_chat(db, monkeypatch, lambda c: c.id + 100000)
    assert out["success"] is False and out["executed"] is False
    assert "tenant_mismatch_result" in out["message"]
    assert "Tienes 3 clientes" not in json.dumps(out)
    ev = _events(db, u, "post_action_audit")[-1]
    assert ev.action_taken == "audit_fail" and ev.severity == "critical"


# ------------------------------------------------------------------ audit_failed


def _approval(db, u, co):
    return request_approval(db, user=u, company_id=co.id, agent_name="RAFAEL",
                            action_type="generate_invoice", payload={"invoice_id": 1})


def _foreign_result(*a, **k):
    return {"success": True, "executed": True, "company_id": 424242, "message": "hecho", "secret": "otra-empresa"}


def test_audit_failed_state_after_real_execution(db, client, monkeypatch):
    u, co = _user(db)
    calls = {"n": 0}

    async def fake(db_, **kw):
        calls["n"] += 1
        return _foreign_result()

    monkeypatch.setattr("services.zeus_agent_executor_v1.execute_agent_action", fake)
    row = _approval(db, u, co)
    _as(u)
    r = client.post(RESOLVE.format(row.id), json={"approve": True})
    assert r.status_code == 422
    body = r.json()
    assert body["status"] == "audit_failed" and body["success"] is False
    assert "pudo producirse" in body["error"] and "no se ha podido verificar" in body["error"]
    assert "otra-empresa" not in r.text and body.get("result") is None
    db.expire_all()
    stored = db.get(ZeusPendingApproval, row.id)
    assert stored.status == "audit_failed"
    saved = json.loads(stored.result_json)
    assert saved["unverified"] is True and saved["unverified_result"]["secret"] == "otra-empresa"
    crit = _events(db, u, "audit_failed_after_execution")
    assert crit and crit[-1].severity == "critical" and crit[-1].company_id == co.id
    # sin doble ejecucion
    r2 = client.post(RESOLVE.format(row.id), json={"approve": True})
    assert r2.status_code == 409
    assert calls["n"] == 1


def test_not_executed_remains_failed(db, client, monkeypatch):
    u, co = _user(db)

    async def fake(db_, **kw):
        return {"success": True, "executed": False, "execution_mode": "simulated", "message": "simulado"}

    monkeypatch.setattr("services.zeus_agent_executor_v1.execute_agent_action", fake)
    row = _approval(db, u, co)
    _as(u)
    r = client.post(RESOLVE.format(row.id), json={"approve": True})
    assert r.json()["status"] == "failed"
    assert not _events(db, u, "audit_failed_after_execution")


def test_audit_exception_after_execution_is_audit_failed(db, client, monkeypatch):
    u, co = _user(db)

    async def fake(db_, **kw):
        return {"success": True, "executed": True, "message": "hecho"}

    def boom(*a, **k):
        raise RuntimeError("audit down")

    monkeypatch.setattr("services.zeus_agent_executor_v1.execute_agent_action", fake)
    monkeypatch.setattr("services.thalos_request_guard_v1.thalos_audit_result", boom)
    row = _approval(db, u, co)
    _as(u)
    r = client.post(RESOLVE.format(row.id), json={"approve": True})
    assert r.json()["status"] == "audit_failed"


def test_audit_failed_not_listed_as_pending(db, client, monkeypatch):
    from services.zeus_human_approval_v1 import list_pending

    u, co = _user(db)

    async def fake(db_, **kw):
        return _foreign_result()

    monkeypatch.setattr("services.zeus_agent_executor_v1.execute_agent_action", fake)
    row = _approval(db, u, co)
    _as(u)
    client.post(RESOLVE.format(row.id), json={"approve": True})
    assert row.id not in [p["id"] for p in list_pending(db, user=u, company_id=co.id)]


def test_chat_confirmation_message_for_audit_failed(db, monkeypatch):
    u, co = _user(db)

    async def fake(db_, **kw):
        return _foreign_result()

    monkeypatch.setattr("services.zeus_agent_executor_v1.execute_agent_action", fake)
    row = _approval(db, u, co)
    out = asyncio.run(orch._confirm_pending(db, u, row))
    assert out["success"] is False and out["executed"] is False and out["status"] == "audit_failed"
    assert "pudo producirse" in out["message"] and "otra-empresa" not in json.dumps(out)
