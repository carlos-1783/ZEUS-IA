"""Fase 2 / Step 1 — THALOS en lecturas (C2) y WebSocket por usuario (C2/A1).

- Toda ruta /api/* de la app real queda cubierta por THALOS (escritura o lectura).
- Una GET con entrada invalida se rechaza y deja evento THALOS.
- El WebSocket registra eventos THALOS y aisla conexiones por usuario: un client_id
  ajeno no da acceso a los eventos de otro usuario ni puede desconectarlo.
"""

from __future__ import annotations

import asyncio
import json
import uuid

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.security import create_access_token, get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.company import Company, UserCompany
from app.models.thalos_security_event import ThalosSecurityEvent
from app.models.user import User
from services import thalos_request_guard_v1 as g

P = "/api/v1"


@pytest.fixture()
def db():
    Base.metadata.create_all(
        bind=engine,
        tables=[User.__table__, Company.__table__, UserCompany.__table__, ThalosSecurityEvent.__table__],
    )
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _seed(db, tag: str, active: bool = True) -> User:
    suf = uuid.uuid4().hex[:8]
    c = Company(company_name=f"WS {tag} {suf}", slug=f"ws-{tag}-{suf}")
    u = User(email=f"ws_{tag}_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
             full_name=tag, is_active=active)
    db.add_all([c, u])
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    db.commit()
    db.refresh(u)
    return u


def _token(u: User) -> str:
    return create_access_token({"sub": u.email, "email": u.email})


def _last_event(db, source: str):
    db.expire_all()
    return (
        db.query(ThalosSecurityEvent)
        .filter(ThalosSecurityEvent.source == source)
        .order_by(ThalosSecurityEvent.id.desc())
        .first()
    )


# ------------------------------------------------------------------ lecturas


def test_every_api_route_is_thalos_covered():
    uncovered = [
        f"{sorted(r.methods)} {r.path}"
        for r in app.routes
        if isinstance(r, APIRoute) and r.path.startswith("/api/") and not g.route_is_thalos_covered(r)
    ]
    assert uncovered == [], f"rutas /api sin THALOS: {uncovered[:20]}"


def test_read_guard_rejects_control_chars_and_records_event(db):
    u = _seed(db, "rg")
    client = TestClient(app)
    r = client.get(f"{P}/chat/messages?agent_name=PERSEO%00&thread_id=main",
                   headers={"Authorization": f"Bearer {_token(u)}"})
    assert r.status_code == 400
    ev = _last_event(db, "thalos_read_guard")
    assert ev is not None and ev.action_taken == "deny" and ev.decision_rule == "control_characters"
    assert ev.user_id == u.id and ev.company_id is not None


def test_read_guard_rejects_oversized_query_even_anonymous(db):
    r = TestClient(app).get(f"{P}/health?x={'a' * 5000}")
    assert r.status_code == 414
    ev = _last_event(db, "thalos_read_guard")
    assert ev.decision_rule == "query_too_long" and ev.user_id is None


def test_read_guard_lets_valid_reads_through(db):
    u = _seed(db, "ok")
    r = TestClient(app).get(f"{P}/chat/messages?agent_name=PERSEO&thread_id=main",
                            headers={"Authorization": f"Bearer {_token(u)}"})
    assert r.status_code == 200, r.text


# ------------------------------------------------------------------ WebSocket


class _FakeWS:
    def __init__(self):
        self.sent = []

    async def send_text(self, m):
        self.sent.append(m)


def test_manager_isolates_same_client_id_between_users():
    from app.api.v1.endpoints.websocket import ConnectionManager

    m = ConnectionManager()
    victim, attacker = _FakeWS(), _FakeWS()
    kv = m.register(victim, "client-123", user_id=1)
    ka = m.register(attacker, "client-123", user_id=2)  # mismo client_id, otro usuario
    assert kv != ka
    asyncio.run(m.send_user_json(1, {"type": "alerta", "secreto": "A"}))
    assert len(victim.sent) == 1 and attacker.sent == []
    # El atacante se va: la conexion de la victima sigue intacta.
    m.unregister(ka, 2, attacker)
    asyncio.run(m.send_user_json(1, {"type": "alerta2"}))
    assert len(victim.sent) == 2
    assert not hasattr(m, "broadcast")


def test_manager_unregister_ignores_replaced_socket():
    from app.api.v1.endpoints.websocket import ConnectionManager

    m = ConnectionManager()
    old, new = _FakeWS(), _FakeWS()
    k = m.register(old, "c1", user_id=7)
    m.register(new, "c1", user_id=7)  # reconexion del mismo usuario
    m.unregister(k, 7, old)  # el handler viejo cierra tarde
    asyncio.run(m.send_user_json(7, {"x": 1}))
    assert len(new.sent) == 1


def test_ws_connect_records_thalos_allow_and_registers_per_user(db):
    from app.api.v1.endpoints.websocket import manager

    u = _seed(db, "wsok")
    with TestClient(app).websocket_connect(f"{P}/ws/client-abc?token={_token(u)}") as ws:
        hello = json.loads(ws.receive_text())
        assert hello["type"] == "connection_established" and hello["user_id"] == u.id
        assert manager.connection_key(u.id, "client-abc") in manager.active_connections
        ws.send_text(json.dumps({"type": "ping"}))
        assert json.loads(ws.receive_text())["type"] == "pong"
    ev = _last_event(db, "thalos_websocket_guard")
    assert ev.action_taken == "allow" and ev.user_id == u.id and ev.company_id is not None
    assert manager.connection_key(u.id, "client-abc") not in manager.active_connections


@pytest.mark.parametrize(
    "path,reason",
    [
        ("/ws/client-x", "missing_token"),
        ("/ws/client-x?token=no.es.valido", "invalid_token"),
        ("/ws/client%20con%20espacios?token=x", "invalid_client_id"),
    ],
)
def test_ws_rejections_are_thalos_events(db, path, reason):
    with TestClient(app).websocket_connect(P + path) as ws:
        msg = json.loads(ws.receive_text())
        assert msg["code"] == reason
        with pytest.raises(WebSocketDisconnect):
            ws.receive_text()
    ev = _last_event(db, "thalos_websocket_guard")
    assert ev.action_taken == "deny" and ev.decision_rule == reason


def test_ws_message_with_control_chars_closes_and_records(db):
    u = _seed(db, "wsctl")
    with TestClient(app).websocket_connect(f"{P}/ws/client-ctl?token={_token(u)}") as ws:
        ws.receive_text()
        ws.send_text('{"type":"x","v":"\u0000"}')
        with pytest.raises(WebSocketDisconnect):
            ws.receive_text()
    ev = _last_event(db, "thalos_websocket_guard")
    assert ev.action_taken == "deny" and ev.decision_rule == "control_characters" and ev.user_id == u.id


def test_debug_requires_superuser_and_fake_diagnostics_removed(db):
    client = TestClient(app)
    assert client.get("/debug").status_code == 401
    normal = _seed(db, "dbgN")
    assert client.get("/debug", headers={"Authorization": f"Bearer {_token(normal)}"}).status_code in (400, 403)
    admin = _seed(db, "dbgS")
    admin.is_superuser = True
    db.add(admin)
    db.commit()
    ok = client.get("/debug", headers={"Authorization": f"Bearer {_token(admin)}"})
    assert ok.status_code == 200 and ok.json()["status"] == "debug"
    for gone in ("/ws-test", "/railway-ws-diagnostic"):
        r = client.get(gone, headers={"Accept": "application/json"})
        assert "websocket_support" not in r.text
