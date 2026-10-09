"""J7: cada paso de la cadena JARVIS deja fila real en agent_activities, con empresa, usuario,
agente, accion, status real y un correlation_id comun por peticion (devuelto como request_id).
Solo se sustituye el envio externo de email y la llamada al modelo."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.auth import get_current_active_user
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.agent_activity import AgentActivity
from app.models.company import Company, UserCompany
from app.models.customer import Customer
from app.models.user import User
from services import activity_logger as al
from services import zeus_orchestrator_service as orch

ZEUS = "/api/v1/chat/ZEUS CORE/chat"
RAFAEL = "/api/v1/chat/RAFAEL/chat"
CAMPAIGN = "crea una oferta del 10% y envíala a los clientes"


@pytest.fixture()
def db():
    from app.db.base import _migrate_zeus_approvals_chat_columns, _migrate_zeus_approvals_execution_columns

    Base.metadata.create_all(bind=engine)
    _migrate_zeus_approvals_execution_columns()
    _migrate_zeus_approvals_chat_columns()
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


@pytest.fixture()
def sent(monkeypatch):
    calls = []

    async def _send(to_email, subject, content, content_type="text/html", **kw):
        calls.append(to_email)
        return {"success": True}

    es = orch.handlers.email_service
    monkeypatch.setattr(es, "is_configured", lambda: True)
    monkeypatch.setattr(es, "send_email", _send)
    return calls


def _seed(db):
    suf = uuid.uuid4().hex[:8]
    co = Company(company_name=f"J7 {suf}", slug=f"j7-{suf}")
    db.add(co)
    db.flush()
    db.add(Customer(name="Cli", email=f"cli_{suf}@example.test", company_id=co.id))
    u = User(email=f"j7_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
             full_name="J7", is_active=True)
    db.add(u)
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=co.id, role="owner"))
    db.commit()
    db.refresh(u)
    db.refresh(co)
    return u, co


def _chat(client, user, message, url=ZEUS, thread="main", context=None):
    app.dependency_overrides[get_current_active_user] = lambda: user
    r = client.post(url, json={"message": message, "thread_id": thread, "context": context or {}})
    assert r.status_code == 200, r.text
    return r.json()


def _rows(db, user, correlation_id):
    db.expire_all()
    rows = db.query(AgentActivity).filter(AgentActivity.user_email == user.email).all()
    return [r for r in rows if (r.details or {}).get("correlation_id") == correlation_id]


def _by_step(rows):
    out = {}
    for r in rows:
        out.setdefault(r.details["chain_step"], []).append(r)
    return out


def test_confirmable_action_leaves_full_chain_with_same_correlation(db, client, sent):
    user, co = _seed(db)
    thread = "t-" + uuid.uuid4().hex[:6]
    first = _chat(client, user, CAMPAIGN, thread=thread)
    assert first["needs_confirmation"] is True and first["request_id"]
    rows = _rows(db, user, first["request_id"])
    steps = _by_step(rows)
    for s in ("ESCUCHAR", "COMPRENDER", "CONTEXTO", "ORQUESTAR", "RESPONDER", "CONTINUAR"):
        assert s in steps, (s, sorted(steps))
    assert all(r.company_id == co.id and r.user_email == user.email for r in rows)
    assert steps["ESCUCHAR"][0].status == "success"
    comp = [r for r in steps["COMPRENDER"] if r.details["action"] == "parse_intent"][0]
    assert comp.details["intent"] and comp.details["confidence"] > 0
    orq = [r for r in steps["ORQUESTAR"] if r.details["action"] == "send_campaign"][0]
    assert orq.status == "needs_confirmation" and orq.details["approval_id"] == first["approval_id"]
    assert steps["RESPONDER"][0].status == "needs_confirmation"
    assert steps["CONTINUAR"][0].details["approval_id"] == first["approval_id"]
    ctxrow = steps["CONTEXTO"][0]
    assert "modules" in ctxrow.details and "message" not in ctxrow.details

    second = _chat(client, user, "confirmar", thread=thread)
    assert second["executed_action"] is True and second["request_id"] != first["request_id"]
    rows2 = _rows(db, user, second["request_id"])
    steps2 = _by_step(rows2)
    for s in ("ESCUCHAR", "CONTEXTO", "ORQUESTAR", "ACTUAR", "AUDITAR", "RESPONDER"):
        assert s in steps2, (s, sorted(steps2))
    assert steps2["ACTUAR"][0].details["action"] == "approval_executed"
    assert steps2["ACTUAR"][0].status == "completed"
    assert steps2["AUDITAR"][0].details["verdict"] == "pass"
    assert steps2["RESPONDER"][0].status == "success"
    assert all(r.company_id == co.id and r.user_email == user.email for r in rows2)
    assert second.get("warnings") in (None, [])


def test_failed_agent_leaves_failed_status_and_request_id(db, client, monkeypatch):
    user, co = _seed(db)

    def _boom(messages, **kw):
        raise RuntimeError("modelo caido")

    monkeypatch.setattr("agents.base_agent.chat_completion", _boom)
    body = _chat(client, user, "hola rafael")
    assert body["success"] is False and body["request_id"]
    steps = _by_step(_rows(db, user, body["request_id"]))
    assert steps["ACTUAR"][0].status == "failed"
    assert steps["RESPONDER"][0].status == "failed"
    assert steps["ESCUCHAR"][0].company_id == co.id


def test_exception_in_run_chat_is_logged_failed(db, client, monkeypatch):
    user, _ = _seed(db)

    def _raise(*a, **k):
        raise RuntimeError("fallo duro")

    monkeypatch.setattr("services.unified_agent_runtime.run_chat", _raise)
    body = _chat(client, user, "hola", url=RAFAEL)
    assert body["success"] is False and body["request_id"]
    act = _by_step(_rows(db, user, body["request_id"]))["ACTUAR"][0]
    assert act.action_type == "chat_request_exception" and act.status == "failed"


def test_two_companies_do_not_share_correlation_or_company(db, client, sent):
    ua, ca = _seed(db)
    ub, cb = _seed(db)
    ra = _chat(client, ua, CAMPAIGN)
    rb = _chat(client, ub, CAMPAIGN)
    assert ra["request_id"] != rb["request_id"]
    rows_a, rows_b = _rows(db, ua, ra["request_id"]), _rows(db, ub, rb["request_id"])
    assert rows_a and rows_b
    assert {r.company_id for r in rows_a} == {ca.id}
    assert {r.company_id for r in rows_b} == {cb.id}
    # ninguna fila de A lleva el correlation de B y viceversa
    assert not _rows(db, ua, rb["request_id"]) and not _rows(db, ub, ra["request_id"])


def test_full_message_is_not_stored_only_masked_preview(db, client, monkeypatch):
    user, _ = _seed(db)
    monkeypatch.setattr("agents.base_agent.chat_completion", lambda m, **k: {
        "success": True, "content": "ok", "model": "stub", "usage": {"total_tokens": 1},
        "cost": 0.0, "elapsed_time": 0.0, "timestamp": "2026-01-01T00:00:00"})
    secret = "mi dni es 12345678 y mi correo secreto.persona@example.test " + "x" * 200
    body = _chat(client, user, secret, url=RAFAEL, context={"channel": "voice"})
    esc = _by_step(_rows(db, user, body["request_id"]))["ESCUCHAR"][0]
    assert esc.details["channel"] == "voice" and esc.details["message_len"] == len(secret)
    prev = esc.details["message_preview"]
    assert "12345678" not in prev and "secreto.persona" not in prev and len(prev) <= 63
    assert secret not in str(esc.details)
    _chat(client, user, "x", url=RAFAEL, context={"channel": "<script>"})  # canal fuera de lista -> text
    bad = _chat(client, user, "y", url=RAFAEL, context={"channel": "<script>"})
    assert _by_step(_rows(db, user, bad["request_id"]))["ESCUCHAR"][0].details["channel"] == "text"


def test_actuar_logging_failure_is_surfaced_as_warning(db, client, sent, monkeypatch):
    user, _ = _seed(db)
    thread = "w-" + uuid.uuid4().hex[:6]
    _chat(client, user, CAMPAIGN, thread=thread)
    real = al.ActivityLogger.log_activity

    def _flaky(*a, **kw):
        if kw.get("action_type") == "approval_executed":
            return None  # el logger falla en silencio, como hoy
        return real(*a, **kw)

    monkeypatch.setattr(al.ActivityLogger, "log_activity", staticmethod(_flaky))
    body = _chat(client, user, "confirmar", thread=thread)
    assert body["executed_action"] is True
    assert body["warnings"] and "ACTUAR" in body["warnings"][0]


def test_no_such_table_retry_keeps_company_id(db, monkeypatch):
    user, co = _seed(db)
    real_factory = al.SessionLocal
    calls = {"n": 0}

    class _Broken:
        def query(self, *a, **k):
            raise AssertionError("no debe inferir")

        def add(self, *a, **k):
            raise OperationalError("INSERT", {}, Exception("no such table: agent_activities"))

        def rollback(self):
            pass

        def close(self):
            pass

    def _factory():
        calls["n"] += 1
        return _Broken() if calls["n"] == 1 else real_factory()

    monkeypatch.setattr(al, "SessionLocal", _factory)
    tag = uuid.uuid4().hex
    row = al.ActivityLogger.log_activity(
        "ZEUS CORE", "j7_retry", "retry", details={"tag": tag}, user_email=user.email,
        company_id=co.id, infer_company=False)
    assert calls["n"] == 2 and row is not None and row.company_id == co.id


def _fake_activity(**kw):
    a = AgentActivity(agent_name="PERSEO", action_type="j7_task", action_description="t",
                      details={}, status="pending", **kw)
    a.id = 987654
    return a


def test_workspace_task_without_company_is_controlled_error_not_default(db, monkeypatch):
    from services import unified_agent_runtime as rt

    keys = []
    monkeypatch.setattr(rt, "memory_load", lambda c, a, t: keys.append(c) or {})
    monkeypatch.setattr(rt, "resolve_handler", lambda a, t: (lambda act: {"status": "completed"}))
    email = f"nadie_{uuid.uuid4().hex[:6]}@example.test"
    res = rt.run_workspace_task(_fake_activity(user_email=email))
    assert res["status"] == "blocked_no_company" and res["executed_handler"] is None
    assert keys == []  # no se toco la memoria ni se ejecuto handler
    row = (db.query(AgentActivity).filter(AgentActivity.user_email == email,
                                          AgentActivity.action_type == "workspace_task_blocked").first())
    assert row is not None and row.company_id is None and row.status == "blocked_no_company"
    # un usuario sin empresa tampoco se resuelve por email
    u = User(email=f"sinco_{uuid.uuid4().hex[:6]}@example.test",
             hashed_password=get_password_hash("TestPass1"), full_name="x", is_active=True)
    db.add(u)
    db.commit()
    assert rt.run_workspace_task(_fake_activity(user_email=u.email))["status"] == "blocked_no_company"
    assert "default" not in keys


def test_workspace_task_resolves_company_from_activity_or_user(db, monkeypatch):
    from services import unified_agent_runtime as rt

    keys = []
    monkeypatch.setattr(rt, "memory_load", lambda c, a, t: keys.append(c) or {})
    monkeypatch.setattr(rt, "resolve_handler", lambda a, t: (lambda act: {"status": "completed"}))
    monkeypatch.setattr(rt, "persist_operational_state", lambda *a, **k: None)
    monkeypatch.setattr(rt, "append_decision_log", lambda *a, **k: None)
    user, co = _seed(db)
    assert rt.run_workspace_task(_fake_activity(user_email=user.email))["status"] == "completed"
    assert rt.run_workspace_task(_fake_activity(user_email=None, company_id=co.id))["status"] == "completed"
    assert keys == [str(co.id), str(co.id)]


def test_client_log_activity_still_blocked_by_executor(db):
    """J3c intacto: una actividad con _origin=client_log no se ejecuta."""
    from services.automation.agent_executor import AgentAutomationExecutor

    user, co = _seed(db)
    act = AgentActivity(agent_name="PERSEO", action_type="j7_x", action_description="x",
                        details={"_origin": "client_log"}, status="pending",
                        user_email=user.email, company_id=co.id)
    db.add(act)
    db.commit()
    AgentAutomationExecutor()._handle_activity(db, act)
    db.refresh(act)
    assert act.status == "blocked_client_origin"
