"""J4: /chat/agents/communicate y /coordinate. Identidad/empresa/control los fija el servidor;
THALOS solo superusuario; sin empresa -> 403; agente desconocido -> 404; log con status real.
Agentes sustituidos por stubs que capturan el contexto (sin LLM ni red)."""

from __future__ import annotations

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
from app.models.user import User

COMM = "/api/v1/chat/agents/communicate"
COORD = "/api/v1/chat/agents/coordinate"
HOSTILE = {
    "user_id": 999999, "company_id": 999999, "tenant_id": 999999, "user_email": "evil@x.test",
    "workflow_id": "wf-evil", "requested_by": "evil@x.test", "task_type": "x", "phase": "x",
    "force_execute": True, "from_agent": "EVIL", "inter_agent_communication": False,
    "multi_agent_task": False, "other_agents": ["EVIL"], "_memory": {"x": 1},
    "image_url": "http://ok.test/a.png",
}


class StubAgent:
    def __init__(self, name, result=None, boom=False):
        self.name = name
        self.seen = []
        self._result = result if result is not None else {"success": True, "content": "ok"}
        self._boom = boom

    def set_zeus_core_ref(self, z):
        pass

    def process_request(self, ctx):
        self.seen.append(dict(ctx))
        if self._boom:
            raise RuntimeError("secreto-interno-xyz")
        return dict(self._result)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def stack(monkeypatch):
    z = ZeusCore()
    ag = {n: StubAgent(n) for n in ("PERSEO", "RAFAEL", "THALOS", "JUSTICIA", "AFRODITA")}
    for a in ag.values():
        z.register_agent(a)
    monkeypatch.setattr(chat_endpoint, "ensure_agent_stack", lambda: None)
    monkeypatch.setattr(chat_endpoint, "zeus", z)
    monkeypatch.setattr(chat_endpoint, "AGENTS", {"ZEUS CORE": z, **ag})
    c = TestClient(app)
    try:
        yield c, ag
    finally:
        app.dependency_overrides.clear()


def _user(db, company=None, with_company=True, superuser=False):
    suf = uuid.uuid4().hex[:8]
    if with_company and company is None:
        company = Company(company_name=f"J4 {suf}", slug=f"j4-{suf}")
        db.add(company)
        db.flush()
    u = User(email=f"j4_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
             full_name="J4", is_active=True, is_superuser=superuser)
    db.add(u)
    db.flush()
    if with_company:
        db.add(UserCompany(user_id=u.id, company_id=company.id, role="owner"))
    db.commit()
    db.refresh(u)
    return u, company


def _as(user):
    app.dependency_overrides[get_current_active_user] = lambda: user


def _last_log(db, action, email):
    db.expire_all()
    return (db.query(AgentActivity).filter(AgentActivity.action_type == action,
            AgentActivity.user_email == email).order_by(AgentActivity.id.desc()).first())


def test_communicate_server_fixes_identity(db, stack):
    c, ag = stack
    u, co = _user(db)
    _as(u)
    r = c.post(COMM, json={"from_agent": "PERSEO", "to_agent": "RAFAEL", "message": "hola", "context": HOSTILE})
    assert r.status_code == 200, r.text
    ctx = ag["RAFAEL"].seen[0]
    assert ctx["user_id"] == u.id and ctx["company_id"] == co.id and ctx["user_email"] == u.email
    assert ctx["requested_by"] == u.email
    assert "workflow_id" not in ctx and "task_type" not in ctx and "phase" not in ctx
    assert "force_execute" not in ctx and "_memory" not in ctx and "tenant_id" not in ctx
    assert ctx["from_agent"] == "PERSEO" and ctx["inter_agent_communication"] is True
    assert ctx["image_url"] == "http://ok.test/a.png"
    log = _last_log(db, "agents_communicate", u.email)
    assert log is not None and log.status == "completed" and log.company_id == co.id


def test_coordinate_server_fixes_identity_and_no_workflow(db, stack, monkeypatch):
    c, ag = stack
    called = []
    monkeypatch.setattr(chat_endpoint.zeus, "teamflow_engine",
                        type("E", (), {"run_workflow": lambda *a, **k: called.append(k)})())
    u, co = _user(db)
    _as(u)
    r = c.post(COORD, json={"task_description": "t", "required_agents": ["perseo", "rafael"], "context": HOSTILE})
    assert r.status_code == 200, r.text
    assert called == []  # el cliente no puede lanzar workflows
    for n in ("PERSEO", "RAFAEL"):
        ctx = ag[n].seen[0]
        assert ctx["user_id"] == u.id and ctx["company_id"] == co.id
        assert ctx["requested_by"] == u.email and "workflow_id" not in ctx
        assert ctx["multi_agent_task"] is True and "EVIL" not in ctx["other_agents"]
    assert _last_log(db, "agents_coordinate", u.email).status == "completed"


def test_no_company_is_403_and_agent_not_called(db, stack):
    c, ag = stack
    u, _ = _user(db, with_company=False)
    _as(u)
    r = c.post(COMM, json={"from_agent": "PERSEO", "to_agent": "RAFAEL", "message": "x"})
    assert r.status_code == 403
    r = c.post(COORD, json={"task_description": "t", "required_agents": ["RAFAEL"]})
    assert r.status_code == 403
    assert ag["RAFAEL"].seen == []


def test_thalos_requires_superuser(db, stack):
    c, ag = stack
    u, _ = _user(db)
    _as(u)
    assert c.post(COMM, json={"from_agent": "PERSEO", "to_agent": "THALOS", "message": "x"}).status_code == 403
    assert c.post(COORD, json={"task_description": "t", "required_agents": ["PERSEO", "thalos"]}).status_code == 403
    assert ag["THALOS"].seen == [] and ag["PERSEO"].seen == []
    su, _ = _user(db, superuser=True)
    _as(su)
    assert c.post(COMM, json={"from_agent": "PERSEO", "to_agent": "THALOS", "message": "x"}).status_code == 200
    assert len(ag["THALOS"].seen) == 1


def test_unknown_agent_404(db, stack):
    c, ag = stack
    u, _ = _user(db)
    _as(u)
    assert c.post(COMM, json={"from_agent": "PERSEO", "to_agent": "NOPE", "message": "x"}).status_code == 404
    assert c.post(COMM, json={"from_agent": "NOPE", "to_agent": "RAFAEL", "message": "x"}).status_code == 404
    assert c.post(COORD, json={"task_description": "t", "required_agents": ["PERSEO", "NOPE"]}).status_code == 404
    assert c.post(COORD, json={"task_description": "t", "required_agents": []}).status_code == 422
    assert ag["PERSEO"].seen == []


def test_agent_failure_logs_failed_without_leak(db, stack):
    c, ag = stack
    ag["RAFAEL"]._boom = True
    u, co = _user(db)
    _as(u)
    r = c.post(COMM, json={"from_agent": "PERSEO", "to_agent": "RAFAEL", "message": "x"})
    assert r.status_code == 500 and "secreto-interno" not in r.text
    log = _last_log(db, "agents_communicate", u.email)
    assert log.status == "failed" and log.company_id == co.id
    r = c.post(COORD, json={"task_description": "t", "required_agents": ["RAFAEL"]})
    assert r.status_code == 500 and "secreto-interno" not in r.text
    assert _last_log(db, "agents_coordinate", u.email).status == "failed"


def test_unsuccessful_result_logs_failed(db, stack):
    c, ag = stack
    ag["PERSEO"]._result = {"success": False, "error": "x"}
    u, _ = _user(db)
    _as(u)
    r = c.post(COORD, json={"task_description": "t", "required_agents": ["PERSEO"]})
    assert r.status_code == 200
    assert _last_log(db, "agents_coordinate", u.email).status == "failed"


def test_cross_tenant_each_user_gets_own_identity(db, stack):
    c, ag = stack
    u1, c1 = _user(db)
    u2, c2 = _user(db)
    for u in (u1, u2):
        _as(u)
        c.post(COMM, json={"from_agent": "PERSEO", "to_agent": "RAFAEL", "message": "x",
                           "context": {"company_id": c1.id, "user_id": u1.id}})
    s1, s2 = ag["RAFAEL"].seen
    assert (s1["user_id"], s1["company_id"]) == (u1.id, c1.id)
    assert (s2["user_id"], s2["company_id"]) == (u2.id, c2.id)
    assert _last_log(db, "agents_communicate", u2.email).company_id == c2.id
