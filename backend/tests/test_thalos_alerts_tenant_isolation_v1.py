"""
Regresión: THALOS difundía sus alertas de seguridad por WebSocket a TODOS
los tenants conectados, sin filtrar por empresa (`emit_thalos_event(0, ...)`
-> `manager.broadcast(msg)` en `services/thalos_events_v1.py`). Una empresa
conectada recibía en tiempo real las alertas de seguridad generadas por la
actividad de OTRA empresa -- fuga de información entre tenants.

Fix: `services/thalos_alert_service.py::create_alert` ahora difunde vía
`services/thalos_events_v1.py::emit_thalos_event_for_company`, que resuelve
los usuarios reales de `alert.company_id` (tabla `UserCompany`) y los
notifica solo a ellos vía `manager.send_user_json` -- nunca a
`manager.broadcast`.

Estas pruebas usan el `ConnectionManager` real de
`app/api/v1/endpoints/websocket.py` (el mismo singleton que usa producción)
con conexiones WebSocket falsas (solo registran los mensajes recibidos) para
no depender de la pila de red real, igual que
`services/perseo_events_v1.py` no se prueba con sockets reales en este
repo. Lo que se verifica es el enrutado real de mensajes del manager, no un
doble simulado del manager.
"""

from __future__ import annotations

import json
import uuid

import pytest  # pyright: ignore[reportMissingImports]
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.company import Company, UserCompany
from app.models.user import User


class _FakeWebSocket:
    """Doble de WebSocket que solo registra lo que se le envía -- el
    `ConnectionManager` real (`send_user_json`/`broadcast`) solo necesita
    `send_text`."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_text(self, message: str) -> None:
        self.sent.append(message)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def manager():
    """El singleton real de producción, con limpieza antes/después para no
    contaminar otros tests que compartan el mismo proceso pytest."""
    from app.api.v1.endpoints.websocket import manager as _manager

    _manager.active_connections.clear()
    _manager.user_connections.clear()
    try:
        yield _manager
    finally:
        _manager.active_connections.clear()
        _manager.user_connections.clear()


def _seed_company(db: Session, label: str):
    suf = uuid.uuid4().hex[:8]
    user = User(
        email=f"thalos_tenant_{label}_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name=f"Thalos Tenant Tester {label}",
        is_active=True,
    )
    company = Company(company_name=f"Thalos Tenant Co {label} {suf}", slug=f"thalos-tenant-{label}-{suf}")
    db.add_all([user, company])
    db.flush()
    db.add(UserCompany(user_id=user.id, company_id=company.id, role="owner"))
    db.commit()
    return user, company


def _connect(manager, user_id: int) -> _FakeWebSocket:
    ws = _FakeWebSocket()
    client_id = f"client-{uuid.uuid4().hex[:8]}"
    manager.active_connections[client_id] = ws
    manager.user_connections.setdefault(user_id, []).append(client_id)
    return ws


def test_alert_for_company_a_not_delivered_to_company_b(db: Session, manager):
    """Reproduce el bug como regresión: dos empresas conectadas por
    WebSocket, una alerta de seguridad para la empresa A -- solo la
    conexión de A debe recibirla, la de B no debe recibir NADA."""
    from services.thalos_alert_service import create_alert

    user_a, company_a = _seed_company(db, "a")
    user_b, company_b = _seed_company(db, "b")

    ws_a = _connect(manager, user_a.id)
    ws_b = _connect(manager, user_b.id)

    row = create_alert(
        db,
        title="Fuerza bruta detectada",
        level="critical",
        message=f"{user_a.email}: actividad sospechosa",
        rule_id="brute_force_email",
        metadata={"email": user_a.email},
        company_id=company_a.id,
    )
    db.commit()

    assert len(ws_a.sent) == 1, "la empresa A debería recibir su propia alerta por WS"
    payload_a = json.loads(ws_a.sent[0])
    assert payload_a["type"] == "thalos_alert_created"
    assert payload_a["alert_id"] == row.id
    assert payload_a["company_id"] == company_a.id

    assert ws_b.sent == [], (
        "FUGA MULTI-TENANT: la empresa B recibió por WebSocket una alerta de "
        "seguridad que pertenece a la empresa A"
    )


def test_alert_without_resolved_company_is_not_broadcast_to_anyone(db: Session, manager):
    """Si no se pudo resolver `company_id` (p.ej. fuerza bruta con email que
    no corresponde a ningún usuario real), la alerta NO debe difundirse a
    las conexiones de otras empresas -- antes, `company_id=None` acababa en
    `emit_thalos_event(0, ...)` -> `manager.broadcast()`, llegando a TODO el
    mundo conectado."""
    from services.thalos_alert_service import create_alert

    user_a, company_a = _seed_company(db, "c")
    ws_a = _connect(manager, user_a.id)

    create_alert(
        db,
        title="Fuerza bruta con email desconocido",
        level="critical",
        message="evil@unknown.test: 6 fallos en 60min",
        rule_id="brute_force_email",
        metadata={"email": f"evil_{uuid.uuid4().hex[:8]}@unknown.test"},
        company_id=None,
    )
    db.commit()

    assert ws_a.sent == [], (
        "una alerta sin empresa resuelta no debe llegar a conexiones de "
        "empresas no relacionadas (antes: manager.broadcast a todos)"
    )


def test_emit_thalos_event_without_user_id_does_not_broadcast(manager):
    """`emit_thalos_event` (ruta genérica, usada también por
    `thalos_monitor_service.run_monitor_cycle` para el evento
    `thalos_monitor_cycle`) ya no tiene fallback de broadcast ciego cuando
    no hay `user_id`: antes `emit_thalos_event(0, ...)` llegaba a *todas*
    las conexiones activas vía `manager.broadcast`."""
    from services.thalos_events_v1 import emit_thalos_event

    user_a = User(
        email=f"thalos_noleak_{uuid.uuid4().hex[:8]}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name="No Leak Tester",
        is_active=True,
    )
    user_a.id = 999001  # no se persiste; solo se usa como clave del manager
    ws_a = _connect(manager, user_a.id)

    emit_thalos_event(0, "thalos_monitor_cycle", {"events_inserted": 1, "alerts_created": 0})

    assert ws_a.sent == [], "sin user_id, el evento no debe llegar a ninguna conexión activa"
