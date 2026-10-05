"""J3: el cliente no puede forzar la ejecucion desde el chat ni desde TeamFlow.
La ejecucion de acciones con consecuencias (enviar campana, crear cliente) solo ocurre
tras vista previa + "confirmar" del MISMO usuario con un pending persistido.
Solo se sustituye el envio externo de email (se cuentan las llamadas)."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.endpoints import chat as chat_endpoint
from app.core.auth import get_current_active_user
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.agent_activity import AgentActivity
from app.models.company import Company, UserCompany
from app.models.customer import Customer
from app.models.user import User
from services import zeus_orchestrator_service as orch

CHAT = "/api/v1/chat/ZEUS CORE/chat"
TEAMFLOW = "/api/v1/teamflow/execute-from-chat"
CAMPAIGN = "crea una oferta del 10% y envíala a los clientes"
CONTROL_KEYS = ("force_execute", "confirm_action", "skip_action_execution", "task_type", "phase", "workflow_id")


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


def _seed(db: Session, company=None, tag="u", with_customer=True):
    suf = uuid.uuid4().hex[:8]
    if company is None:
        company = Company(company_name=f"J3 {suf}", slug=f"j3-{suf}")
        db.add(company)
        db.flush()
        if with_customer:
            db.add(Customer(name="Cli", email=f"cli_{suf}@example.test", company_id=company.id))
    user = User(
        email=f"j3_{tag}_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name=f"J3 {tag}",
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(UserCompany(user_id=user.id, company_id=company.id, role="owner"))
    db.commit()
    db.refresh(user)
    db.refresh(company)
    return user, company


def _chat(client, user, message, context=None, thread=None):
    app.dependency_overrides[get_current_active_user] = lambda: user
    return client.post(
        CHAT,
        json={"message": message, "context": context or {}, "thread_id": thread or "t-" + uuid.uuid4().hex[:6]},
    )


def test_build_server_context_drops_control_keys(db):
    user, _ = _seed(db)
    ctx = chat_endpoint.build_server_context(db, user, {k: True for k in CONTROL_KEYS}, "main")
    for k in CONTROL_KEYS:
        assert k not in ctx


def test_campaign_with_client_force_flags_does_not_send(db, client, sent):
    user, _ = _seed(db)
    for flag in ("force_execute", "confirm_action", "skip_action_execution"):
        r = _chat(client, user, CAMPAIGN, {flag: True})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["needs_confirmation"] is True
        assert body["executed_action"] is False
    assert sent == []


def test_confirm_without_pending_does_not_execute(db, client, sent):
    user, _ = _seed(db)
    r = _chat(client, user, "confirmar", {"force_execute": True})
    assert r.json()["executed_action"] is False
    # «sí» sin pending no es una confirmacion: no ejecuta (se evita el LLM llamando al orquestador).
    out = asyncio.run(orch.try_handle_zeus_chat(db, user, "sí", {"thread_id": "np-" + uuid.uuid4().hex[:6]}))
    assert not (out or {}).get("executed")
    assert sent == []


def test_full_flow_same_user_sends_once(db, client, sent):
    user, _ = _seed(db)
    thread = "flow-" + uuid.uuid4().hex[:6]
    p = _chat(client, user, CAMPAIGN, thread=thread).json()
    assert p["needs_confirmation"] and sent == []
    c = _chat(client, user, "confirmar", thread=thread).json()
    assert c["executed_action"] is True
    assert len(sent) == 1
    again = _chat(client, user, "confirmar", thread=thread).json()
    assert again["executed_action"] is False
    assert len(sent) == 1


def test_affirmative_si_confirms_only_exact_with_pending(db, client, sent):
    user, _ = _seed(db)
    thread = "si-" + uuid.uuid4().hex[:6]
    _chat(client, user, CAMPAIGN, thread=thread)
    assert _chat(client, user, "sí", thread=thread).json()["executed_action"] is True
    assert len(sent) == 1
    thread2 = "si2-" + uuid.uuid4().hex[:6]
    _chat(client, user, CAMPAIGN, thread=thread2)
    # Respuesta ambigua: no confirma (el orquestador la deja pasar sin ejecutar nada).
    out = asyncio.run(orch.try_handle_zeus_chat(db, user, "si, pero cambia el texto", {"thread_id": thread2}))
    assert not (out or {}).get("executed")
    assert len(sent) == 1


def test_other_user_same_company_cannot_confirm(db, client, sent):
    a, company = _seed(db, tag="a")
    b, _ = _seed(db, company=company, tag="b")
    thread = "shared-" + uuid.uuid4().hex[:6]
    _chat(client, a, CAMPAIGN, thread=thread)
    rb = _chat(client, b, "confirmar", thread=thread).json()
    assert rb["executed_action"] is False
    assert sent == []
    assert _chat(client, a, "confirmar", thread=thread).json()["executed_action"] is True
    assert len(sent) == 1


def test_topic_change_invalidates_pending(db, client, sent):
    user, _ = _seed(db)
    thread = "topic-" + uuid.uuid4().hex[:6]
    _chat(client, user, CAMPAIGN, thread=thread)
    _chat(client, user, "¿cuántos clientes tengo?", thread=thread)
    assert _chat(client, user, "confirmar", thread=thread).json()["executed_action"] is False
    assert sent == []


def test_expired_pending_is_not_executed(db, client, sent, monkeypatch):
    user, _ = _seed(db)
    thread = "ttl-" + uuid.uuid4().hex[:6]
    _chat(client, user, CAMPAIGN, thread=thread)
    real = orch.time.time
    monkeypatch.setattr(orch.time, "time", lambda: real() + orch.PENDING_TTL_SECONDS + 5)
    assert _chat(client, user, "confirmar", thread=thread).json()["executed_action"] is False
    assert sent == []


def _count_customers(db, company_id):
    db.expire_all()
    return db.query(Customer).filter(Customer.company_id == company_id).count()


def test_create_customer_requires_confirmation(db, client):
    user, company = _seed(db, with_customer=False)
    thread = "cc-" + uuid.uuid4().hex[:6]
    msg = f"crear cliente Juan juan_{uuid.uuid4().hex[:6]}@example.com"
    r = _chat(client, user, msg, {"force_execute": True}, thread=thread).json()
    assert r["needs_confirmation"] is True and r["executed_action"] is False
    assert _count_customers(db, company.id) == 0
    c = _chat(client, user, "confirmar", thread=thread).json()
    assert c["executed_action"] is True
    assert _count_customers(db, company.id) == 1


def test_teamflow_force_execute_does_not_execute_and_logs_real_status(db, client, sent):
    user, company = _seed(db)
    app.dependency_overrides[get_current_active_user] = lambda: user
    r = client.post(
        TEAMFLOW,
        json={"message": CAMPAIGN, "thread_id": "tf-" + uuid.uuid4().hex[:6], "force_execute": True},
    )
    assert r.status_code == 200, r.text
    assert r.json()["needs_confirmation"] is True
    assert sent == []
    r2 = client.post(TEAMFLOW, json={"message": "confirmar", "thread_id": "tf-np-" + uuid.uuid4().hex[:6]})
    assert r2.status_code == 200
    db.expire_all()
    rows = (
        db.query(AgentActivity)
        .filter(AgentActivity.action_type == "teamflow_execute_from_chat", AgentActivity.user_email == user.email)
        .order_by(AgentActivity.id.asc())
        .all()
    )
    assert [x.status for x in rows] == ["completed", "failed"]
    assert all((x.details or {}).get("company_id") == company.id for x in rows)
