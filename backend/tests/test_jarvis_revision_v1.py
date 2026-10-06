"""J8 (correcciones de la revision independiente): H1-H7.

H1 respuesta con negacion/destinatario concreto no es un «sí, a todos»; H2 negacion/duda nunca
prepara una accion; H3 varias peticiones en un mensaje se avisan; H4 estado caducado se borra y no
guarda el mensaje original; H5 un texto cualquiera no es un nombre; H6 /jarvis/thread pasa por
THALOS y filtra por empresa; H7 save_state verifica la persistencia y ZEUS no promete continuidad."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_active_user
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.chat_message import ChatMessage
from app.models.company import Company, UserCompany
from app.models.customer import Customer
from app.models.user import User
from app.models.zeus_pending_approval import ZeusPendingApproval
from services import jarvis_clarification as clarif
from services.agent_memory_service import persist_operational_state, scoped_thread_id
from services.intent_parser import parse_intent

ZEUS = "/api/v1/chat/ZEUS CORE/chat"
JARVIS = "/api/v1/jarvis/message"

NEGATED = [
    "no hay que enviar oferta del 5% a clientes",
    "mejor no enviar la oferta del 5% a clientes",
    "evita enviar oferta 5% a clientes",
    "no quiero crear el cliente Luis Gómez luis@x.es",
    "no sé si enviar oferta a clientes",
    "no, envía oferta 5% a clientes",  # un «no» que contesta y luego ordena: POR DISEÑO se pregunta
    "no hace falta crear cliente Ana ana@x.es",
    "no mandes la campaña a todos mis clientes",
    "no envíes oferta a clientes",
    "no crees el cliente Luis Gómez luis@x.es",
]
PARTIAL = [
    "envía la oferta pero no a todos",
    "envía la oferta a todos menos a Pedro",
    "manda la oferta solo a mis clientes de Madrid",
]
MIXED = [
    "crea el cliente José Álvarez con email jose@x.es y mándale la oferta del 10%",
    "cuántos clientes tengo y qué ventas hicimos",
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


def _seed(db, with_company=True):
    suf = uuid.uuid4().hex[:8]
    u = User(email=f"j8r_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
             full_name="J8R", is_active=True)
    db.add(u)
    db.flush()
    co = None
    if with_company:
        co = Company(company_name=f"J8R {suf}", slug=f"j8r-{suf}")
        db.add(co)
        db.flush()
        db.add(Customer(name="Cli", email=f"cli_{suf}@example.test", company_id=co.id))
        db.add(UserCompany(user_id=u.id, company_id=co.id, role="owner"))
    db.commit()
    db.refresh(u)
    if co:
        db.refresh(co)
    return u, co


def _chat(client, user, message, thread="main", url=JARVIS):
    app.dependency_overrides[get_current_active_user] = lambda: user
    r = client.post(url, json={"message": message, "thread_id": thread})
    assert r.status_code == 200, r.text
    return r.json()


def _pending_count(db, user):
    db.expire_all()
    return db.query(ZeusPendingApproval).filter(ZeusPendingApproval.user_id == user.id).count()


# ------------------------------------------------------------------------------------------ H2


@pytest.mark.parametrize("msg", NEGATED)
def test_h2_negacion_nunca_prepara_accion(msg):
    t = parse_intent(msg)
    assert t.needs_clarification and t.missing_entities == ["explicit_intent"], (msg, t.missing_entities)
    assert "no he hecho nada" in t.clarification_question


@pytest.mark.parametrize("msg", PARTIAL)
def test_h2_destinatarios_parciales_se_preguntan_y_se_dice_que_no_hay_filtrado(msg):
    t = parse_intent(msg)
    assert t.needs_clarification and t.missing_entities == ["recipients_scope"], msg
    assert "TODOS los clientes" in t.clarification_question


def test_h2_ordenes_claras_siguen_funcionando():
    assert not parse_intent("envía oferta 5% a todos mis clientes").needs_clarification
    assert not parse_intent("crea el cliente Ana López ana@x.com").needs_clarification
    assert not parse_intent("manda una campaña a todos mis clientes con un 10% de descuento").needs_clarification


@pytest.mark.parametrize("msg", NEGATED + PARTIAL + MIXED + ["nunca envíes", "no mandes", "no crees el cliente"])
def test_h2_h3_endpoint_no_crea_aprobacion_ni_ejecuta(db, client, msg):
    user, co = _seed(db)
    out = _chat(client, user, msg, thread="neg-" + uuid.uuid4().hex[:6])
    assert out["needs_clarification"] is True or "no hago nada" in out["message"]
    assert not out["needs_confirmation"] and not out["executed_action"] and out["approval_id"] is None
    assert _pending_count(db, user) == 0
    assert db.query(Customer).filter(Customer.company_id == co.id).count() == 1  # solo el sembrado


# ------------------------------------------------------------------------------------------ H3


def test_h3_acciones_mezcladas_se_detectan_y_se_nombran_ambas():
    t = parse_intent(MIXED[0])
    assert t.needs_clarification and t.missing_entities == ["single_action"]
    assert "crear un cliente" in t.clarification_question and "campaña" in t.clarification_question
    t2 = parse_intent(MIXED[1])
    assert t2.needs_clarification and t2.missing_entities == ["single_action"]
    assert "clientes" in t2.clarification_question and "ventas" in t2.clarification_question


@pytest.mark.parametrize("ok", [
    "crea una oferta del 10% y envíala a todos mis clientes",
    "crea una campaña para aumentar las ventas y envíala a todos mis clientes",
    "ventas y facturación de hoy",
    "crea el cliente Ana López con email ana@x.com y teléfono 612345678",
])
def test_h3_una_sola_peticion_no_se_marca_como_multiple(ok):
    assert parse_intent(ok).missing_entities != ["single_action"]


# ------------------------------------------------------------------------------------------ H1


@pytest.mark.parametrize("reply", ["no a todos", "solo a Juan", "sí, pero solo a Juan", "todos menos Pedro",
                                   "a todos excepto Pedro", "no, a todos no"])
def test_h1_respuesta_con_negacion_o_destinatario_concreto_no_es_un_si(db, client, reply):
    user, _ = _seed(db)
    th = "h1-" + uuid.uuid4().hex[:6]
    assert _chat(client, user, "manda una oferta del 20%", thread=th)["needs_clarification"] is True
    out = _chat(client, user, reply, thread=th)
    assert out["needs_clarification"] is True and not out["needs_confirmation"]
    assert out["approval_id"] is None and _pending_count(db, user) == 0
    assert "TODOS los clientes" in out["message"]
    # el estado sigue vivo: un «sí, a todos» posterior si completa
    ok = _chat(client, user, "sí, a todos", thread=th)
    assert ok["needs_confirmation"] is True and ok["approval_id"]


# ------------------------------------------------------------------------------------------ H4


def test_h4_estado_caducado_se_borra_y_no_guarda_el_mensaje_original(db, client):
    user, co = _seed(db)
    th = "h4-" + uuid.uuid4().hex[:6]
    _chat(client, user, "crea el cliente Ana López", thread=th)
    ck, tk = str(co.id), scoped_thread_id(th, user.id)
    state = clarif.load_state(ck, tk)
    assert state and "original" not in state and "raw_message" not in str(state)
    assert state["slots"]["name"] == "Ana López"  # solo lo derivado necesario para continuar
    state["asked_at"] = "2000-01-01T00:00:00+00:00"
    arts = clarif._artifacts(ck, tk)
    arts[clarif.KEY] = state
    persist_operational_state(ck, "ZEUS CORE", tk, artifacts=arts)
    assert clarif.load_state(ck, tk) is None
    assert clarif.KEY not in clarif._artifacts(ck, tk)  # borrado, no solo ignorado


def test_h4_ambiguedad_se_resuelve_sin_mensaje_original(db, client):
    user, co = _seed(db)
    th = "h4b-" + uuid.uuid4().hex[:6]
    first = _chat(client, user, "¿cómo va la caja hoy?", thread=th)
    assert first["needs_clarification"] is True
    state = clarif.load_state(str(co.id), scoped_thread_id(th, user.id))
    assert state["kind"] == "ambiguity" and "original" not in state
    out = _chat(client, user, "el estado de caja, tesorería", thread=th)
    assert out["executed_action"] is True and not out.get("needs_clarification")


# ------------------------------------------------------------------------------------------ H5


@pytest.mark.parametrize("reply", ["borra todo", "Borra todo", "cancela el pedido", "quiero 5 cosas", "ana lopez"])
def test_h5_texto_cualquiera_no_es_un_nombre(db, client, reply):
    user, _ = _seed(db)
    th = "h5-" + uuid.uuid4().hex[:6]
    first = _chat(client, user, "crea un cliente con email h5@example.com", thread=th)
    assert first["needs_clarification"] is True and "cómo se llama" in first["message"].lower()
    out = _chat(client, user, reply, thread=th)
    assert not out["needs_confirmation"] and _pending_count(db, user) == 0


def test_h5_un_nombre_razonable_si_se_acepta(db, client):
    user, _ = _seed(db)
    th = "h5ok-" + uuid.uuid4().hex[:6]
    _chat(client, user, "crea un cliente con email h5ok@example.com", thread=th)
    out = _chat(client, user, "Ana de la Cruz", thread=th)
    assert out["needs_confirmation"] is True and "Ana de la Cruz" in out["message"]


# ------------------------------------------------------------------------------------------ H6


def test_h6_thread_pasa_por_thalos_y_filtra_por_empresa(db, client):
    from services.crm_office_service import primary_company_id

    user, co = _seed(db)
    other = Company(company_name="Otra " + uuid.uuid4().hex[:5], slug="o-" + uuid.uuid4().hex[:8])
    db.add(other)
    db.flush()
    th = "h6-" + uuid.uuid4().hex[:6]
    db.add(ChatMessage(company_id=other.id, user_id=user.id, agent_name="ZEUS CORE", thread_id=th,
                       role="user", message="mensaje de OTRA empresa"))
    db.commit()
    assert primary_company_id(db, user) == co.id
    _chat(client, user, "cuántos clientes tengo", thread=th)
    app.dependency_overrides[get_current_active_user] = lambda: user
    r = client.get(f"/api/v1/jarvis/thread/{th}")
    assert r.status_code == 200
    msgs = [m["message"] for m in r.json()["messages"]]
    assert "cuántos clientes tengo" in msgs and "mensaje de OTRA empresa" not in msgs
    # guard THALOS: usuario sin empresa -> 403, igual que /jarvis/message
    nocomp, _ = _seed(db, with_company=False)
    app.dependency_overrides[get_current_active_user] = lambda: nocomp
    assert client.get(f"/api/v1/jarvis/thread/{th}").status_code == 403
    # /chat/messages (frontend) conserva su comportamiento (sin filtro de empresa)
    app.dependency_overrides[get_current_active_user] = lambda: user
    legacy = client.get("/api/v1/chat/messages", params={"agent_name": "ZEUS CORE", "thread_id": th})
    assert legacy.status_code == 200
    assert "mensaje de OTRA empresa" in [m["message"] for m in legacy.json()["messages"]]


# ------------------------------------------------------------------------------------------ H7


def test_h7_si_no_se_pudo_guardar_el_estado_se_avisa(db, client, monkeypatch):
    user, _ = _seed(db)
    monkeypatch.setattr(clarif, "save_state", lambda *a, **k: False)
    out = _chat(client, user, "crea el cliente Ana López", thread="h7-" + uuid.uuid4().hex[:6])
    assert out["needs_clarification"] is True and "no he podido recordar" in out["message"]


def test_h7_save_state_verifica_que_quedo_persistido(db, monkeypatch):
    user, co = _seed(db)
    t = parse_intent("crea el cliente Ana López")
    key = scoped_thread_id("h7b-" + uuid.uuid4().hex[:5], user.id)
    assert clarif.save_state(str(co.id), key, t) is True
    monkeypatch.setattr(clarif, "persist_operational_state", lambda *a, **k: None)  # fallo silencioso
    key2 = scoped_thread_id("h7c-" + uuid.uuid4().hex[:5], user.id)
    assert clarif.save_state(str(co.id), key2, t) is False
