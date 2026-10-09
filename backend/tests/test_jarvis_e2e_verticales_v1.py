"""J12a: recorridos e2e REALES de JARVIS por vertical (hosteleria, oficina, seguros).

Todo va por HTTP contra la app real (TestClient) con usuarios y empresas reales creados en la BD de
test (sufijo uuid) y TOKENS JWT REALES (`create_access_token` + cabecera Authorization: no se usa
`dependency_overrides`, asi que pasan por `get_current_active_user` y por el guard THALOS reales).
Solo se sustituye la llamada final al proveedor del modelo (`agents.base_agent.chat_completion`, que
captura lo que llegaria al LLM) y, en el montaje de J9b, el cliente del clasificador; nunca la logica
de negocio. Reutiliza `stack`, `db`, `_user`, `rows` y `approvals` de test_jarvis_plan_v1.

Verticales (registro real):
- hosteleria = company_type "bar_restaurant" (modulos tpv, control_horario, payroll);
- oficina    = company_type "office" (crm, analytics, clients, payments);
- seguros    = `app.core.verticals_registry`: modulo "insurance" cerrado, solo superusuario. JARVIS no
  tiene ninguna accion de seguros: solo se prueban cadena, acceso, aislamiento y que no se ejecuta nada.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import date

import pytest

from app.core.security import create_access_token
from app.models.agent_activity import AgentActivity
from app.models.company import UserCompany
from app.models.customer import Customer
from app.models.erp import InventoryMovement, Product
from app.models.insurance import InsurancePolicy, PolicyBranch, PolicyStatus
from app.models.thalos_security_event import ThalosSecurityEvent
from app.models.user import User
from app.models.zeus_pending_approval import ZeusPendingApproval
from app.core.security import get_password_hash
from test_jarvis_plan_v1 import (  # noqa: F401  (fixtures de pytest + ayudantes)
    JARVIS, _user, approvals, classifier, db, rows, stack, step, use_model,
)

CHAIN_REQUIRED = ["ESCUCHAR", "CONTEXTO", "COMPRENDER", "ORQUESTAR", "ACTUAR", "AUDITAR", "RESPONDER"]
_PROMPTS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "prompts.json")
with open(_PROMPTS_PATH, encoding="utf-8") as _fh:
    _CFG = json.load(_fh)["zeus_prime_v1"]
AGENT_PROMPT = {k: _CFG["agents"][k]["prompt"] for k in _CFG["agents"]}
ALL_PROMPTS = {_CFG["system"]["prompt"], *AGENT_PROMPT.values()}


# ----------------------------------------------------------------------------- ayudantes HTTP
def _headers(user):
    return {"Authorization": "Bearer " + create_access_token({"sub": str(user.id)})}


def http(stack, user, method, url, **kw):
    """Peticion con token real (sin overrides de dependencias)."""
    from app.main import app

    app.dependency_overrides.clear()
    return stack.c.request(method, url, headers=_headers(user) if user is not None else {}, **kw)


def say(stack, user, message, thread="t-e2e", channel="text"):
    r = http(stack, user, "POST", JARVIS, json={"message": message, "thread_id": thread, "channel": channel})
    assert r.status_code == 200, r.text
    return r.json()


def evidence(stack, user, kind, item_id):
    return http(stack, user, "GET", f"/api/v1/jarvis/evidence/{kind}/{item_id}")


def of_kind(out, kind):
    return [e for e in out.get("evidence") or [] if e["kind"] == kind]


def _member(db, company, role="member"):
    suf = uuid.uuid4().hex[:8]
    u = User(email=f"j12a_m_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
             full_name="J12a miembro", is_active=True)
    db.add(u)
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=company.id, role=role))
    db.commit()
    db.refresh(u)
    return u


def _tenant(db, ctype, label):
    suf = uuid.uuid4().hex[:6]
    return _user(db, ctype, name=f"J12a {label} {suf}")


def _approval_row(db, aid):
    db.expire_all()
    return db.query(ZeusPendingApproval).filter(ZeusPendingApproval.id == aid).one()


# ----------------------------------------------------------------------------- definicion de verticales
class Hosteleria:
    id = "hosteleria"
    ctype = "bar_restaurant"
    consulta = "¿cuánto he vendido hoy en el TPV?"
    consulta_action = "tpv_sales_summary"
    # dos dominios en un mensaje => plan multiagente por reglas (sin modelo): cada agente REAL llama al modelo
    dominio_msg = "revisa la nómina y los turnos de la plantilla y lanza una campaña de instagram para el lunes"
    dominio_agents = ["AFRODITA", "PERSEO"]
    bloqueada = "enséñame las estadísticas"
    bloqueada_action = "analytics_summary"
    bloqueada_module = "analytics"
    action_type = "create_inventory_movement"
    evidence_kind = "movement"

    @staticmethod
    def prepare(db, co, name):
        return Product(sku=f"J12A-{uuid.uuid4().hex[:6]}", name=name, price=1.5, company_id=co.id,
                       track_inventory=True, quantity_on_hand=10.0, low_stock_threshold=2.0)

    @staticmethod
    def request(ctx):
        return f"por favor, registra una entrada de 5 unidades de {ctx['name']}"

    @staticmethod
    def effect(db, co, ctx):
        db.expire_all()
        p = ctx["obj"]
        n = db.query(InventoryMovement).filter(InventoryMovement.product_id == p.id).count()
        stock = db.query(Product).filter(Product.id == p.id, Product.company_id == co.id).one().quantity_on_hand
        return n, float(stock)

    expected_before = (0, 10.0)
    expected_after = (1, 15.0)


class Oficina:
    id = "oficina"
    ctype = "office"
    consulta = "enséñame las estadísticas"
    consulta_action = "analytics_summary"
    dominio_msg = "prepara la factura y el IVA del trimestre y redacta el contrato con la cláusula de RGPD"
    dominio_agents = ["RAFAEL", "JUSTICIA"]
    bloqueada = "¿cuánto he vendido hoy en el TPV?"
    bloqueada_action = "tpv_sales_summary"
    bloqueada_module = "tpv"
    action_type = "create_customer"
    evidence_kind = "customer"

    @staticmethod
    def prepare(db, co, name):
        return None

    @staticmethod
    def request(ctx):
        return f"crea el cliente Ana López con email {ctx['email']}"

    @staticmethod
    def effect(db, co, ctx):
        db.expire_all()
        return (db.query(Customer).filter(Customer.email == ctx["email"]).count(),)

    expected_before = (0,)
    expected_after = (1,)


VERTICALES = [Hosteleria, Oficina]
IDS = [v.id for v in VERTICALES]


PRODUCTOS = iter(["Harina de trigo", "Aceite de oliva", "Azucar moreno", "Sal marina", "Cafe molido", "Arroz bomba"] * 4)


def _setup_action(db, vert, co):
    name = next(PRODUCTOS)
    ctx = {"email": f"ana{uuid.uuid4().hex[:8]}@empresa.es", "name": name}
    obj = vert.prepare(db, co, name)
    if obj is not None:
        db.add(obj)
        db.commit()
        db.refresh(obj)
    ctx["obj"] = obj
    return ctx


def _chain(db, co, request_id):
    """Filas chain_* de una peticion, en orden de insercion."""
    db.expire_all()
    out = (db.query(AgentActivity).filter(AgentActivity.company_id == co.id).order_by(AgentActivity.id.asc()).all())
    return [r for r in out if (r.details or {}).get("correlation_id") == request_id]


def _guard_events(db, co, user, route):
    db.expire_all()
    evs = db.query(ThalosSecurityEvent).filter(ThalosSecurityEvent.company_id == co.id,
                                               ThalosSecurityEvent.user_id == user.id,
                                               ThalosSecurityEvent.event_type == "request_guard").all()
    return [e for e in evs if json.loads(e.details_json or "{}").get("route") == route]


# ============================================================================= a) cadena completa
@pytest.mark.parametrize("vert", VERTICALES, ids=IDS)
def test_a_cadena_completa_consulta_permitida_con_thalos(db, stack, vert):
    u, co = _tenant(db, vert.ctype, vert.id)
    out = say(stack, u, vert.consulta, thread="t-a")
    assert out["success"] is True and out["executed_action"] is True and out["request_id"]
    chain = _chain(db, co, out["request_id"])
    steps = {(r.details or {}).get("chain_step") for r in chain}
    assert set(CHAIN_REQUIRED) <= steps, steps
    for r in chain:
        d = r.details or {}
        assert r.company_id == co.id and r.user_email == u.email and d.get("user_id") == u.id
        assert r.agent_name and d.get("action") and r.status not in ("pending", "in_progress")
        assert d["correlation_id"] == out["request_id"]
    by_step = {(r.details or {})["chain_step"]: r for r in chain}
    assert by_step["ORQUESTAR"].details["action"] == vert.consulta_action and by_step["ORQUESTAR"].status == "success"
    assert by_step["RESPONDER"].status == "success" and by_step["ESCUCHAR"].details["action"] == "message_received"
    # AUDITAR = THALOS audita el resultado (agente THALOS, mismo correlation_id y empresa)
    aud = by_step["AUDITAR"]
    assert aud.agent_name == "THALOS" and aud.status == "completed" and aud.company_id == co.id
    # orden de la cadena = orden de las filas
    order = [(r.details or {})["chain_step"] for r in chain]
    firsts = [order.index(s) for s in CHAIN_REQUIRED]
    assert firsts == sorted(firsts), order
    # THALOS: guard de entrada + auditoria posterior, ambos con empresa y usuario reales
    g = _guard_events(db, co, u, "/api/v1/jarvis/message")
    assert len(g) == 1
    gd = json.loads(g[0].details_json)
    assert gd["decision"] == "allow" and gd["reason"] == "ok" and g[0].action_taken == "allow"
    post = db.query(ThalosSecurityEvent).filter(ThalosSecurityEvent.company_id == co.id,
                                                ThalosSecurityEvent.event_type == "post_action_audit").all()
    assert post and all(e.user_id == u.id for e in post)
    # y la evidencia "audit" de la respuesta es el mismo request_id
    assert of_kind(out, "audit")[0]["id"] == out["request_id"]
    assert evidence(stack, u, "audit", out["request_id"]).status_code == 200


@pytest.mark.parametrize("vert", VERTICALES, ids=IDS)
def test_a_sin_token_no_hay_cadena_y_guard_no_se_salta(db, stack, vert):
    u, co = _tenant(db, vert.ctype, vert.id)
    n0 = len(rows(db, co.id))
    r = http(stack, None, "POST", JARVIS, json={"message": vert.consulta, "thread_id": "t-x"})
    assert r.status_code in (401, 403)
    assert len(rows(db, co.id)) == n0 and stack.llm.calls == []
    # THALOS deniega la entrada con caracteres de control y deja evento deny + sin cadena
    r = http(stack, u, "POST", JARVIS, json={"message": "hola\x00", "thread_id": "t-x"})
    assert r.status_code == 400
    deny = [e for e in _guard_events(db, co, u, "/api/v1/jarvis/message")
            if json.loads(e.details_json)["decision"] == "deny"]
    assert len(deny) == 1 and json.loads(deny[0].details_json)["reason"] == "control_characters"
    assert not [r for r in rows(db, co.id) if (r.details or {}).get("chain_step") == "ESCUCHAR"]


# ============================================================================= b) accion con consecuencias
@pytest.mark.parametrize("vert", VERTICALES, ids=IDS)
def test_b_accion_sin_confirmar_no_se_ejecuta_y_flujo_de_confirmacion(db, stack, monkeypatch, vert):
    monkeypatch.setattr("services.afrodita_unified_control.writes_enabled", lambda: True)
    u, co = _tenant(db, vert.ctype, vert.id)
    other = _member(db, co)
    ctx = _setup_action(db, vert, co)
    assert vert.effect(db, co, ctx) == vert.expected_before

    # 1) sin confirmar: pide confirmacion, deja aprobacion pendiente y NO hay efecto en BD
    pend = say(stack, u, vert.request(ctx), thread="t-b")
    assert pend["needs_confirmation"] is True and pend["executed_action"] is False and pend["approval_id"]
    aid = pend["approval_id"]
    row = _approval_row(db, aid)
    assert (row.status, row.company_id, row.user_id, row.action_type) == ("pending", co.id, u.id, vert.action_type)
    assert vert.effect(db, co, ctx) == vert.expected_before

    # 2) "confirmar" de OTRO usuario de la misma empresa (mismo hilo) no ejecuta nada
    assert say(stack, other, "confirmar", thread="t-b")["executed_action"] is False
    assert http(stack, other, "POST", f"/api/v1/zeus-core/approvals/{aid}/resolve", json={"approve": True}).status_code == 403
    assert _approval_row(db, aid).status == "pending" and vert.effect(db, co, ctx) == vert.expected_before

    # 3) cambio de tema en otro hilo: rechaza SU aprobacion y no ejecuta
    ctx2 = _setup_action(db, vert, co)
    p2 = say(stack, u, vert.request(ctx2), thread="t-b2")
    assert p2["needs_confirmation"] is True
    say(stack, u, "¿cuántos clientes tengo?", thread="t-b2")
    assert _approval_row(db, p2["approval_id"]).status == "rejected"
    assert say(stack, u, "confirmar", thread="t-b2")["executed_action"] is False
    assert vert.effect(db, co, ctx2) == vert.expected_before and vert.effect(db, co, ctx) == vert.expected_before

    # 4) "confirmar" del mismo usuario: se ejecuta UNA sola vez
    done = say(stack, u, "confirmar", thread="t-b")
    assert done["executed_action"] is True and done["approval_id"] == aid
    assert vert.effect(db, co, ctx) == vert.expected_after
    assert _approval_row(db, aid).status == "executed"
    again = say(stack, u, "confirmar", thread="t-b")
    assert again["executed_action"] is False
    assert vert.effect(db, co, ctx) == vert.expected_after  # no duplica
    assert http(stack, u, "POST", f"/api/v1/zeus-core/approvals/{aid}/resolve", json={"approve": True}).status_code == 409
    assert vert.effect(db, co, ctx) == vert.expected_after

    # 5) auditoria THALOS del resultado, con el mismo correlation_id de la respuesta
    chain = _chain(db, co, done["request_id"])
    aud = [r for r in chain if (r.details or {}).get("chain_step") == "AUDITAR"]
    assert aud and aud[0].agent_name == "THALOS" and aud[0].status == "completed" and aud[0].company_id == co.id
    assert {"ESCUCHAR", "ORQUESTAR", "AUDITAR", "RESPONDER"} <= {(r.details or {}).get("chain_step") for r in chain}
    ev = db.query(ThalosSecurityEvent).filter(ThalosSecurityEvent.company_id == co.id,
                                              ThalosSecurityEvent.user_id == u.id,
                                              ThalosSecurityEvent.event_type == "post_action_audit").all()
    assert ev

    # 6) evidencia: URL del recurso creado, accesible solo para esa empresa
    items = of_kind(done, vert.evidence_kind)
    assert len(items) == 1 and items[0]["url"].startswith("/api/v1/jarvis/evidence/")
    assert http(stack, u, "GET", items[0]["url"]).status_code == 200
    assert http(stack, other, "GET", items[0]["url"]).status_code == 200      # misma empresa
    assert http(stack, None, "GET", items[0]["url"]).status_code in (401, 403)  # sin sesion
    b, _ = _tenant(db, vert.ctype, "otra")
    r = http(stack, b, "GET", items[0]["url"])
    assert r.status_code == 404 and ctx["email"] not in r.text


# ============================================================================= c) cross-tenant
@pytest.mark.parametrize("vert", VERTICALES, ids=IDS)
def test_c_cross_tenant_hilo_evidencia_aprobacion_y_contexto_del_modelo(db, stack, monkeypatch, vert):
    monkeypatch.setattr("services.afrodita_unified_control.writes_enabled", lambda: True)
    a, ca = _tenant(db, vert.ctype, "A")
    b, cb = _tenant(db, vert.ctype, "B")  # MISMO tipo de empresa: aislamiento por empresa, no por tipo
    ctx = _setup_action(db, vert, ca)
    tag = uuid.uuid4().hex[:8]
    mark_a, mark_b = f"secretoa{tag}", f"secretob{tag}"
    dom_msg, dom_agent = vert.dominio_msg, vert.dominio_agents[0]

    out_a = say(stack, a, f"{dom_msg} {mark_a}", thread="t-c")
    assert dom_agent in [c[0] for c in stack.llm.calls]
    pend = say(stack, a, vert.request(ctx), thread="t-c2")
    aid = pend["approval_id"]
    assert aid and out_a["request_id"]

    # lo que llega al LLM en la peticion de B (mismo thread_id) no contiene nada de A
    stack.llm.calls.clear()
    say(stack, b, f"{dom_msg} {mark_b}", thread="t-c")
    assert stack.llm.calls, "B deberia haber llegado al modelo"
    sent = json.dumps(stack.llm.calls, ensure_ascii=False)
    assert mark_b in sent
    for leak in (mark_a, ca.company_name, ca.slug, a.email, ctx["email"]):
        assert leak not in sent, leak
    # (y A si ve su propio contexto de empresa: el control no es vacuo)
    stack.llm.calls.clear()
    say(stack, a, f"{dom_msg} otra {tag}", thread="t-c")
    assert ca.company_name in json.dumps(stack.llm.calls, ensure_ascii=False)
    assert cb.company_name not in json.dumps(stack.llm.calls, ensure_ascii=False)

    # hilo: B no ve el de A, A si
    tb = http(stack, b, "GET", "/api/v1/jarvis/thread/t-c").json()
    ta = http(stack, a, "GET", "/api/v1/jarvis/thread/t-c").json()
    assert mark_a not in json.dumps(tb) and mark_b in json.dumps(tb)
    assert mark_a in json.dumps(ta) and mark_b not in json.dumps(ta)
    assert all(m["company_id"] == cb.id and m["user_id"] == b.id for m in tb["messages"])
    assert not http(stack, b, "GET", "/api/v1/jarvis/thread/t-c2").json()["messages"]

    # evidencia de A: 404 para B, idéntico a un recurso inexistente
    for kind, rid, missing in (("approval", aid, 10**9), ("audit", pend["request_id"], "no-existe-" + tag),
                               ("audit", out_a["request_id"], "no-existe-" + tag)):
        assert evidence(stack, a, kind, rid).status_code == 200
        rb, rn = evidence(stack, b, kind, rid), evidence(stack, b, kind, missing)
        assert rb.status_code == 404 and (rb.status_code, rb.json()) == (rn.status_code, rn.json()), (kind, rb.text)

    # resolver la aprobacion de A desde B: 404 (ni aprueba ni rechaza) y "confirmar" en su hilo tampoco
    for approve in (True, False):
        r = http(stack, b, "POST", f"/api/v1/zeus-core/approvals/{aid}/resolve", json={"approve": approve})
        assert r.status_code == 404, r.text
    assert http(stack, b, "GET", "/api/v1/zeus-core/approvals/pending").json()["pending"] == []
    assert say(stack, b, "confirmar", thread="t-c2")["executed_action"] is False
    assert _approval_row(db, aid).status == "pending" and vert.effect(db, ca, ctx) == vert.expected_before

    # lo de A sigue intacto: confirma y se ejecuta una vez
    assert say(stack, a, "confirmar", thread="t-c2")["executed_action"] is True
    assert vert.effect(db, ca, ctx) == vert.expected_after
    assert not approvals(db, b)


# ============================================================================= d) modulos
@pytest.mark.parametrize("vert", VERTICALES, ids=IDS)
def test_d_modulo_no_activo_blocked_module_sin_llamar_al_modelo(db, stack, vert):
    u, co = _tenant(db, vert.ctype, vert.id)
    fake = use_model(stack, classifier(step("RAFAEL", "consulta", "no debe llamarse")))
    out = say(stack, u, vert.bloqueada, thread="t-d")
    assert out["success"] is False and out["executed_action"] is False and not out.get("needs_confirmation")
    assert "Tu empresa no tiene activo el módulo" in out["message"]
    assert stack.llm.calls == [] and fake.calls == []  # ni agentes/LLM ni clasificador
    blocked = [r for r in _chain(db, co, out["request_id"]) if r.status == "blocked_module"]
    assert len(blocked) == 1
    d = blocked[0].details
    assert (d["chain_step"], d["action"], d["module"]) == ("ORQUESTAR", vert.bloqueada_action, vert.bloqueada_module)
    assert blocked[0].company_id == co.id and blocked[0].user_email == u.email and d["user_id"] == u.id
    assert not approvals(db, u)
    # ni efecto ni aprobacion; el guard THALOS si dejo su evento "allow"
    assert any(json.loads(e.details_json)["decision"] == "allow"
               for e in _guard_events(db, co, u, "/api/v1/jarvis/message"))


@pytest.mark.parametrize("vert", VERTICALES, ids=IDS)
def test_d_agente_thalos_bloqueado_para_no_superusuario_sin_llamar_al_modelo(db, stack, vert):
    u, co = _tenant(db, vert.ctype, vert.id)
    r = http(stack, u, "POST", "/api/v1/chat/THALOS/chat", json={"message": "revisa los logs", "thread_id": "t-d2"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["success"] is False and "solo está disponible para administradores" in out["message"]
    assert stack.llm.calls == []
    assert [r for r in rows(db, co.id, action="route_to_agent") if r.status == "blocked_module"]


# ============================================================================= e) prompt integro
@pytest.mark.parametrize("vert", VERTICALES, ids=IDS)
def test_e_prompt_de_sistema_integro_de_los_agentes_del_recorrido(db, stack, vert):
    u, co = _tenant(db, vert.ctype, vert.id)
    out = say(stack, u, vert.dominio_msg, thread="t-e")
    assert out["success"] is True and [s["agent"] for s in out["steps"]] == vert.dominio_agents
    sys_prompts = [c[1][0]["content"] for c in stack.llm.calls if c[1][0]["role"] == "system"]
    assert len(sys_prompts) == len(stack.llm.calls) >= len(vert.dominio_agents)
    for agent in vert.dominio_agents:
        # el prompt LITERAL de prompts.json llega entero al modelo (no truncado ni alterado)
        assert AGENT_PROMPT[agent] in sys_prompts, f"prompt de {agent} alterado o truncado"
        assert len(AGENT_PROMPT[agent]) > 50
    # y ninguna llamada del recorrido lleva un prompt de sistema distinto de los de la configuracion
    assert all(p in ALL_PROMPTS for p in sys_prompts)


# ============================================================================= seguros (solo tests)
def _policy(db, co):
    cust = db.query(Customer).filter(Customer.company_id == co.id).first()
    p = InsurancePolicy(company_id=co.id, customer_id=cust.id, policy_number=f"J12A-{uuid.uuid4().hex[:10]}",
                        branch=PolicyBranch.HOGAR, coverages={}, insured_risk={}, premium_amount=100,
                        start_date=date.today(), status=PolicyStatus.ACTIVE)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _policy_numbers(stack, user):
    r = http(stack, user, "GET", "/api/v1/insurance/policies")
    assert r.status_code == 200, r.text
    return {p["policy_number"] for p in r.json()["data"]}


def test_seguros_modulo_cerrado_para_empresas_y_abierto_solo_a_superusuario(db, stack):
    for ctype in ("bar_restaurant", "office"):
        u, co = _tenant(db, ctype, "seg")
        r = http(stack, u, "GET", "/api/v1/insurance/policies")
        assert r.status_code == 403 and "insurance" in r.json()["detail"]
        assert http(stack, u, "GET", "/api/v1/insurance/claims").status_code == 403
    assert http(stack, None, "GET", "/api/v1/insurance/policies").status_code == 401
    su, _ = _user(db, "office", superuser=True, name=f"J12a seg-su {uuid.uuid4().hex[:6]}")
    assert http(stack, su, "GET", "/api/v1/insurance/policies").status_code == 200


def test_seguros_cross_tenant_las_polizas_de_una_empresa_no_aparecen_en_otra(db, stack):
    sa, ca = _user(db, "office", superuser=True, name=f"J12a seg-A {uuid.uuid4().hex[:6]}")
    sb, cb = _user(db, "office", superuser=True, name=f"J12a seg-B {uuid.uuid4().hex[:6]}")
    pa, pb = _policy(db, ca), _policy(db, cb)
    na, nb = _policy_numbers(stack, sa), _policy_numbers(stack, sb)
    assert pa.policy_number in na and pb.policy_number not in na
    assert pb.policy_number in nb and pa.policy_number not in nb
    # detalle directo de la poliza ajena: no existe para la otra empresa
    assert http(stack, sa, "GET", f"/api/v1/insurance/policies/{pa.id}").status_code == 200
    assert http(stack, sb, "GET", f"/api/v1/insurance/policies/{pa.id}").status_code == 404


def test_seguros_jarvis_cadena_con_superusuario_y_sin_accion_de_seguros(db, stack):
    su, co = _user(db, "office", superuser=True, name=f"J12a seg-J {uuid.uuid4().hex[:6]}")
    n0 = db.query(InsurancePolicy).filter(InsurancePolicy.company_id == co.id).count()
    # (a) cadena completa con consulta permitida
    out = say(stack, su, "enséñame las estadísticas", thread="t-seg")
    assert out["success"] is True and out["executed_action"] is True
    chain = _chain(db, co, out["request_id"])
    assert set(CHAIN_REQUIRED) <= {(r.details or {}).get("chain_step") for r in chain}
    assert all(r.company_id == co.id and r.user_email == su.email for r in chain)
    assert len(_guard_events(db, co, su, "/api/v1/jarvis/message")) == 1
    # (b) JARVIS no tiene accion de seguros: pedir una poliza NO crea ninguna ni deja aprobacion ejecutable
    resp = say(stack, su, "crea una póliza de hogar para mi cliente por 100 euros", thread="t-seg2")
    assert resp["executed_action"] is False
    say(stack, su, "confirmar", thread="t-seg2")
    db.expire_all()
    assert db.query(InsurancePolicy).filter(InsurancePolicy.company_id == co.id).count() == n0
    assert not [a for a in approvals(db, su) if a.status == "executed"]
    # (d) un usuario de empresa NO tiene el modulo: 403 (no llega ni a la logica de seguros)
    u, _ = _tenant(db, "office", "seg-u")
    assert http(stack, u, "GET", "/api/v1/insurance/policies").status_code == 403


def test_seguros_prompt_integro_en_el_recorrido_del_superusuario(db, stack):
    su, co = _user(db, "office", superuser=True, name=f"J12a seg-P {uuid.uuid4().hex[:6]}")
    out = say(stack, su, Oficina.dominio_msg, thread="t-seg3")
    assert out["success"] is True
    sys_prompts = [c[1][0]["content"] for c in stack.llm.calls if c[1][0]["role"] == "system"]
    assert AGENT_PROMPT["RAFAEL"] in sys_prompts and AGENT_PROMPT["JUSTICIA"] in sys_prompts and all(p in ALL_PROMPTS for p in sys_prompts)
