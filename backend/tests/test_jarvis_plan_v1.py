"""J9b: plan de pasos multiagente. Sin red ni LLM real: se sustituye SOLO `agents.base_agent.chat_completion`
(los agentes son los reales, con su prompt de personalidad) y el cliente del clasificador J8b."""

from __future__ import annotations

import json
import os
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from agents.afrodita import Afrodita
from agents.justicia import Justicia
from agents.perseo import Perseo
from agents.rafael import Rafael
from agents.thalos import Thalos
from agents.zeus_core import ZeusCore
from app.api.v1.endpoints import chat as chat_endpoint
from app.core.auth import get_current_active_user
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.agent_activity import AgentActivity
from app.models.company import Company, UserCompany
from app.models.customer import Customer
from app.models.user import User
from app.models.zeus_pending_approval import ZeusPendingApproval
from services import jarvis_model_comprehension as mc
from services import jarvis_plan as jp

JARVIS = "/api/v1/jarvis/message"
MSG_CAMPANA_CONTRATO = (
    "prepara una campaña para el lanzamiento y revisa si el contrato con el proveedor tiene cláusula de exclusividad"
)
MSG_IVA_CORREO = "dime cuánto IVA pago este trimestre y redacta un borrador de correo a mi gestor"
OFFER = "prepara la oferta del 10% a todos mis clientes y revisa el contrato con el proveedor"

_PROMPTS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "prompts.json")
with open(_PROMPTS_PATH, encoding="utf-8") as _fh:
    _CFG = json.load(_fh)["zeus_prime_v1"]
PROMPT = {k: _CFG["agents"][k]["prompt"] for k in _CFG["agents"]}
NAME_OF_PROMPT = {v: k for k, v in PROMPT.items()}


# ----------------------------------------------------------------------------- helpers de modelo
def step(agent, kind, objective, deps=(), action_type=None):
    return {"agent": agent, "kind": kind, "objective": objective, "depends_on": list(deps),
            "action_type": action_type}


def classifier(*steps, actions=(), overall=0.95):
    return {"actions": list(actions), "steps": list(steps), "overall_certainty": overall,
            "needs_clarification": False, "clarification_question": None, "notes": ""}


OFFER_ACT = {"action_type": "send_campaign", "polarity": "affirm", "certainty": 0.95,
             "entities": {"names": [], "emails": [], "phones": [], "percentages": [10],
                          "recipients": "all_customers"}}
CUST_ACT = {"action_type": "create_customer", "polarity": "affirm", "certainty": 0.95,
            "entities": {"names": ["María Pérez"], "emails": ["maria@x.es"], "phones": [], "percentages": [],
                         "recipients": None}}


class FakeClf:
    def __init__(self, data=None, raw=None):
        self.data, self.raw, self.calls = data, raw, []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.calls.append(kw)
        content = self.raw if self.raw is not None else json.dumps(self.data)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                               usage=SimpleNamespace(prompt_tokens=800, completion_tokens=100))


class Llm:
    """Sustituto de `chat_completion`: registra cada llamada (en orden) y responde segun el agente."""

    def __init__(self):
        self.calls = []        # [(agente, messages)]
        self.fail_for = set()  # agentes cuyo modelo falla

    def __call__(self, messages, temperature=0.3, max_tokens=2000, **kw):
        agent = NAME_OF_PROMPT.get(messages[0]["content"], "ZEUS CORE")
        self.calls.append((agent, json.loads(json.dumps(messages))))
        if agent in self.fail_for:
            return {"success": False, "error": f"fallo simulado {agent}"}
        return {"success": True, "content": f"Respuesta de {agent} numero {len(self.calls)}.", "model": "stub",
                "cost": 0.0, "elapsed_time": 0.0, "usage": {"total_tokens": 1},
                "timestamp": "2026-01-01T00:00:00"}

    def agents(self):
        return [a for a, _ in self.calls]


class StubZeus:
    name = "ZEUS CORE"

    def set_zeus_core_ref(self, z):
        pass

    def process_request(self, ctx):
        return {"success": True, "content": "zeus-ok"}


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
def stack(monkeypatch):
    import agents.base_agent as base
    import services.unified_agent_runtime as rt

    for k in ("JARVIS_MODEL_COMPREHENSION", "JARVIS_CLASSIFIER_MODEL", "JARVIS_CLASSIFIER_TIMEOUT_SEC",
              "JARVIS_CLASSIFIER_MIN_CERTAINTY", "JARVIS_CLASSIFIER_COMPANY_DAILY_BUDGET_USD",
              "JARVIS_CLASSIFIER_GLOBAL_DAILY_BUDGET_USD", "JARVIS_CLASSIFIER_JSON_MODE"):
        monkeypatch.delenv(k, raising=False)
    llm = Llm()
    monkeypatch.setattr(base, "chat_completion", llm)
    z = ZeusCore()
    real = {"PERSEO": Perseo(), "RAFAEL": Rafael(), "JUSTICIA": Justicia(), "AFRODITA": Afrodita(),
            "THALOS": Thalos()}
    for a in real.values():
        z.register_agent(a)
    agents = {"ZEUS CORE": StubZeus(), **real}
    monkeypatch.setattr(rt, "_get_agents", lambda: dict(agents))
    monkeypatch.setattr(chat_endpoint, "ensure_agent_stack", lambda: None)
    monkeypatch.setattr(chat_endpoint, "AGENTS", dict(agents))
    monkeypatch.setattr(chat_endpoint, "zeus", z)
    monkeypatch.setattr(mc, "get_client", lambda: None)  # por defecto: sin modelo (fallback por reglas)
    c = TestClient(app)
    try:
        yield SimpleNamespace(c=c, llm=llm, mp=monkeypatch)
    finally:
        app.dependency_overrides.clear()


def use_model(stack, data=None, raw=None):
    fake = FakeClf(data, raw)
    stack.mp.setattr(mc, "get_client", lambda: fake)
    return fake


def _user(db, company_type="office", superuser=False, name=None):
    suf = uuid.uuid4().hex[:8]
    co = Company(company_name=name or f"J9b {suf}", slug=f"j9b-{suf}", company_type=company_type)
    db.add(co)
    db.flush()
    u = User(email=f"j9b_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
             full_name="J9b", is_active=True, is_superuser=superuser)
    db.add(u)
    db.flush()
    db.add(Customer(name="Cli", email=f"cli_{suf}@example.test", company_id=co.id))
    db.add(UserCompany(user_id=u.id, company_id=co.id, role="owner"))
    db.commit()
    db.refresh(u)
    db.refresh(co)
    return u, co


def say(stack, user, message, thread="t-plan"):
    app.dependency_overrides[get_current_active_user] = lambda: user
    r = stack.c.post(JARVIS, json={"message": message, "thread_id": thread})
    assert r.status_code == 200, r.text
    return r.json()


def rows(db, company_id, step=None, action=None):
    db.expire_all()
    out = db.query(AgentActivity).filter(AgentActivity.company_id == company_id).all()
    return [r for r in out
            if (step is None or (r.details or {}).get("chain_step") == step)
            and (action is None or (r.details or {}).get("action") == action)]


def approvals(db, user):
    db.expire_all()
    return db.query(ZeusPendingApproval).filter(ZeusPendingApproval.user_id == user.id).all()


# ----------------------------------------------------------------------------- 2 dominios
def test_dos_dominios_dos_pasos_dos_agentes_cada_uno_con_su_prompt_y_en_orden(db, stack):
    u, co = _user(db)
    fake = use_model(stack, classifier(
        step("PERSEO", "borrador", "Preparar una campaña para el lanzamiento"),
        step("JUSTICIA", "consulta", "Revisar si el contrato con el proveedor tiene cláusula de exclusividad"),
    ))
    out = say(stack, u, MSG_CAMPANA_CONTRATO)
    assert len(fake.calls) == 1  # un solo viaje al clasificador
    assert out["success"] is True and out["executed_action"] is False
    assert [s["agent"] for s in out["steps"]] == ["PERSEO", "JUSTICIA"]
    assert [s["status"] for s in out["steps"]] == ["done", "done"]
    assert [s["kind"] for s in out["steps"]] == ["borrador", "consulta"]
    # orden y agente real de cada llamada al modelo: el primero que se ve es PERSEO y despues JUSTICIA
    llm = stack.llm
    assert llm.agents()[0] == "PERSEO" and "JUSTICIA" in llm.agents()
    first_j = llm.agents().index("JUSTICIA")
    assert all(a == "PERSEO" for a in llm.agents()[:first_j])
    for agent, messages in llm.calls:
        if agent in ("PERSEO", "JUSTICIA"):
            assert messages[0] == {"role": "system", "content": PROMPT[agent]}  # prompt integro
    assert "1. PERSEO" in out["message"] and "2. JUSTICIA" in out["message"]
    assert len(out["message"]) < 900  # mensaje breve: sin entregables incrustados
    assert approvals(db, u) == []


def test_pasos_ejecutados_por_cuatro_agentes_distintos_con_prompt_integro(db, stack):
    u, _ = _user(db)
    use_model(stack, classifier(
        step("RAFAEL", "consulta", "Calcular el IVA a pagar"),
        step("AFRODITA", "consulta", "Resumir los turnos de la semana"),
        step("JUSTICIA", "consulta", "Resumir las obligaciones de privacidad"),
    ))
    out = say(stack, u, "calcula el iva y resume los turnos y la privacidad")
    assert [s["status"] for s in out["steps"]] == ["done"] * 3
    seen = {a: m for a, m in stack.llm.calls}
    for agent in ("RAFAEL", "AFRODITA", "JUSTICIA"):
        assert seen[agent][0]["content"] == PROMPT[agent]


# ----------------------------------------------------------------------------- dependencia
def test_el_paso_2_recibe_el_resumen_del_paso_1(db, stack):
    u, _ = _user(db)
    use_model(stack, classifier(
        step("RAFAEL", "consulta", "Calcular cuanto IVA se paga este trimestre"),
        step("RAFAEL", "borrador", "Redactar un borrador de correo al gestor", deps=[1]),
    ))
    out = say(stack, u, MSG_IVA_CORREO)
    assert [s["status"] for s in out["steps"]] == ["done", "done"] and out["steps"][1]["depends_on"] == [1]
    (_, m1), (_, m2) = stack.llm.calls[0], stack.llm.calls[1]
    assert "Resultado de pasos previos" not in m1[-1]["content"]
    assert "Resultado de pasos previos" in m2[-1]["content"]
    assert "Respuesta de RAFAEL numero 1." in m2[-1]["content"]  # lo que dijo el paso 1
    assert "borrador" in m2[-1]["content"].lower()
    assert m2[0]["content"] == PROMPT["RAFAEL"]


def test_paso_independiente_no_recibe_resultado_de_otros(db, stack):
    u, _ = _user(db)
    use_model(stack, classifier(
        step("RAFAEL", "consulta", "Calcular el IVA"),
        step("AFRODITA", "consulta", "Resumir los turnos"),
    ))
    say(stack, u, "calcula el iva y resume los turnos")
    assert all("Resultado de pasos previos" not in m[-1]["content"] for _, m in stack.llm.calls)


# ----------------------------------------------------------------------------- consecuencias
def test_paso_con_consecuencias_deja_aprobacion_pendiente_y_no_se_ejecuta(db, stack):
    u, co = _user(db)
    use_model(stack, classifier(
        step("JUSTICIA", "consulta", "Revisar el contrato con el proveedor"),
        step("PERSEO", "accion_con_consecuencias", "Enviar la oferta a todos los clientes",
             action_type="send_campaign"),
        actions=[OFFER_ACT],
    ))
    out = say(stack, u, OFFER)
    assert out["executed_action"] is False and out["needs_confirmation"] is True and out["approval_id"]
    st = out["steps"]
    assert st[0]["status"] == "done" and st[1]["status"] == "pending_confirmation"
    assert st[1]["approval_id"] == out["approval_id"] and st[1]["agent"] == "PERSEO"
    rs = approvals(db, u)
    assert len(rs) == 1 and rs[0].status == "pending" and rs[0].action_type == "send_campaign"
    assert rs[0].company_id == co.id and rs[0].id == out["approval_id"]
    assert "confirmar" in out["message"] and "pendiente" in out["message"].lower()
    assert "PERSEO" not in stack.llm.agents()  # el paso con consecuencias no llama al agente


def test_dependiente_de_un_paso_con_consecuencias_no_se_ejecuta_el_independiente_si(db, stack):
    u, _ = _user(db)
    use_model(stack, classifier(
        step("PERSEO", "accion_con_consecuencias", "Enviar la oferta", action_type="send_campaign"),
        step("RAFAEL", "consulta", "Calcular el impacto fiscal de la oferta", deps=[1]),
        step("JUSTICIA", "consulta", "Revisar el contrato con el proveedor"),
        actions=[OFFER_ACT],
    ))
    out = say(stack, u, OFFER)
    s = out["steps"]
    assert [x["status"] for x in s] == ["pending_confirmation", "skipped", "done"]
    assert stack.llm.agents()[0] == "JUSTICIA" and "RAFAEL" not in stack.llm.agents()


def test_dos_acciones_con_consecuencias_siguen_preguntando_cual_primero(db, stack):
    u, _ = _user(db)
    use_model(stack, classifier(
        step("PERSEO", "accion_con_consecuencias", "Enviar la oferta", action_type="send_campaign"),
        step("ZEUS CORE", "accion_con_consecuencias", "Crear el cliente", action_type="create_customer"),
        actions=[OFFER_ACT, CUST_ACT],
    ))
    out = say(stack, u, "envía la oferta del 10% a todos mis clientes y crea el cliente María Pérez maria@x.es")
    assert out["needs_clarification"] and "una cada vez" in out["message"] and not out.get("steps")
    assert approvals(db, u) == [] and stack.llm.calls == []


def test_accion_afirmada_que_el_modelo_no_puso_como_paso_se_anade_al_final(db, stack):
    u, _ = _user(db)
    use_model(stack, classifier(
        step("JUSTICIA", "consulta", "Revisar el contrato"),
        step("RAFAEL", "consulta", "Calcular el IVA"),
        actions=[OFFER_ACT],
    ))
    out = say(stack, u, OFFER)
    assert [s["kind"] for s in out["steps"]] == ["consulta", "consulta", "accion_con_consecuencias"]
    assert out["steps"][2]["status"] == "pending_confirmation" and len(approvals(db, u)) == 1


def test_falta_un_dato_en_el_paso_con_consecuencias_no_crea_aprobacion(db, stack):
    u, _ = _user(db)
    cust = json.loads(json.dumps(CUST_ACT))
    cust["entities"]["emails"] = []  # el modelo no encontro correo
    use_model(stack, classifier(
        step("RAFAEL", "consulta", "Calcular el IVA"),
        step("ZEUS CORE", "accion_con_consecuencias", "Crear el cliente", action_type="create_customer"),
        actions=[cust],
    ))
    out = say(stack, u, "calcula el iva y crea el cliente María Pérez")
    assert [s["status"] for s in out["steps"]] == ["done", "needs_data"]
    assert approvals(db, u) == [] and out["needs_confirmation"] is False


# ----------------------------------------------------------------------------- modulos
def test_modulo_no_activo_bloquea_el_paso_dependientes_no_se_ejecutan_independientes_si(db, stack):
    u, co = _user(db, "office")  # no superusuario: THALOS (modulo admin) no esta activo
    use_model(stack, classifier(
        step("THALOS", "consulta", "Revisar los logs de seguridad"),
        step("RAFAEL", "consulta", "Resumir los hallazgos de seguridad en un informe fiscal", deps=[1]),
        step("AFRODITA", "consulta", "Resumir los turnos de la semana"),
    ))
    out = say(stack, u, "revisa los logs, haz un informe y resume los turnos")
    assert [s["status"] for s in out["steps"]] == ["blocked", "skipped", "done"]
    assert "solo está disponible para administradores" in out["steps"][0]["summary"]
    assert out["success"] is False
    assert stack.llm.agents() == ["AFRODITA"]
    assert rows(db, co.id, "ORQUESTAR", "route_to_agent")
    r = [x for x in rows(db, co.id, "ACTUAR", "plan_step") if x.status == "blocked_module"]
    assert r and r[0].details["module"] == "admin"


def test_superusuario_si_puede_planificar_con_thalos(db, stack):
    u, _ = _user(db, "office", superuser=True)
    use_model(stack, classifier(
        step("THALOS", "consulta", "Revisar los logs de seguridad"),
        step("AFRODITA", "consulta", "Resumir los turnos"),
    ))
    out = say(stack, u, "revisa los logs y resume los turnos")
    assert [s["status"] for s in out["steps"]] == ["done", "done"]
    assert stack.llm.calls[0][1][0]["content"] == PROMPT["THALOS"]


# ----------------------------------------------------------------------------- fallos
def test_fallo_de_un_agente_se_refleja_y_sus_dependientes_no_se_ejecutan(db, stack):
    u, co = _user(db)
    stack.llm.fail_for.add("RAFAEL")
    use_model(stack, classifier(
        step("RAFAEL", "consulta", "Calcular el IVA"),
        step("RAFAEL", "borrador", "Redactar el correo al gestor", deps=[1]),
        step("AFRODITA", "consulta", "Resumir los turnos"),
    ))
    out = say(stack, u, "calcula el iva, redacta el correo y resume los turnos")
    assert [s["status"] for s in out["steps"]] == ["failed", "skipped", "done"]
    assert out["success"] is False
    assert "falló" in out["message"] and "depende del paso 1" in out["steps"][1]["summary"]
    assert stack.llm.agents().count("RAFAEL") >= 1 and "AFRODITA" in stack.llm.agents()
    assert [x for x in rows(db, co.id, "ACTUAR", "plan_step") if x.status == "failed"]


# ----------------------------------------------------------------------------- fallback por reglas
def test_sin_modelo_el_plan_sale_de_las_reglas_en_orden_de_aparicion(db, stack):
    u, _ = _user(db)
    out = say(stack, u, MSG_CAMPANA_CONTRATO)  # get_client -> None
    assert [s["agent"] for s in out["steps"]] == ["PERSEO", "JUSTICIA"]
    assert [s["status"] for s in out["steps"]] == ["done", "done"]
    assert all(s["kind"] in ("consulta", "borrador") for s in out["steps"])
    assert stack.llm.calls[0][0] == "PERSEO" and stack.llm.calls[0][1][0]["content"] == PROMPT["PERSEO"]
    first_j = stack.llm.agents().index("JUSTICIA")
    assert stack.llm.calls[first_j][1][0]["content"] == PROMPT["JUSTICIA"]
    plan_rows = rows(db, _u_company(db, u), "ORQUESTAR", "plan")
    assert plan_rows and plan_rows[0].details["source"] == "rules"


def _u_company(db, user):
    return db.query(UserCompany).filter(UserCompany.user_id == user.id).first().company_id


def test_un_solo_dominio_no_genera_plan(db, stack):
    u, _ = _user(db)
    out = say(stack, u, "calcula el IVA y la factura del trimestre")
    assert not out.get("steps")


def test_reglas_nunca_crean_pasos_con_consecuencias_ni_con_negacion(db, stack):
    u, _ = _user(db)
    out = say(stack, u, "no revises el contrato ni prepares la campaña")
    assert not out.get("steps") and approvals(db, u) == []
    plan = jp.plan_from_rules("prepara la campaña y revisa el contrato")
    assert plan and all(s.kind != "accion_con_consecuencias" for s in plan.steps)


def test_modelo_invalido_cae_a_reglas(db, stack):
    u, _ = _user(db)
    use_model(stack, raw="esto no es json")
    out = say(stack, u, MSG_CAMPANA_CONTRATO)
    assert [s["agent"] for s in out["steps"]] == ["PERSEO", "JUSTICIA"]


# ----------------------------------------------------------------------------- limites y validacion
def test_limite_de_pasos_del_modelo(db, stack):
    u, _ = _user(db)
    use_model(stack, classifier(*[step("RAFAEL", "consulta", f"Tarea {i}") for i in range(1, 7)]))
    out = say(stack, u, "haz seis cosas de IVA y gastos y facturas y demas")
    assert len(out["steps"]) == jp.MAX_STEPS == 4
    assert "primeros pasos" in out["message"] and len(stack.llm.calls) >= 4


def test_limite_de_pasos_por_reglas():
    plan = jp.plan_from_rules(
        "prepara la campaña, revisa la factura, revisa el contrato, revisa las nóminas y revisa los logs",
        is_superuser=True)
    assert plan and len(plan.steps) == 4 and plan.truncated == 1
    assert [s.agent for s in plan.steps] == ["PERSEO", "RAFAEL", "JUSTICIA", "AFRODITA"]


@pytest.mark.parametrize("steps", [
    [step("RAFAEL", "consulta", "A", deps=[2]), step("RAFAEL", "consulta", "B")],            # dependencia hacia delante
    [step("RAFAEL", "consulta", "A"), step("RAFAEL", "consulta", "B", deps=[2])],            # sobre si mismo
    [step("RAFAEL", "consulta", ""), step("JUSTICIA", "consulta", "B")],                      # objetivo vacio
    [step("ZEUS CORE", "consulta", "A"), step("RAFAEL", "consulta", "B")],                    # ZEUS no es paso de consulta
    [step("RAFAEL", "accion_con_consecuencias", "A", action_type="send_campaign"),
     step("JUSTICIA", "consulta", "B")],                                                     # accion sin clasificar en `actions`
])
def test_planes_invalidos_se_descartan(db, stack, steps):
    u, _ = _user(db)
    use_model(stack, classifier(*steps))
    out = say(stack, u, "calcula el iva y revisa el contrato")
    assert not out.get("steps") or all(s["status"] != "pending_confirmation" for s in out["steps"])
    assert approvals(db, u) == []


def test_esquema_cerrado_agente_o_tipo_fuera_de_catalogo_es_salida_invalida():
    from pydantic import ValidationError

    base = classifier(step("RAFAEL", "consulta", "x"), step("JUSTICIA", "consulta", "y"))
    mc.ClassifierOutput.model_validate(base)
    for bad in (step("HACKER", "consulta", "x"), step("RAFAEL", "ejecutar_sql", "x"),
                {**step("RAFAEL", "consulta", "x"), "company_id": 999}):
        with pytest.raises(ValidationError):
            mc.ClassifierOutput.model_validate({**base, "steps": [bad, step("JUSTICIA", "consulta", "y")]})


def test_el_modelo_no_puede_cambiar_empresa_ni_usuario(db, stack):
    u, co = _user(db)
    seen = []
    import services.unified_agent_runtime as rt

    real = rt.run_chat

    def spy(agent, thread, message, company_id, context):
        seen.append((agent, company_id, context.get("company_id"), context.get("user_id")))
        return real(agent, thread, message, company_id, context)

    stack.mp.setattr(rt, "run_chat", spy)
    use_model(stack, classifier(
        {**step("RAFAEL", "consulta", "Calcular el IVA de la empresa 999999"), "company_id": 999999},
        step("AFRODITA", "consulta", "Resumir los turnos"),
    ))
    out = say(stack, u, "calcula el iva y resume los turnos", )
    assert out["steps"]  # salida invalida (campo extra) -> reglas
    assert seen and all(cid == co.id and ctx_cid == co.id and uid == u.id for _, cid, ctx_cid, uid in seen)


# ----------------------------------------------------------------------------- J7
def test_registro_j7_mismo_correlation_id_en_todos_los_pasos(db, stack):
    u, co = _user(db)
    use_model(stack, classifier(
        step("RAFAEL", "consulta", "Calcular el IVA"),
        step("PERSEO", "accion_con_consecuencias", "Enviar la oferta", action_type="send_campaign", deps=[1]),
        step("AFRODITA", "consulta", "Resumir los turnos"),
        actions=[OFFER_ACT],
    ))
    out = say(stack, u, OFFER)
    rid = out["request_id"]
    assert rid
    allrows = rows(db, co.id)
    mine = [r for r in allrows if (r.details or {}).get("correlation_id") == rid]
    plan_row = [r for r in mine if r.details["chain_step"] == "ORQUESTAR" and r.details["action"] == "plan"]
    assert len(plan_row) == 1 and plan_row[0].details["count"] == 3
    steps_rows = [r for r in mine if r.details["action"] == "plan_step"]
    assert sorted(r.details["step_n"] for r in steps_rows) == [1, 2, 3]
    assert {r.details["chain_step"] for r in steps_rows} == {"ACTUAR"}
    by_n = {r.details["step_n"]: r for r in steps_rows}
    assert by_n[1].status == "success" and by_n[1].agent_name == "RAFAEL"
    assert by_n[2].status == "needs_confirmation" and by_n[2].details["approval_id"] == out["approval_id"]
    assert by_n[2].details["executed"] is False and by_n[3].status == "success"
    # el contenido de los objetivos/respuestas no se vuelca al registro
    assert "Respuesta de" not in json.dumps([r.details for r in steps_rows])
    # la aprobacion y el contexto de memoria de cada agente comparten el mismo id
    assert [r for r in mine if r.details["action"] == "load_conversation_memory"]
    assert [r for r in mine if r.details["action"] == "send_campaign" and r.status == "needs_confirmation"]


# ----------------------------------------------------------------------------- aislamiento
def test_aislamiento_entre_empresas(db, stack):
    ua, ca = _user(db, "office", name="Empresa A Oficina")
    ub, cb = _user(db, "bar_restaurant", name="Empresa B Bar")
    import services.unified_agent_runtime as rt

    ctxs = []
    real = rt.run_chat

    def spy(agent, thread, message, company_id, context):
        ctxs.append((company_id, context["zeus_global_context"]["company_name"], context["user_id"]))
        return real(agent, thread, message, company_id, context)

    stack.mp.setattr(rt, "run_chat", spy)
    plan = classifier(
        step("RAFAEL", "consulta", "Calcular el IVA"),
        step("PERSEO", "accion_con_consecuencias", "Enviar la oferta", action_type="send_campaign"),
        actions=[OFFER_ACT],
    )
    use_model(stack, plan)
    oa = say(stack, ua, OFFER, thread="mismo-hilo")
    ob = say(stack, ub, OFFER, thread="mismo-hilo")
    assert oa["approval_id"] != ob["approval_id"]
    assert ctxs[0] == (ca.id, "Empresa A Oficina", ua.id) and ctxs[1] == (cb.id, "Empresa B Bar", ub.id)
    ra, rb = approvals(db, ua), approvals(db, ub)
    assert [r.company_id for r in ra] == [ca.id] and [r.company_id for r in rb] == [cb.id]
    # B no puede confirmar la aprobacion de A: su «confirmar» solo ve la suya (empresa B)
    out_b = say(stack, ub, "confirmar", thread="otro-hilo")
    assert "No hay ninguna acción pendiente" in out_b["message"]
    assert all(r.company_id == ca.id for r in approvals(db, ua))
    assert "Empresa A" not in json.dumps(ob) and "Empresa B" not in json.dumps(oa)
    assert rows(db, ca.id, "ACTUAR", "plan_step") and not any(
        (r.details or {}).get("correlation_id") == ob["request_id"] for r in rows(db, ca.id))


def test_el_contexto_de_los_agentes_no_lleva_datos_personales(db, stack):
    u, _ = _user(db)
    seen = []
    import services.unified_agent_runtime as rt

    real = rt.run_chat

    def spy(agent, thread, message, company_id, context):
        seen.append(context["zeus_global_context"])
        return real(agent, thread, message, company_id, context)

    stack.mp.setattr(rt, "run_chat", spy)
    use_model(stack, classifier(step("RAFAEL", "consulta", "Calcular el IVA"),
                                step("AFRODITA", "consulta", "Resumir los turnos")))
    say(stack, u, "calcula el iva y resume los turnos")
    assert seen
    for gc in seen:
        assert set(gc) == {"company_name", "company_type", "active_modules"}
        assert u.email not in json.dumps(gc)
    for _, messages in stack.llm.calls:
        assert u.email not in json.dumps(messages)


def test_mensaje_simple_sin_plan_sigue_igual(db, stack):
    u, _ = _user(db)
    out = say(stack, u, "hola, ¿qué tal?")
    assert not out.get("steps") and "Plan de" not in out["message"]
