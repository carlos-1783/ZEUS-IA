"""J12b R10: el chat no devuelve texto de excepciones al cliente (mensaje generico + request_id),
los agentes devuelven errores genericos y /chat/health comprueba BD y agentes. Sin LLM ni red."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints import chat as chat_endpoint
from app.core.auth import get_current_active_user
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.db.session import get_db
from app.main import app
from app.models.company import Company, UserCompany
from app.models.user import User

SECRET = "SECRETO-INTERNO-postgres://user:pw@host/db"


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


def _user(db):
    suf = uuid.uuid4().hex[:8]
    c = Company(company_name=f"R10 {suf}", slug=f"r10-{suf}")
    db.add(c)
    db.flush()
    u = User(email=f"r10_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
             full_name="R10", is_active=True)
    db.add(u)
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    db.commit()
    db.refresh(u)
    return u


def test_chat_excepcion_no_filtra_detalle_y_devuelve_request_id(db, client, monkeypatch):
    import services.unified_agent_runtime as rt

    async def boom(*a, **k):
        raise RuntimeError(SECRET)

    monkeypatch.setattr(rt, "run_chat", boom)
    monkeypatch.setattr(chat_endpoint, "ensure_agent_stack", lambda: None)
    monkeypatch.setitem(chat_endpoint.AGENTS, "ZEUS CORE", object())
    u = _user(db)
    app.dependency_overrides[get_current_active_user] = lambda: u
    r = client.post("/api/v1/chat/ZEUS CORE/chat", json={"message": "hola"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is False
    assert SECRET not in r.text and "RuntimeError" not in r.text
    assert body["error"] == "internal_error"
    assert body["request_id"] and body["request_id"] in body["message"]


def test_agentes_devuelven_error_generico():
    import inspect
    from agents import afrodita, justicia, rafael

    for mod in (afrodita, justicia, rafael):
        src = inspect.getsource(mod)
        assert '"error": str(e)' not in src and '"error": str(exc)' not in src
        assert "Error en firewall: {" not in src


def test_health_ok_publico_sin_detalles(client):
    r = client.get("/api/v1/chat/health")
    assert r.status_code == 200 and r.json() == {"status": "healthy"}


def test_health_503_si_la_bd_falla(client):
    class Roto:
        def execute(self, *a, **k):
            raise RuntimeError(SECRET)

    app.dependency_overrides[get_db] = lambda: Roto()
    r = client.get("/api/v1/chat/health")
    assert r.status_code == 503 and r.json() == {"status": "unhealthy"} and SECRET not in r.text


def test_health_503_si_agentes_cargados_sin_inicializar(client, monkeypatch):
    monkeypatch.setattr(chat_endpoint, "_agents_ready", True)
    monkeypatch.setattr(chat_endpoint, "AGENTS", {"ZEUS CORE": None, "PERSEO": object()})
    r = client.get("/api/v1/chat/health")
    assert r.status_code == 503 and r.json() == {"status": "unhealthy"}
