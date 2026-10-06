"""J8: JARVIS (punto de entrada unico) y comprension estructurada con umbral.

Parser: frases reales por vertical -> intencion/entidades/urgencia/confianza, ambiguedad y falsos
positivos antiguos. Endpoint: alias /jarvis/message == /chat/ZEUS CORE/chat (cadena, guard, tenant),
pregunta concreta sin ejecutar ni crear aprobacion, y continuacion en el mismo hilo.
Sin red ni LLM: solo se sustituye el envio de email."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_active_user
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.agent_activity import AgentActivity
from app.models.company import Company, UserCompany
from app.models.customer import Customer
from app.models.user import User
from app.models.zeus_pending_approval import ZeusPendingApproval
from services.intent_parser import extract_entities, parse_intent

ZEUS = "/api/v1/chat/ZEUS CORE/chat"
JARVIS = "/api/v1/jarvis/message"


# ----------------------------------------------------------------------------- parser puro


def test_hosteleria_ventas_tpv_hoy():
    t = parse_intent("¿cuánto he vendido hoy en el TPV?")
    assert t.intent == "tpv_sales_today" and t.confidence >= 0.8
    assert t.metadata["days"] == 1 and t.entities.period["label"] == "today"
    assert not t.needs_clarification and t.urgency == "normal"  # «hoy» es periodo, no urgencia


def test_oficina_crear_cliente_sin_email_pregunta_el_email():
    t = parse_intent("crea el cliente Ana López")
    assert t.intent == "create_customer"
    assert t.entities.names == ["Ana López"]
    assert t.missing_entities == ["email"] and t.needs_clarification
    assert "email de Ana López" in t.clarification_question


def test_oficina_crear_cliente_completo():
    t = parse_intent("crea el cliente Ana López con email ana@empresa.es y teléfono 612 345 678")
    assert t.intent == "create_customer" and not t.needs_clarification
    assert t.metadata["name"] == "Ana López" and t.metadata["email"] == "ana@empresa.es"
    assert t.metadata["phone"] == "612345678"
    assert t.confidence == 0.9  # 0.85 base + 0.05 entidades obligatorias presentes
    assert t.confidence_breakdown["required_entities_bonus"] == 0.05


def test_oficina_campana_todos_los_clientes_con_descuento():
    t = parse_intent("manda una campaña a todos mis clientes con un 10% de descuento")
    assert t.intent == "create_campaign_send" and t.discount_percent == 10.0
    assert t.entities.percentages == [10.0] and t.entities.recipients == "all_customers"
    assert t.requires_confirmation and not t.needs_clarification and t.confidence >= 0.9


def test_oficina_caja_este_mes_es_cashflow():
    t = parse_intent("¿cómo va la caja este mes?")
    assert t.intent == "get_cashflow" and t.metadata["days"] == 30
    assert t.entities.period["label"] == "month" and not t.needs_clarification


def test_caja_hoy_es_ambigua_y_pregunta():
    t = parse_intent("¿cómo va la caja hoy?")
    assert t.needs_clarification and t.ambiguous_with
    assert t.confidence < 0.7  # penalizacion por ambiguedad
    assert "o" in t.clarification_question and "?" in t.clarification_question
    assert {t.intent, *t.ambiguous_with} == {"get_cashflow", "tpv_sales_today"}


def test_campana_sin_destinatarios_pregunta_a_quien():
    t = parse_intent("manda una oferta del 20%")
    assert t.intent == "create_campaign_send" and t.missing_entities == ["recipients"]
    assert "¿A quién" in t.clarification_question


def test_campana_a_una_persona_no_se_convierte_en_envio_masivo():
    t = parse_intent("manda la oferta a Juan Pérez")
    assert t.needs_clarification and t.missing_entities == ["recipients"]


def test_urgencia_explicita():
    assert parse_intent("urgente: cuántos clientes tengo").urgency == "high"
    assert parse_intent("manda la campaña a todos mis clientes ya").urgency == "high"
    assert parse_intent("lo necesito hoy mismo, ventas de hoy").urgency == "high"
    assert parse_intent("cuando puedas, cuántos clientes tengo").urgency == "low"
    assert parse_intent("cuántos clientes tengo").urgency == "normal"
    assert parse_intent("ya tengo clientes nuevos en el CRM").urgency == "normal"


def test_entidades_tipadas():
    e = extract_entities(
        "Factura F-2024/15 de Ana López por 1.234,50 € el 15/03/2025, cliente 42, "
        "escribe a ana@x.com, descuento del 15%, últimos 14 días"
    )
    assert e.invoice_ids == ["F-2024/15"]
    assert e.amounts == [{"value": 1234.5, "currency": "EUR"}]
    assert e.dates == ["2025-03-15"] and e.customer_ids == [42]
    assert e.emails == ["ana@x.com"] and e.percentages == [15.0]
    assert e.period == {"label": "last_days", "days": 14}
    assert "Ana López" in e.names


@pytest.mark.parametrize(
    "msg",
    [
        "la caja del supermercado es azul",          # antes: _CASHFLOW_RE casaba «caja» suelta
        "me gusta el producto estrella de la tienda",  # antes: _METRICS_RE casaba «producto»
        "voy a convertir clientes en fans de la marca",  # antes: «ver» casaba dentro de «convertir»
        "crea una campaña para el cliente Juan",     # antes: create_customer («crea ... cliente»)
    ],
)
def test_falsos_positivos_antiguos_ya_no_disparan(msg):
    t = parse_intent(msg)
    assert t.intent == "unknown" or t.confidence < 0.7, (msg, t.intent)


def test_campana_que_menciona_ventas_no_es_consulta_tpv():
    t = parse_intent("crea una campaña para aumentar las ventas y envíala a todos mis clientes")
    assert t.intent == "create_campaign_send" and not t.needs_clarification


def test_ingreso_suelto_no_basta_para_metricas():
    assert parse_intent("el ingreso del paciente fue ayer").confidence < 0.7
    assert parse_intent("dame las métricas del mes").intent == "get_metrics"


def test_ventas_de_ayer_pide_periodo_soportado():
    t = parse_intent("ventas de ayer")
    assert t.needs_clarification and t.missing_entities == ["supported_period"]


# ----------------------------------------------------------------------------- endpoint


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


@pytest.fixture(autouse=True)
def _llm_stub(monkeypatch):
    """Sustituye SOLO la llamada al modelo conversacional (sin red). Si algun test llega aqui es
    porque el mensaje no era operativo y cae al LLM de ZEUS, como en produccion."""
    import services.unified_agent_runtime as rt

    monkeypatch.setattr(rt, "run_chat", lambda *a, **k: {"success": True, "message": "respuesta-llm-stub"})


@pytest.fixture()
def client():
    c = TestClient(app)
    try:
        yield c
    finally:
        app.dependency_overrides.clear()


def _seed(db, with_company=True):
    suf = uuid.uuid4().hex[:8]
    u = User(email=f"j8_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
             full_name="J8", is_active=True)
    db.add(u)
    db.flush()
    co = None
    if with_company:
        co = Company(company_name=f"J8 {suf}", slug=f"j8-{suf}")
        db.add(co)
        db.flush()
        db.add(Customer(name="Cli", email=f"cli_{suf}@example.test", company_id=co.id))
        db.add(UserCompany(user_id=u.id, company_id=co.id, role="owner"))
    db.commit()
    db.refresh(u)
    if co:
        db.refresh(co)
    return u, co


def _post(client, user, url, message, thread="main", **extra):
    app.dependency_overrides[get_current_active_user] = lambda: user
    return client.post(url, json={"message": message, "thread_id": thread, **extra})


def _chat(client, user, message, url=JARVIS, thread="main", **extra):
    r = _post(client, user, url, message, thread, **extra)
    assert r.status_code == 200, r.text
    return r.json()


def _rows(db, user, rid):
    db.expire_all()
    rows = db.query(AgentActivity).filter(AgentActivity.user_email == user.email).all()
    return [r for r in rows if (r.details or {}).get("correlation_id") == rid]


def _pending_count(db, user):
    db.expire_all()
    return db.query(ZeusPendingApproval).filter(ZeusPendingApproval.user_id == user.id).count()


def test_alias_jarvis_equivale_a_chat_zeus_core(db, client):
    user, co = _seed(db)
    msg = "crea una oferta del 10% y envíala a los clientes"
    a = _chat(client, user, msg, url=ZEUS, thread="t-a-" + uuid.uuid4().hex[:5])
    b = _chat(client, user, msg, url=JARVIS, thread="t-b-" + uuid.uuid4().hex[:5], channel="voice")
    for k in ("agent", "success", "needs_confirmation", "executed_action", "needs_clarification"):
        assert a[k] == b[k], k
    assert a["agent"] == "ZEUS CORE" and b["needs_confirmation"] is True
    assert a["request_id"] and b["request_id"] and a["request_id"] != b["request_id"]
    steps_a = sorted((r.details["chain_step"], r.status) for r in _rows(db, user, a["request_id"]))
    rows_b = _rows(db, user, b["request_id"])
    steps_b = sorted((r.details["chain_step"], r.status) for r in rows_b)
    assert steps_a == steps_b and {"ESCUCHAR", "COMPRENDER", "ORQUESTAR", "RESPONDER"} <= {s for s, _ in steps_b}
    assert all(r.company_id == co.id for r in rows_b)  # tenant resuelto en servidor
    esc = [r for r in rows_b if r.details["chain_step"] == "ESCUCHAR"][0]
    assert esc.details["channel"] == "voice"  # el canal del cuerpo llega a la cadena


def test_jarvis_exige_auth_y_empresa_como_el_chat(db, client):
    app.dependency_overrides.clear()
    assert client.post(JARVIS, json={"message": "hola"}).status_code in (401, 403)
    nocomp, _ = _seed(db, with_company=False)
    r_chat = _post(client, nocomp, ZEUS, "cuántos clientes tengo")
    r_jarvis = _post(client, nocomp, JARVIS, "cuántos clientes tengo")
    assert r_chat.status_code == r_jarvis.status_code == 403  # THALOS: sin empresa
    bad = _post(client, _seed(db)[0], JARVIS, "hola\x00mundo")
    assert bad.status_code == 400  # THALOS: caracteres de control


def test_jarvis_canal_invalido_422(db, client):
    user, _ = _seed(db)
    assert _post(client, user, JARVIS, "hola", channel="fax").status_code == 422


def test_thread_devuelve_solo_el_historial_propio(db, client):
    a, _ = _seed(db)
    b, _ = _seed(db)
    th = "hist-" + uuid.uuid4().hex[:6]
    _chat(client, a, "cuántos clientes tengo", thread=th)
    app.dependency_overrides[get_current_active_user] = lambda: a
    r = client.get(f"/api/v1/jarvis/thread/{th}")
    assert r.status_code == 200 and r.json()["total"] >= 2
    assert {m["role"] for m in r.json()["messages"]} >= {"user", "assistant"}
    app.dependency_overrides[get_current_active_user] = lambda: b
    assert client.get(f"/api/v1/jarvis/thread/{th}").json()["total"] == 0


def test_falta_email_pregunta_sin_ejecutar_y_la_respuesta_completa(db, client):
    user, co = _seed(db)
    th = "cli-" + uuid.uuid4().hex[:6]
    first = _chat(client, user, "crea el cliente Ana López", thread=th)
    assert first["needs_clarification"] is True and first["intent"] == "create_customer"
    assert "email" in first["message"] and not first["needs_confirmation"] and not first["executed_action"]
    assert first["approval_id"] is None and _pending_count(db, user) == 0
    comp = [r for r in _rows(db, user, first["request_id"])
            if r.details["chain_step"] == "COMPRENDER" and r.details["action"] == "parse_intent"][0]
    assert comp.status == "needs_more_data" and comp.details["missing_entities"] == ["email"]
    assert "Ana" not in str(comp.details)  # la traza no lleva valores de entidades
    cont = [r for r in _rows(db, user, first["request_id"]) if r.details["chain_step"] == "CONTINUAR"]
    assert cont and cont[0].status == "needs_more_data"

    email = f"ana_{uuid.uuid4().hex[:6]}@example.com"
    second = _chat(client, user, f"su email es {email}", thread=th)
    assert second["needs_confirmation"] is True and second["approval_id"]
    assert "Ana López" in second["message"] and email in second["message"]
    assert db.query(Customer).filter(Customer.email == email).count() == 0  # aun no creado
    third = _chat(client, user, "confirmar", thread=th)
    assert third["executed_action"] is True
    db.expire_all()
    cust = db.query(Customer).filter(Customer.email == email).one()
    assert cust.company_id == co.id and cust.name == "Ana López"


def test_la_aclaracion_no_se_filtra_a_otro_usuario_ni_hilo(db, client):
    a, _ = _seed(db)
    b, _ = _seed(db)
    th = "iso-" + uuid.uuid4().hex[:6]
    _chat(client, a, "crea el cliente Ana López", thread=th)
    email = f"x_{uuid.uuid4().hex[:6]}@example.test"
    # otro usuario, mismo nombre de hilo: no completa nada
    out_b = _chat(client, b, f"su email es {email}", thread=th)
    assert not out_b.get("needs_confirmation") and _pending_count(db, b) == 0
    # mismo usuario, otro hilo: tampoco
    out_a2 = _chat(client, a, f"su email es {email}", thread=th + "-otro")
    assert not out_a2.get("needs_confirmation")


def test_cambio_de_tema_descarta_la_aclaracion(db, client):
    user, _ = _seed(db)
    th = "tema-" + uuid.uuid4().hex[:6]
    _chat(client, user, "crea el cliente Ana López", thread=th)
    out = _chat(client, user, "cuántos clientes tengo", thread=th)
    assert out["executed_action"] is True and not out.get("needs_clarification")
    out2 = _chat(client, user, "ana@example.test", thread=th)
    assert not out2.get("needs_confirmation")  # el estado se descarto


def test_cancelar_la_pregunta(db, client):
    user, _ = _seed(db)
    th = "canc-" + uuid.uuid4().hex[:6]
    _chat(client, user, "crea el cliente Ana López", thread=th)
    out = _chat(client, user, "no", thread=th)
    assert "No he hecho nada" in out["message"] and _pending_count(db, user) == 0


def test_campana_sin_destinatarios_pregunta_y_si_completa(db, client):
    user, _ = _seed(db)
    th = "camp-" + uuid.uuid4().hex[:6]
    first = _chat(client, user, "manda una oferta del 20%", thread=th)
    assert first["needs_clarification"] is True and "¿A quién" in first["message"]
    assert not first["needs_confirmation"] and _pending_count(db, user) == 0
    second = _chat(client, user, "sí, a todos", thread=th)
    assert second["needs_confirmation"] is True and second["approval_id"]
    assert "20" in second["message"] or second["execution"] is not None


def test_ambigua_pregunta_concreta_y_la_respuesta_desambigua(db, client):
    user, _ = _seed(db)
    th = "amb-" + uuid.uuid4().hex[:6]
    first = _chat(client, user, "¿cómo va la caja hoy?", thread=th)
    assert first["needs_clarification"] is True and not first["executed_action"]
    assert "cashflow" in first["message"] and "TPV" in first["message"]
    comp = [r for r in _rows(db, user, first["request_id"]) if r.details["action"] == "parse_intent"][0]
    assert comp.status == "not_understood"
    second = _chat(client, user, "las ventas del TPV", thread=th)
    assert second["executed_action"] is True and not second.get("needs_clarification")


def test_operativo_no_clasificable_ya_no_devuelve_ayuda_generica(db, client):
    user, _ = _seed(db)
    out = _chat(client, user, "la caja")
    assert out["needs_clarification"] is True and out["executed_action"] is False
    assert "cashflow" in out["message"] and "Prueba con frases concretas" not in out["message"]
