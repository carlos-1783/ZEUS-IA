"""J8 vuelta 3: criterio estricto de MENSAJE COMPLETO para acciones confirmables.

El mensaje entero debe ser una unica orden afirmativa limpia (vocabulario cerrado de cortesia,
verbos, argumentos). Retractaciones o condiciones DESPUES del verbo, temporales no soportados u
otra frase -> pregunta explicita, nunca vista previa. Endpoint /api/v1/jarvis/message."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_active_user
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.company import Company, UserCompany
from app.models.customer import Customer
from app.models.user import User
from app.models.zeus_pending_approval import ZeusPendingApproval

JARVIS = "/api/v1/jarvis/message"

RETRACTED = [
    "podrías enviar la oferta del 10% a todos mis clientes? no, mejor no",
    "envía la oferta del 10% a todos mis clientes o mejor no",
    "envía la oferta del 10% a todos mis clientes, es broma",
    "puedes enviar la oferta del 10% a todos mis clientes, no?  mejor espera",
    "necesito que envíes la oferta del 10% a todos mis clientes. Cancela eso, no la envíes",
    "envía la oferta del 10% a todos mis clientes, cuando yo te diga",
    "ok y envía la oferta del 10% a todos mis clientes ... jajaja no",
    "vale, crea el cliente Ana ana@x.es solo si te lo confirmo luego, de momento no",
    # variantes
    "envía la oferta del 10% a todos mis clientes mañana",      # temporal no soportado
    "envía la oferta del 10% a todos mis clientes. Espera",
    "crea el cliente Ana López ana@x.es, de momento no",
    "No. Envía la oferta del 10% a todos mis clientes",          # falso negativo conservador documentado
    "envía la oferta del 10% a todos mis clientes y luego avísame",
    "crea el cliente Luis Gómez luis@x.es cuando puedas",
]

ORDERS = [
    "envía una oferta del 15% a todos mis clientes",
    "por favor, envía la oferta del 10% a todos mis clientes",
    "zeus, crea el cliente María Pérez maria@x.es",
    "quiero que envíes una oferta del 20% a todos mis clientes",
    "crea el cliente José Ruiz jose@x.es",
    "puedes enviar una oferta del 10% a todos mis clientes",
    "vale, manda la oferta del 10% a todos mis clientes",
    "envía la oferta del 10% a todos mis clientes, gracias",
    "crea el cliente María Pérez maria@x.es por favor",
]


@pytest.fixture(autouse=True)
def _llm_stub(monkeypatch):
    import services.unified_agent_runtime as rt

    monkeypatch.setattr(rt, "run_chat", lambda *a, **k: {"success": True, "message": "respuesta-llm-stub"})


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


def _seed(db):
    suf = uuid.uuid4().hex[:8]
    u = User(email=f"j8c_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
             full_name="J8C", is_active=True)
    db.add(u)
    db.flush()
    co = Company(company_name=f"J8C {suf}", slug=f"j8c-{suf}")
    db.add(co)
    db.flush()
    db.add(Customer(name="Cli", email=f"cli_{suf}@example.test", company_id=co.id))
    db.add(UserCompany(user_id=u.id, company_id=co.id, role="owner"))
    db.commit()
    db.refresh(u)
    db.refresh(co)
    return u, co


def _chat(client, user, message):
    app.dependency_overrides[get_current_active_user] = lambda: user
    r = client.post(JARVIS, json={"message": message, "thread_id": "oc-" + uuid.uuid4().hex[:6]})
    assert r.status_code == 200, r.text
    return r.json()


def _approvals(db, user):
    db.expire_all()
    return db.query(ZeusPendingApproval).filter(ZeusPendingApproval.user_id == user.id).count()


@pytest.mark.parametrize("msg", RETRACTED)
def test_retractacion_o_condicion_en_cualquier_punto_no_prepara_ni_ejecuta(db, client, msg):
    user, co = _seed(db)
    out = _chat(client, user, msg)
    assert out["needs_clarification"] is True, msg
    assert not out["needs_confirmation"] and not out["executed_action"] and out["approval_id"] is None
    assert _approvals(db, user) == 0
    assert "no he hecho nada" in out["message"]
    assert db.query(Customer).filter(Customer.company_id == co.id).count() == 1  # solo el sembrado


@pytest.mark.parametrize("msg", ORDERS)
def test_las_ordenes_limpias_siguen_preparandose(db, client, msg):
    user, co = _seed(db)
    out = _chat(client, user, msg)
    assert out["needs_confirmation"] is True and out["approval_id"], msg
    assert not out["executed_action"] and _approvals(db, user) == 1
    assert db.query(Customer).filter(Customer.company_id == co.id).count() == 1


@pytest.mark.parametrize("msg", ["¿cuántos clientes tengo?", "¿cuánto he vendido hoy en el TPV?",
                                 "¿cómo va la caja este mes?"])
def test_las_consultas_no_confirmables_no_se_ven_afectadas(db, client, msg):
    user, _ = _seed(db)
    out = _chat(client, user, msg)
    assert out["executed_action"] is True and out["approval_id"] is None and _approvals(db, user) == 0
