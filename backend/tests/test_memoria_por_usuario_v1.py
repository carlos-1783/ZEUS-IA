"""J6 (R6): la memoria conversacional que ve el LLM esta aislada por empresa + usuario + agente + hilo.
Solo se sustituye la llamada al modelo (agents.base_agent.chat_completion): se capturan los
mensajes que le llegarian. La memoria se persiste y se lee de la BD real de test."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_active_user
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.agent_memory import AgentShortTermBuffer
from app.models.company import Company, UserCompany
from app.models.user import User
from services import unified_agent_runtime as rt

CHAT = "/api/v1/chat/RAFAEL/chat"


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
def model_calls(monkeypatch):
    """Stub SOLO de la llamada al modelo; devuelve la lista de `messages` recibidos."""
    calls = []

    def _fake(messages, temperature=0.7, max_tokens=500, **kw):
        calls.append([dict(m) for m in messages])
        n = len(calls)
        return {
            "success": True,
            "content": f"respuesta-{n}",
            "model": "stub",
            "usage": {"total_tokens": 1},
            "cost": 0.0,
            "elapsed_time": 0.0,
            "timestamp": "2026-01-01T00:00:00",
        }

    monkeypatch.setattr("agents.base_agent.chat_completion", _fake)
    return calls


def _user(db, company=None, superuser=False):
    suf = uuid.uuid4().hex[:8]
    u = User(
        email=f"j6_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name="J6",
        is_active=True,
        is_superuser=superuser,
    )
    db.add(u)
    db.flush()
    if company is not None:
        db.add(UserCompany(user_id=u.id, company_id=company.id, role="owner"))
    db.commit()
    db.refresh(u)
    return u


def _company(db):
    suf = uuid.uuid4().hex[:8]
    c = Company(company_name=f"J6 {suf}", slug=f"j6-{suf}")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _say(client, user, text, thread="main"):
    app.dependency_overrides[get_current_active_user] = lambda: user
    r = client.post(CHAT, json={"message": text, "thread_id": thread})
    assert r.status_code == 200, r.text
    return r.json()


def _sent_text(call):
    return "\n".join(m["content"] for m in call)


def test_two_users_same_company_same_thread_do_not_share_history(db, client, model_calls):
    co = _company(db)
    a, b = _user(db, co), _user(db, co)
    tag = uuid.uuid4().hex[:6]
    _say(client, a, f"secreto-A-{tag}")
    _say(client, b, f"hola-B-{tag}")
    assert f"secreto-A-{tag}" not in _sent_text(model_calls[1])
    # A vuelve: ve lo suyo, no lo de B
    _say(client, a, f"otra-A-{tag}")
    txt = _sent_text(model_calls[2])
    assert f"secreto-A-{tag}" in txt and f"hola-B-{tag}" not in txt


def test_continuity_same_user_second_message_includes_first(db, client, model_calls):
    co = _company(db)
    u = _user(db, co)
    tag = uuid.uuid4().hex[:6]
    _say(client, u, f"primero-{tag}")
    _say(client, u, f"segundo-{tag}")
    second = model_calls[1]
    assert any(m["role"] == "user" and f"primero-{tag}" in m["content"] for m in second)
    assert any(m["role"] == "assistant" and m["content"] == "respuesta-1" for m in second)
    # persistido en BD bajo la clave con usuario, no bajo "main" a secas
    row = (
        db.query(AgentShortTermBuffer)
        .filter(AgentShortTermBuffer.company_id == str(co.id), AgentShortTermBuffer.thread_id == f"main:u{u.id}")
        .first()
    )
    assert row is not None and len(row.messages) == 4


def test_two_companies_isolated_even_with_same_thread(db, client, model_calls):
    c1, c2 = _company(db), _company(db)
    a, b = _user(db, c1), _user(db, c2)
    tag = uuid.uuid4().hex[:6]
    _say(client, a, f"empresa1-{tag}", thread="compartido")
    _say(client, b, f"empresa2-{tag}", thread="compartido")
    assert f"empresa1-{tag}" not in _sent_text(model_calls[1])


def test_legacy_buffer_without_user_is_ignored(db, client, model_calls):
    from datetime import datetime, timedelta, timezone

    co = _company(db)
    u = _user(db, co)
    tag = uuid.uuid4().hex[:6]
    db.add(
        AgentShortTermBuffer(
            company_id=str(co.id),
            agent_id="RAFAEL",
            thread_id="main",
            messages=[{"role": "user", "content": f"legado-{tag}"}],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    db.commit()
    _say(client, u, f"nuevo-{tag}")
    assert f"legado-{tag}" not in _sent_text(model_calls[0])


def test_user_without_company_gets_controlled_error_and_no_default_key(db, client, model_calls):
    u = _user(db, None)
    app.dependency_overrides[get_current_active_user] = lambda: u
    r = client.post(CHAT, json={"message": "hola", "thread_id": "main"})
    # El guard THALOS global ya corta en HTTP; run_chat es la segunda barrera (test siguiente).
    assert r.status_code == 403 and "empresa" in r.json()["detail"].lower()
    assert model_calls == []
    leaked = (
        db.query(AgentShortTermBuffer)
        .filter(AgentShortTermBuffer.company_id.in_(["default", u.email]))
        .count()
    )
    assert leaked == 0


def test_run_chat_without_company_or_user_fails_without_shared_key(model_calls):
    for ctx in (None, {"user_email": "x@y.z"}, {"user_id": 5}, {"company_id": 3}):
        out = rt.run_chat("RAFAEL", "main", "hola", None, ctx)
        assert out["success"] is False and out["error"] == "memory_scope_required"
    assert model_calls == []


def test_superuser_without_company_uses_platform_space_per_user(db, client, model_calls):
    s1, s2 = _user(db, None, superuser=True), _user(db, None, superuser=True)
    tag = uuid.uuid4().hex[:6]
    _say(client, s1, f"plat1-{tag}")
    _say(client, s2, f"plat2-{tag}")
    assert f"plat1-{tag}" not in _sent_text(model_calls[1])
    assert (
        db.query(AgentShortTermBuffer)
        .filter(AgentShortTermBuffer.company_id == "platform", AgentShortTermBuffer.thread_id == f"main:u{s1.id}")
        .count()
        == 1
    )


def test_client_cannot_inject_superuser_flag(db, client, model_calls):
    u = _user(db, None)
    app.dependency_overrides[get_current_active_user] = lambda: u
    r = client.post(
        CHAT, json={"message": "hola", "thread_id": "main", "context": {"_is_superuser": True, "company_id": 1}}
    )
    assert r.status_code == 403
    assert model_calls == []
