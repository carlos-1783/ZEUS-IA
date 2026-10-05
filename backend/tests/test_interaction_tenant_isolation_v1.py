"""
Regresión de los hallazgos H-01 y H-04 de ZEUS_JARVIS_INTERACTION_AUDIT.md.

H-01 (crítico): el `company_id` que enviaba el cliente en `context` se confiaba como clave
del *pending* de ZEUS, como clave de memoria y como `company_id` de `chat_messages`.
Un usuario de la empresa A podía dejar su acción redactada bajo la clave de la empresa B,
y cuando B escribía «confirmar» se ejecutaba la acción de A. Reproducido en vivo en la
auditoría (T3/T3b). Estos tests fijan el comportamiento correcto:

  * la empresa y el usuario se derivan SOLO en servidor (JWT -> BD);
  * el *pending* queda atado a (empresa, usuario, hilo).

H-04 (alto): `GET /chat/panel/executions` y `POST /commands/activate-company/{empresa}`
respondían 200 sin token (el segundo además muta un estado global persistido en disco).

Ningún test envía emails ni llama al LLM: las empresas de prueba no tienen clientes con
email, así que `execute_send_campaign` sale antes de tocar ningún proveedor.
"""

from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

import pytest  # pyright: ignore[reportMissingImports]
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.endpoints import chat as chat_endpoint
from app.api.v1.endpoints import commands as commands_endpoint
from app.core.auth import get_current_active_user
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.company import Company, UserCompany
from app.models.user import User
from services.agent_memory_service import load as memory_load
from services.zeus_global_context import enrich_chat_context
from services import zeus_orchestrator_service as orch

CAMPAIGN_10 = "crea una oferta del 10% y envíala a los clientes"
CAMPAIGN_77 = "crea una oferta del 77% y envíala a los clientes"


@pytest.fixture()
def db():
    from app.db.base import _migrate_zeus_approvals_chat_columns, _migrate_zeus_approvals_execution_columns

    Base.metadata.create_all(bind=engine)
    _migrate_zeus_approvals_execution_columns()
    _migrate_zeus_approvals_chat_columns()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_user(db: Session, company: Company | None = None, *, tag: str = "u"):
    suf = uuid.uuid4().hex[:8]
    user = User(
        email=f"inter_{tag}_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name=f"Interaction {tag}",
        is_active=True,
    )
    db.add(user)
    db.flush()
    if company is None:
        company = Company(company_name=f"Inter Co {suf}", slug=f"inter-{suf}")
        db.add(company)
        db.flush()
    db.add(UserCompany(user_id=user.id, company_id=company.id, role="owner"))
    db.commit()
    db.refresh(user)
    db.refresh(company)
    return user, company


def _pending_for(user: User, company_id: int, thread: str = "main"):
    """Lee la solicitud pending de ZEUS (J3b: zeus_pending_approvals, unico estado) con las
    mismas claves que usa el orquestador. Devuelve el mismo formato que antes."""
    import json

    from app.models.zeus_pending_approval import ZeusPendingApproval

    ctx = {"zeus_global_context": {"company_id": company_id}, "thread_id": thread}
    thread_key = orch._pending_thread_key(user, ctx)
    s = SessionLocal()
    try:
        row = (
            s.query(ZeusPendingApproval)
            .filter(
                ZeusPendingApproval.company_id == company_id,
                ZeusPendingApproval.user_id == user.id,
                ZeusPendingApproval.thread_id == thread_key,
                ZeusPendingApproval.status == "pending",
            )
            .order_by(ZeusPendingApproval.id.desc())
            .first()
        )
        if row is None:
            return None
        return {
            "user_id": row.user_id,
            "company_id": row.company_id,
            "payload": json.loads(row.payload_json),
        }
    finally:
        s.close()


# --------------------------------------------------------------------------- H-01


def test_enrich_chat_context_ignores_client_company_id(db: Session):
    a, company_a = _seed_user(db, tag="a")
    b, company_b = _seed_user(db, tag="b")

    ctx = enrich_chat_context(db, a, {"company_id": company_b.id, "user_id": b.id})

    assert ctx["company_id"] == company_a.id
    assert ctx["user_id"] == a.id
    assert ctx["zeus_global_context"]["company_id"] == company_a.id


def test_build_server_context_drops_client_identity_and_internal_keys(db: Session):
    a, company_a = _seed_user(db, tag="a")
    b, company_b = _seed_user(db, tag="b")

    ctx = chat_endpoint.build_server_context(
        db,
        a,
        {
            "company_id": company_b.id,
            "user_id": b.id,
            "user_email": b.email,
            "zeus_global_context": {"company_id": company_b.id},
            "_memory": {"short_term": [{"role": "user", "content": "inyectado"}]},
            "_company_id": company_b.id,
            "conversation_history": [{"role": "user", "content": "inyectado"}],
            "image_url": "https://example.test/ref.png",
        },
        "main",
    )

    assert ctx["company_id"] == company_a.id
    assert ctx["user_id"] == a.id
    assert ctx["user_email"] == a.email
    assert ctx["thread_id"] == "main"
    assert "zeus_global_context" not in ctx
    assert "conversation_history" not in ctx
    assert not any(str(k).startswith("_") for k in ctx)
    # Los campos legítimos del cliente (referencias de media) se conservan.
    assert ctx["image_url"] == "https://example.test/ref.png"


def test_client_company_id_cannot_inject_pending_action_into_other_company(db: Session):
    """Reproduce T3/T3b de la auditoría."""
    a, company_a = _seed_user(db, tag="a")
    b, company_b = _seed_user(db, tag="b")
    thread = f"t-{uuid.uuid4().hex[:6]}"

    # B prepara su campaña del 10 %.
    out_b = asyncio.run(
        orch.try_handle_zeus_chat(db, b, CAMPAIGN_10, {"thread_id": thread})
    )
    assert out_b["needs_confirmation"] is True

    # A intenta dejar su campaña del 77 % bajo la clave de la empresa de B.
    out_a = asyncio.run(
        orch.try_handle_zeus_chat(
            db, a, CAMPAIGN_77, {"thread_id": thread, "company_id": company_b.id}
        )
    )
    assert out_a["needs_confirmation"] is True

    # El pending de B sigue siendo el de B.
    pending_b = _pending_for(b, company_b.id, thread)
    assert pending_b is not None
    assert pending_b["user_id"] == b.id
    assert pending_b["company_id"] == company_b.id
    assert pending_b["payload"]["discount_percent"] == 10.0

    # El de A está bajo la clave de A.
    pending_a = _pending_for(a, company_a.id, thread)
    assert pending_a is not None
    assert pending_a["user_id"] == a.id
    assert pending_a["company_id"] == company_a.id
    assert pending_a["payload"]["discount_percent"] == 77.0


def test_pending_action_is_bound_to_the_requesting_user(db: Session):
    """Otro usuario de la MISMA empresa no puede confirmar el pending ajeno."""
    owner, company = _seed_user(db, tag="owner")
    colleague, _ = _seed_user(db, company, tag="colleague")
    thread = f"t-{uuid.uuid4().hex[:6]}"

    out = asyncio.run(orch.try_handle_zeus_chat(db, owner, CAMPAIGN_10, {"thread_id": thread}))
    assert out["needs_confirmation"] is True
    assert _pending_for(owner, company.id, thread) is not None

    # El compañero escribe «confirmar» en el mismo hilo: no hay nada suyo que confirmar.
    out_c = asyncio.run(orch.try_handle_zeus_chat(db, colleague, "confirmar", {"thread_id": thread}))
    assert out_c["handled"] is True
    assert out_c["executed"] is False
    assert "No hay ninguna acción pendiente" in out_c["message"]

    # El pending del propietario sigue intacto.
    assert _pending_for(owner, company.id, thread) is not None


def test_company_key_never_collides_with_a_company_id():
    """Un usuario sin empresa no debe compartir clave con una empresa cuyo id coincida."""
    user = SimpleNamespace(id=5)
    key_without_company = orch._company_key(user, {})
    assert key_without_company != "5"
    assert orch._company_key(user, {"zeus_global_context": {"company_id": 5}}) == "5"


# --------------------------------------------------------------------------- H-04


@pytest.fixture()
def raw_client():
    """Cliente sin lifespan: no ejecuta los eventos de arranque de la app."""
    client = TestClient(app)
    try:
        yield client
    finally:
        app.dependency_overrides.clear()


def _fake_user(*, superuser: bool):
    return SimpleNamespace(
        id=1, email="fake@example.test", is_active=True, is_superuser=superuser, role="owner"
    )


def test_panel_executions_requires_authentication(raw_client: TestClient):
    assert raw_client.get("/api/v1/chat/panel/executions").status_code == 401


def test_panel_executions_forbidden_for_non_superuser(raw_client: TestClient):
    app.dependency_overrides[get_current_active_user] = lambda: _fake_user(superuser=False)
    assert raw_client.get("/api/v1/chat/panel/executions").status_code == 403


def test_panel_executions_ok_for_superuser(raw_client: TestClient, monkeypatch):
    app.dependency_overrides[get_current_active_user] = lambda: _fake_user(superuser=True)
    monkeypatch.setattr(chat_endpoint, "ensure_agent_stack", lambda: None)
    monkeypatch.setattr(
        chat_endpoint, "zeus", SimpleNamespace(get_execution_panel=lambda: {"recent_executions": []})
    )
    resp = raw_client.get("/api/v1/chat/panel/executions")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


class _FakeStateManager:
    """Evita escribir en app/data/system_state.json (fichero versionado)."""

    def __init__(self):
        self.updates = []

    def update_state(self, data):
        self.updates.append(data)
        return dict(data)


def test_activate_company_requires_authentication(raw_client: TestClient, monkeypatch):
    fake = _FakeStateManager()
    monkeypatch.setattr(commands_endpoint, "state_manager", fake)
    resp = raw_client.post("/api/v1/commands/activate-company/THALOS")
    assert resp.status_code == 401
    assert fake.updates == []


def test_activate_company_forbidden_for_non_superuser(raw_client: TestClient, monkeypatch):
    fake = _FakeStateManager()
    monkeypatch.setattr(commands_endpoint, "state_manager", fake)
    app.dependency_overrides[get_current_active_user] = lambda: _fake_user(superuser=False)
    resp = raw_client.post("/api/v1/commands/activate-company/THALOS")
    assert resp.status_code == 403
    assert fake.updates == []


def test_activate_company_ok_for_superuser(raw_client: TestClient, monkeypatch):
    fake = _FakeStateManager()
    monkeypatch.setattr(commands_endpoint, "state_manager", fake)
    app.dependency_overrides[get_current_active_user] = lambda: _fake_user(superuser=True)
    resp = raw_client.post("/api/v1/commands/activate-company/THALOS")
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
    assert len(fake.updates) == 1
