"""J8 vuelta 2: lista BLANCA para acciones con consecuencias (enviar campaña, crear cliente).

Solo se prepara la accion si el verbo va en una clausula con forma de orden afirmativa (cortesia y
formulas de peticion como unico material previo). Negaciones no previstas («nada de», «deja de»,
«ni se te ocurra», «sin»), condicionales, dudas y subordinadas -> pregunta explicita, nunca vista
previa ni aprobacion. Endpoint real /api/v1/jarvis/message."""

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

NOT_AN_ORDER = [
    # las 6 de la revision
    "nada de enviar ofertas a clientes",
    "nada de enviar la oferta del 10% a clientes",
    "para nada envíes la oferta del 10% a clientes",
    "ni se te ocurra enviar la oferta del 10% a clientes",
    "sin enviar la oferta del 10% a clientes",
    "deja de enviar ofertas a mis clientes",
    # variantes
    "nada de crear el cliente Ana ana@x.es",
    "deja de crear clientes",
    "sin crear el cliente Ana ana@x.es",
    "si quieres envía la oferta del 10% a clientes",
    "¿y si enviamos la oferta del 10% a clientes?",
    "¿podrías no enviar la oferta?",
    # falsos negativos conservadores documentados: se pregunta
    "no olvides enviar la oferta a clientes",
    "no dejes de enviar la oferta del 10% a todos mis clientes",
    "no es que no quiera, envía la oferta a todos mis clientes",
]

ORDERS = [
    "envía una oferta del 15% a todos mis clientes",
    "por favor, envía la oferta del 10% a todos mis clientes",
    "zeus, crea el cliente María Pérez maria@x.es",
    "quiero que envíes una oferta del 20% a todos mis clientes",
    "crea el cliente José Ruiz jose@x.es",
    "puedes enviar una oferta del 10% a todos mis clientes",
    "vale, manda la oferta del 10% a todos mis clientes",
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
    u = User(email=f"j8w_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
             full_name="J8W", is_active=True)
    db.add(u)
    db.flush()
    co = Company(company_name=f"J8W {suf}", slug=f"j8w-{suf}")
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
    r = client.post(JARVIS, json={"message": message, "thread_id": "wl-" + uuid.uuid4().hex[:6]})
    assert r.status_code == 200, r.text
    return r.json()


def _approvals(db, user):
    db.expire_all()
    return db.query(ZeusPendingApproval).filter(ZeusPendingApproval.user_id == user.id).count()


@pytest.mark.parametrize("msg", NOT_AN_ORDER)
def test_lo_que_no_es_una_orden_afirmativa_no_prepara_ni_ejecuta(db, client, msg):
    user, co = _seed(db)
    out = _chat(client, user, msg)
    assert not out["needs_confirmation"] and not out["executed_action"] and out["approval_id"] is None, msg
    assert _approvals(db, user) == 0
    assert db.query(Customer).filter(Customer.company_id == co.id).count() == 1  # solo el sembrado


@pytest.mark.parametrize("msg", [m for m in NOT_AN_ORDER if "oferta" in m or "cliente" in m][:12])
def test_y_ZEUS_pregunta_algo_en_vez_de_callar(db, client, msg):
    user, _ = _seed(db)
    out = _chat(client, user, msg)
    assert out["message"].strip() and (out["needs_clarification"] is True or out["success"])


@pytest.mark.parametrize("msg", ORDERS)
def test_las_ordenes_afirmativas_siguen_preparandose(db, client, msg):
    user, co = _seed(db)
    out = _chat(client, user, msg)
    assert out["needs_confirmation"] is True and out["approval_id"], msg
    assert not out["executed_action"] and _approvals(db, user) == 1
    assert db.query(Customer).filter(Customer.company_id == co.id).count() == 1  # aun nada creado


@pytest.mark.parametrize("msg", ["¿cuántos clientes tengo?", "¿cuánto he vendido hoy en el TPV?",
                                 "¿cómo va la caja este mes?", "nada de ventas hoy, dime la caja del mes"])
def test_las_consultas_no_confirmables_no_se_ven_afectadas(db, client, msg):
    user, _ = _seed(db)
    out = _chat(client, user, msg)
    assert out["approval_id"] is None and _approvals(db, user) == 0
    if not msg.startswith("nada de"):
        assert out["executed_action"] is True, msg
