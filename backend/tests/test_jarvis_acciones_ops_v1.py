"""J9e: acciones de JUSTICIA/AFRODITA en el chat JARVIS (consultas sin confirmacion, escrituras por vista
previa + aprobacion J3b), clasificador J8b ampliado con validacion en servidor, pasos de plan J9b con
consultas reales y /chat/agents/coordinate unificado con el ejecutor de planes. Sin red ni LLM real."""

from __future__ import annotations

import json
import time
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from agents.zeus_core import ZeusCore
from app.api.v1.endpoints import chat as chat_endpoint
from app.core.auth import get_current_active_user
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.agent_activity import AgentActivity
from app.models.company import Company, UserCompany
from app.models.erp import InventoryMovement, Product
from app.models.legal_document import LegalDocument
from app.models.ops_route import OpsRoute
from app.models.user import User
from app.models.zeus_pending_approval import ZeusPendingApproval
from services import jarvis_model_comprehension as mc
from services import jarvis_ops_actions as ops
from services import module_gate

import services.unified_agent_runtime as _rt0

_REAL_RUN_CHAT = _rt0.run_chat
JARVIS = "/api/v1/jarvis/message"
COORD = "/api/v1/chat/agents/coordinate"
ROUTE_MSG = "crea una ruta de Madrid a Valencia"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    import services.unified_agent_runtime as rt

    monkeypatch.setattr(rt, "run_chat", lambda *a, **k: {"success": True, "message": "respuesta-llm-stub"})
    monkeypatch.setattr(mc, "get_client", lambda: None)  # por defecto: sin modelo (criterio estricto)
    for k in ("JARVIS_MODEL_COMPREHENSION", "JARVIS_CLASSIFIER_MODEL", "JARVIS_CLASSIFIER_TIMEOUT_SEC",
              "JARVIS_CLASSIFIER_MIN_CERTAINTY", "JARVIS_CLASSIFIER_COMPANY_DAILY_BUDGET_USD",
              "JARVIS_CLASSIFIER_GLOBAL_DAILY_BUDGET_USD", "JARVIS_CLASSIFIER_JSON_MODE"):
        monkeypatch.delenv(k, raising=False)


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


@pytest.fixture()
def writes_on(monkeypatch):
    monkeypatch.setattr("services.afrodita_unified_control.writes_enabled", lambda: True)


def _user(db, role="owner", company=None, company_type="bar_restaurant", superuser=False):
    suf = uuid.uuid4().hex[:8]
    if company is None:
        company = Company(company_name=f"J9e {suf}", slug=f"j9e-{suf}", company_type=company_type)
        db.add(company)
        db.flush()
    u = User(email=f"j9e_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
             full_name="J9e", is_active=True, is_superuser=superuser)
    db.add(u)
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=company.id, role=role))
    db.commit()
    db.refresh(u)
    db.refresh(company)
    return u, company


def _product(db, company, name=None, stock=10.0):
    suf = uuid.uuid4().hex[:6]
    p = Product(sku=f"J9E-{suf}", name=name or f"Harina {suf}", price=1.5, company_id=company.id,
                track_inventory=True, quantity_on_hand=stock, low_stock_threshold=2.0)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


_n = {"i": 0}


def say(client, user, message, thread=None):
    _n["i"] += 1
    app.dependency_overrides[get_current_active_user] = lambda: user
    r = client.post(JARVIS, json={"message": message, "thread_id": thread or f"t-{uuid.uuid4().hex[:8]}"})
    assert r.status_code == 200, r.text
    return r.json()


def approvals(db, user):
    db.expire_all()
    return db.query(ZeusPendingApproval).filter(ZeusPendingApproval.user_id == user.id).all()


def rows(db, company_id, step=None, action=None, status=None):
    db.expire_all()
    out = db.query(AgentActivity).filter(AgentActivity.company_id == company_id).all()
    return [r for r in out
            if (step is None or (r.details or {}).get("chain_step") == step)
            and (action is None or (r.details or {}).get("action") == action)
            and (status is None or r.status == status)]


def prepared(out):
    return bool(out.get("needs_confirmation") and out.get("approval_id")) and not out.get("executed")


# =============================================================== CONSULTAS (sin confirmacion)
def test_estado_legal_por_chat_con_datos_de_la_empresa_y_aislado(db, client):
    ua, ca = _user(db)
    ub, cb = _user(db)
    for u, c, n in ((ua, ca, 2), (ub, cb, 5)):
        for _ in range(n):
            db.add(LegalDocument(user_id=u.id, company_id=c.id, doc_type="contrato", content="x", status="draft"))
    db.commit()
    oa, ob = say(client, ua, "¿cuál es el estado legal?"), say(client, ub, "dime el estado legal de mi cuenta")
    assert "2 documentos legales" in oa["message"] and "5 documentos legales" in ob["message"]
    assert not approvals(db, ua) and not approvals(db, ub)  # 0 aprobaciones
    assert rows(db, ca.id, action="get_legal_status", status="completed")


def test_auditoria_de_cumplimiento_por_chat_se_ejecuta_sin_aprobacion(db, client):
    u, c = _user(db)
    db.add(LegalDocument(user_id=u.id, company_id=c.id, doc_type="nda", content="x", status="draft"))
    db.commit()
    out = say(client, u, "ejecuta la auditoría de cumplimiento")
    assert out["success"] is not False and "auditor" in out["message"].lower()
    assert not approvals(db, u)
    assert rows(db, c.id, step="ACTUAR", action="run_compliance_audit")
    out = say(client, u, "no hagas la auditoría de cumplimiento")  # negacion: no se ejecuta
    assert "no he hecho nada" in out["message"].lower() or "no lo he entendido" in out["message"].lower()


def test_inventario_por_chat_solo_de_su_empresa(db, client):
    ua, ca = _user(db)
    ub, cb = _user(db)
    for _ in range(3):
        _product(db, ca)
    _product(db, cb)
    oa = say(client, ua, "¿cómo está el inventario?")
    ob = say(client, ub, "dime el estado del inventario")
    assert "3 referencias" in oa["message"] and "1 referencias" in ob["message"]
    assert not approvals(db, ua)


def test_turnos_por_chat_sigue_funcionando(db, client):
    u, c = _user(db)
    out = say(client, u, "estado de mis turnos")
    assert out["message"] and not approvals(db, u)


def test_modulo_no_activo_bloquea_consultas_y_lo_registra(db, client, monkeypatch):
    u, c = _user(db)
    real = module_gate.active_modules
    # turnos: modulo real `control_horario`
    monkeypatch.setattr(module_gate, "active_modules", lambda d, us: {**real(d, us), "control_horario": False})
    out = say(client, u, "estado de mis turnos")
    assert out["success"] is False and "módulo" in out["message"]
    assert rows(db, c.id, step="ORQUESTAR", action="shift_status", status="blocked_module")
    # JUSTICIA: modulo `agents` (el endpoint ya exige `agents` para ZEUS CORE, asi que se mapea a otro modulo
    # SOLO para comprobar el mecanismo de bloqueo de la accion en el orquestador)
    monkeypatch.setitem(module_gate.ACTION_MODULE, "get_legal_status", "payroll")
    monkeypatch.setattr(module_gate, "active_modules", lambda d, us: {**real(d, us), "payroll": False})
    out = say(client, u, "¿cuál es el estado legal?")
    assert out["success"] is False and "módulo" in out["message"]
    assert rows(db, c.id, step="ORQUESTAR", action="get_legal_status", status="blocked_module")
    assert not approvals(db, u)


# =============================================================== ESCRITURAS (vista previa + aprobacion)
def test_ruta_por_chat_prepara_aprobacion_no_ejecuta_y_confirmar_la_crea(db, client, writes_on):
    u, c = _user(db)
    out = say(client, u, ROUTE_MSG, thread="t-ruta")
    assert prepared(out) and "Madrid -> Valencia" in out["message"] and "confirmar" in out["message"]
    ap = approvals(db, u)
    assert len(ap) == 1 and ap[0].agent_name == "AFRODITA" and ap[0].action_type == "create_ops_route"
    assert ap[0].status == "pending" and ap[0].company_id == c.id
    assert db.query(OpsRoute).filter(OpsRoute.company_id == c.id).count() == 0  # nada ejecutado
    done = say(client, u, "confirmar", thread="t-ruta")
    assert done["success"] is True and done["executed_action"] is True
    db.expire_all()
    assert db.query(OpsRoute).filter(OpsRoute.company_id == c.id).count() == 1
    assert approvals(db, u)[0].status == "executed"


def test_movimiento_por_chat_entrada_y_salida_con_efecto_en_bd(db, client, writes_on):
    u, c = _user(db)
    p = _product(db, c, name="Harina de trigo", stock=10)
    out = say(client, u, "por favor, registra una entrada de 5 unidades de Harina de trigo", thread="t-mov")
    assert prepared(out) and "10 -> 15" in out["message"] and p.sku in out["message"]
    assert approvals(db, u)[0].agent_name == "AFRODITA"
    db.refresh(p)
    assert p.quantity_on_hand == 10  # la vista previa no toca el stock
    say(client, u, "confirmar", thread="t-mov")
    db.expire_all()
    p = db.query(Product).filter(Product.id == p.id).one()
    assert p.quantity_on_hand == 15
    assert db.query(InventoryMovement).filter(InventoryMovement.product_id == p.id).count() == 1
    out = say(client, u, "registra una salida de 3 uds de Harina de trigo en el inventario.", thread="t-mov2")
    assert prepared(out) and "15 -> 12" in out["message"]
    say(client, u, "sí", thread="t-mov2")
    db.expire_all()
    assert db.query(Product).filter(Product.id == p.id).one().quantity_on_hand == 12


def test_producto_de_otra_empresa_no_prepara_nada(db, client, writes_on):
    ua, ca = _user(db)
    ub, cb = _user(db)
    pb = _product(db, cb, name="Aceite ajeno", stock=7)
    out = say(client, ua, "registra una entrada de 5 unidades de Aceite ajeno")
    assert not prepared(out) and "no encuentro el producto" in out["message"].lower()
    assert not approvals(db, ua)
    # por SKU de la otra empresa tampoco
    out = say(client, ua, f"registra una salida de 1 unidades de {pb.sku}")
    assert not prepared(out) and not approvals(db, ua)
    db.refresh(pb)
    assert pb.quantity_on_hand == 7


def test_producto_inexistente_o_stock_negativo_no_preparan(db, client, writes_on):
    u, c = _user(db)
    _product(db, c, name="Cafe molido", stock=2)
    assert not prepared(say(client, u, "registra una entrada de 5 unidades de Producto Fantasma"))
    out = say(client, u, "registra una salida de 9 unidades de Cafe molido")
    assert not prepared(out) and "negativo" in out["message"].lower()
    assert not approvals(db, u)


@pytest.mark.parametrize("msg", [
    "no registres una entrada de 5 unidades de Cafe molido",
    "nunca crees una ruta de Madrid a Valencia",
    "quizás deberíamos registrar una entrada de 5 unidades de Cafe molido",
    "no sé si crear una ruta de Madrid a Valencia",
    "crea una ruta de Madrid a Valencia pero no la ejecutes",
    "registra una entrada de 5 kg de Cafe molido",
    "registra un ajuste de 5 unidades de Cafe molido",
    "registra una entrada de 5 unidades de Cafe molido y envía la oferta a todos mis clientes",
    "crea una ruta",
    "si quieres crea una ruta de Madrid a Valencia",
])
def test_negacion_duda_o_fuera_de_plantilla_no_preparan(db, client, writes_on, msg):
    u, c = _user(db)
    _product(db, c, name="Cafe molido", stock=5)
    out = say(client, u, msg)
    assert not prepared(out) and not approvals(db, u)


def test_escrituras_deshabilitadas_por_flags_no_crean_aprobacion(db, client):
    u, c = _user(db)  # sin writes_on: AFRODITA en modo solo lectura por defecto
    out = say(client, u, ROUTE_MSG)
    assert not prepared(out) and "deshabilitada" in out["message"].lower()
    assert not approvals(db, u)


def test_roles_miembro_puede_ruta_pero_no_movimiento(db, client, writes_on):
    owner, c = _user(db)
    member, _ = _user(db, role="member", company=c)
    _product(db, c, name="Cafe molido", stock=5)
    assert prepared(say(client, member, ROUTE_MSG))  # create_ops_route: member
    out = say(client, member, "registra una entrada de 5 unidades de Cafe molido")
    assert not prepared(out) and "rol" in out["message"].lower()
    assert len(approvals(db, member)) == 1


def test_otro_usuario_no_puede_confirmar_la_accion_de_otro(db, client, writes_on):
    owner, c = _user(db)
    other, _ = _user(db, company=c)
    assert prepared(say(client, owner, ROUTE_MSG, thread="t-shared"))
    out = say(client, other, "confirmar", thread="t-shared")
    assert out["success"] is False and "no hay ninguna acción pendiente" in out["message"].lower()
    db.expire_all()
    assert db.query(OpsRoute).filter(OpsRoute.company_id == c.id).count() == 0


def test_modulo_no_activo_no_impide_preparar_ruta_pero_si_el_ejecutor_confirma_ok(db, client, writes_on):
    # create_ops_route/inventario no tienen modulo propio (EXECUTOR_UNMAPPED_ACTIONS): permitidas
    assert module_gate.check_executor_action(None, None, "create_ops_route") is None


# =============================================================== CLASIFICADOR (modelo) con validacion en servidor
def clf(*actions, steps=(), overall=0.95, nc=False, q=None):
    return {"actions": list(actions), "steps": list(steps), "overall_certainty": overall,
            "needs_clarification": nc, "clarification_question": q, "notes": ""}


def mov(product="Cafe molido", qty=(5,), movement="in", pol="affirm", cert=0.95):
    return {"action_type": "create_inventory_movement", "polarity": pol, "certainty": cert,
            "entities": {"product": product, "quantities": list(qty), "movement": movement}}


def route(origin="Madrid", dest="Valencia", pol="affirm", cert=0.95):
    return {"action_type": "create_ops_route", "polarity": pol, "certainty": cert,
            "entities": {"origin": origin, "destination": dest}}


class FakeClient:
    def __init__(self, data):
        self.data, self.calls = data, []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(self.data)))],
            usage=SimpleNamespace(prompt_tokens=900, completion_tokens=80))


def use(monkeypatch, data):
    fake = FakeClient(data)
    monkeypatch.setattr(mc, "get_client", lambda: fake)
    return fake


def test_modelo_orden_indirecta_de_movimiento_prepara_aprobacion(db, client, writes_on, monkeypatch):
    u, c = _user(db)
    p = _product(db, c, name="Cafe molido", stock=4)
    use(monkeypatch, clf(mov()))
    out = say(client, u, "no te olvides de anotar la entrada de 5 unidades de Cafe molido")
    assert prepared(out) and "4 -> 9" in out["message"]
    assert approvals(db, u)[0].agent_name == "AFRODITA"
    db.refresh(p)
    assert p.quantity_on_hand == 4


@pytest.mark.parametrize("bad,msg", [
    (mov(product="Cafe molido especial"), "anota la entrada de 5 unidades de Cafe molido"),   # producto inventado
    (mov(qty=(50,)), "anota la entrada de 5 unidades de Cafe molido"),                      # cantidad ausente
    (mov(movement="out"), "anota la entrada de 5 unidades de Cafe molido"),                  # tipo contrario
    (mov(movement="adjustment"), "anota el ajuste de 5 unidades de Cafe molido"),            # ajuste no soportado
    (mov(qty=(5, 6)), "anota la entrada de 5 unidades de Cafe molido"),                      # dos cantidades
    (mov(qty=(-5,)), "anota la entrada de -5 unidades de Cafe molido"),                      # negativa
    (mov(product="unidades"), "anota la entrada de 5 unidades de Cafe molido"),              # producto = palabra de plantilla
    (route(dest="Sevilla"), "anota una ruta de Madrid a Valencia"),                           # destino inventado
    (route(origin="Madrid; DROP TABLE"), "anota una ruta de Madrid; DROP TABLE a Valencia"), # forma invalida
])
def test_modelo_malicioso_o_inconsistente_no_prepara(db, client, writes_on, monkeypatch, bad, msg):
    u, c = _user(db)
    _product(db, c, name="Cafe molido", stock=5)
    use(monkeypatch, clf(bad))
    out = say(client, u, msg)
    assert not prepared(out) and not approvals(db, u)
    db.expire_all()
    assert db.query(OpsRoute).filter(OpsRoute.company_id == c.id).count() == 0


def test_modelo_negate_duda_y_conflicto_no_preparan(db, client, writes_on, monkeypatch):
    u, c = _user(db)
    _product(db, c, name="Cafe molido", stock=5)
    use(monkeypatch, clf(mov(pol="negate")))
    assert not prepared(say(client, u, "no anotes la entrada de 5 unidades de Cafe molido"))
    use(monkeypatch, clf(mov(pol="uncertain", cert=0.4), nc=True, overall=0.4))
    assert not prepared(say(client, u, "igual anoto la entrada de 5 unidades de Cafe molido"))
    # el modelo dice affirm pero el texto niega con certeza no reforzada -> pregunta
    use(monkeypatch, clf(mov(cert=0.85), overall=0.85))
    assert not prepared(say(client, u, "no registres la entrada de 5 unidades de Cafe molido"))
    assert not approvals(db, u)


def test_modelo_producto_de_otra_empresa_no_prepara(db, client, writes_on, monkeypatch):
    ua, ca = _user(db)
    ub, cb = _user(db)
    _product(db, cb, name="Aceite ajeno", stock=7)
    use(monkeypatch, clf(mov(product="Aceite ajeno")))
    out = say(client, ua, "no te olvides de anotar la entrada de 5 unidades de Aceite ajeno")
    assert not prepared(out) and not approvals(db, ua)


def test_modelo_accion_fuera_de_catalogo_es_salida_invalida_y_cae_a_reglas(db, client, writes_on, monkeypatch):
    u, c = _user(db)
    bad = clf(route())
    bad["actions"][0]["action_type"] = "delete_everything"
    use(monkeypatch, bad)
    out = say(client, u, "no te olvides de anotar una ruta de Madrid a Valencia")
    assert not prepared(out) and not approvals(db, u)


# =============================================================== PLAN J9b con consultas reales
def step(agent, kind, objective, deps=(), action_type=None):
    return {"agent": agent, "kind": kind, "objective": objective, "depends_on": list(deps),
            "action_type": action_type}


def test_plan_con_consultas_reales_de_justicia_y_afrodita(db, client, monkeypatch):
    u, c = _user(db)
    db.add(LegalDocument(user_id=u.id, company_id=c.id, doc_type="nda", content="x", status="draft"))
    db.commit()
    for _ in range(2):
        _product(db, c)
    use(monkeypatch, clf(steps=[
        step("JUSTICIA", "consulta", "Estado legal de la empresa", action_type="get_legal_status"),
        step("AFRODITA", "consulta", "Estado del inventario", action_type="get_inventory_status"),
    ]))
    out = say(client, u, "dime el estado legal y el inventario y registra todo")
    assert [s["status"] for s in out["steps"]] == ["done", "done"]
    assert "1 documentos legales" in out["steps"][0]["text"]
    assert "2 referencias" in out["steps"][1]["text"]
    assert not approvals(db, u)
    ev = rows(db, c.id, step="ACTUAR", action="plan_step")
    assert len(ev) == 2 and all(r.status == "completed" or r.status == "success" for r in ev)


def test_plan_consulta_real_con_agente_incorrecto_o_kind_incorrecto_se_descarta(db, client, monkeypatch):
    u, c = _user(db)
    for steps_ in (
        [step("AFRODITA", "consulta", "x", action_type="get_legal_status"),
         step("JUSTICIA", "consulta", "y", action_type="get_legal_status")],
        [step("JUSTICIA", "borrador", "x", action_type="get_legal_status"),
         step("JUSTICIA", "consulta", "y", action_type="get_legal_status")],
        [step("ZEUS CORE", "consulta", "x", action_type="get_inventory_status"),
         step("AFRODITA", "consulta", "y", action_type="get_inventory_status")],
    ):
        use(monkeypatch, clf(steps=steps_))
        out = say(client, u, "dime el estado legal y el inventario y registra todo")
        assert not out.get("steps")  # plan invalido: no hay pasos ejecutados
    assert not approvals(db, u)


def test_plan_modulo_inactivo_bloquea_el_paso_y_sus_dependientes(db, client, monkeypatch):
    u, c = _user(db)
    _product(db, c)
    real = module_gate.check_agent
    monkeypatch.setattr(module_gate, "check_agent", lambda d, us, ag: (
        {"module": "agents", "message": "Tu empresa no tiene activo el módulo Agentes."} if ag == "JUSTICIA"
        else real(d, us, ag)))
    use(monkeypatch, clf(steps=[
        step("JUSTICIA", "consulta", "Estado legal", action_type="get_legal_status"),
        step("AFRODITA", "consulta", "Inventario", deps=[1], action_type="get_inventory_status"),
    ]))
    out = say(client, u, "dime el estado legal y el inventario y registra todo")
    assert [s["status"] for s in out["steps"]] == ["blocked", "skipped"]
    assert not rows(db, c.id, action="get_inventory_status", status="completed")


def test_plan_escritura_afrodita_como_paso_con_consecuencias_solo_prepara(db, client, writes_on, monkeypatch):
    u, c = _user(db)
    p = _product(db, c, name="Cafe molido", stock=5)
    use(monkeypatch, clf(
        mov(),
        steps=[step("AFRODITA", "consulta", "Estado del inventario", action_type="get_inventory_status"),
               step("AFRODITA", "accion_con_consecuencias", "Registrar la entrada", deps=[1],
                    action_type="create_inventory_movement")]))
    out = say(client, u, "mira el inventario y luego registra la entrada de 5 unidades de Cafe molido")
    assert out["needs_confirmation"] is True and out["approval_id"] and out["executed_action"] is False
    assert [s["status"] for s in out["steps"]] == ["done", "pending_confirmation"]
    assert "5 -> 10" in out["steps"][1]["text"]
    db.refresh(p)
    assert p.quantity_on_hand == 5
    assert approvals(db, u)[0].agent_name == "AFRODITA"


# =============================================================== reglas puras y catalogo
def test_catalogo_cerrado_y_tipos_ampliados():
    from app.schemas.zeus_action import ZeusAction
    from services.jarvis_classifier_prompt import ACTION_TYPES, CLASSIFIER_SYSTEM_PROMPT

    for a in ("get_legal_status", "run_compliance_audit", "get_inventory_status", "create_ops_route",
              "create_inventory_movement"):
        ZeusAction(action_type=a, user_id=1)
    assert {"create_ops_route", "create_inventory_movement"} <= set(ACTION_TYPES)
    assert "create_inventory_movement" in CLASSIFIER_SYSTEM_PROMPT and "get_legal_status" in CLASSIFIER_SYSTEM_PROMPT
    with pytest.raises(Exception):
        ZeusAction(action_type="delete_everything", user_id=1)


@pytest.mark.parametrize("msg", [
    "crea una ruta de Madrid a Valencia", "por favor, crea la ruta operativa de Alcalá de Henares a Madrid.",
    "quiero que registres una entrada de 5 unidades de Harina", "anota una salida de 2,5 uds del Harina de trigo",
])
def test_plantillas_ops_aceptan_ordenes_claras(msg):
    from services.intent_parser import parse_intent

    t = parse_intent(msg)
    assert t.intent in ("create_ops_route", "create_inventory_movement") and not t.needs_clarification
    assert t.requires_confirmation is True


@pytest.mark.parametrize("msg", [
    "crea una ruta de madrid; drop table a valencia", "crea una ruta de Madrid a Valencia 😀",
    "registra una entrada de 5 unidades de harina... gracias", "registra una entrada de 5 unidades de ¿Harina?",
    "registra una entrada de -5 unidades de Harina", "registra una entrada de 5 unidades de Harina sin gluten",
    "registra la entrada de 5 unidades de Harina o no", "crea una ruta de No a Valencia",
])
def test_plantillas_ops_rechazan_lo_ambiguo(msg):
    from services.intent_parser import parse_intent

    t = parse_intent(msg)
    assert not (t.intent in ("create_ops_route", "create_inventory_movement") and not t.needs_clarification), msg


def test_resolve_product_exacto_ambiguo_y_ajeno(db):
    u, c = _user(db)
    _, c2 = _user(db)
    a = _product(db, c, name="Cafe de Colombia")
    _product(db, c, name="Dup")
    _product(db, c, name="dup")
    other = _product(db, c2, name="Solo ajeno")
    assert ops.resolve_product(db, u, c.id, "cafe de colombia")[0].id == a.id
    assert ops.resolve_product(db, u, c.id, a.sku)[0].id == a.id
    assert ops.resolve_product(db, u, c.id, "Dup")[0] is None   # ambiguo
    assert ops.resolve_product(db, u, c.id, "Solo ajeno")[0] is None
    assert ops.resolve_product(db, u, c.id, other.sku)[0] is None


# =============================================================== /chat/agents/coordinate unificado
class StubAgent:
    def __init__(self, name, result=None):
        self.name, self.seen = name, []
        self._result = result if result is not None else {"success": True, "content": f"ok-{name}", "message": f"ok-{name}"}

    def set_zeus_core_ref(self, z):
        pass

    def process_request(self, ctx):
        self.seen.append(dict(ctx))
        if isinstance(self._result, Exception):
            raise self._result
        return dict(self._result)


@pytest.fixture()
def coord(monkeypatch):
    import services.unified_agent_runtime as rt

    monkeypatch.setattr(rt, "run_chat", _REAL_RUN_CHAT)  # coordinate usa el run_chat real (agentes stub)
    z = ZeusCore()
    ag = {n: StubAgent(n) for n in ("PERSEO", "RAFAEL", "THALOS", "JUSTICIA", "AFRODITA")}
    for a in ag.values():
        z.register_agent(a)
    monkeypatch.setattr(chat_endpoint, "ensure_agent_stack", lambda: None)
    monkeypatch.setattr(chat_endpoint, "zeus", z)
    monkeypatch.setattr(chat_endpoint, "AGENTS", {"ZEUS CORE": z, **ag})
    monkeypatch.setattr(rt, "_get_agents", lambda: {"ZEUS CORE": z, **ag})
    yield ag


def post_coord(client, user, agents, task="analiza la situación", context=None):
    app.dependency_overrides[get_current_active_user] = lambda: user
    return client.post(COORD, json={"task_description": task, "required_agents": agents, "context": context})


def test_coordinate_ejecuta_pasos_j9b_con_j7_por_paso_y_contexto_de_servidor(db, client, coord):
    u, c = _user(db)
    r = post_coord(client, u, ["perseo", "rafael"], context={"company_id": 999999, "user_id": 999999,
                                                              "other_agents": ["EVIL"], "workflow_id": "wf"})
    assert r.status_code == 200, r.text
    b = r.json()
    # contrato conservado
    assert b["success"] is True and b["agents_involved"] == ["PERSEO", "RAFAEL"] and b["coordinated_by"] == "ZEUS CORE"
    assert b["results"]["PERSEO"]["success"] is True and "ok-PERSEO" in b["results"]["PERSEO"]["content"]
    assert b["teamflow_execution"] is None and b["task"] == "analiza la situación"
    # contrato nuevo: pasos J9b
    assert [s["agent"] for s in b["steps"]] == ["PERSEO", "RAFAEL"] and all(s["status"] == "done" for s in b["steps"])
    assert b["executed"] is False and b["needs_confirmation"] is False
    for n in ("PERSEO", "RAFAEL"):
        ctx = coord[n].seen[0]
        assert ctx["user_id"] == u.id and ctx["company_id"] == c.id and ctx["multi_agent_task"] is True
        assert "EVIL" not in ctx["other_agents"] and "workflow_id" not in ctx
    assert coord["PERSEO"].seen[0]["other_agents"] == ["RAFAEL"]
    # J7: un plan_step por agente, mismo correlation_id que el log de la llamada
    steps = rows(db, c.id, step="ACTUAR", action="plan_step")
    assert len(steps) == 2
    corr = {(r_.details or {}).get("correlation_id") for r_ in rows(db, c.id) if (r_.details or {}).get("correlation_id")}
    assert len({(r_.details or {}).get("correlation_id") for r_ in steps}) == 1
    call = db.query(AgentActivity).filter(AgentActivity.action_type == "agents_coordinate",
                                          AgentActivity.user_email == u.email).first()
    assert call is not None and call.status == "completed"
    assert (call.details or {}).get("correlation_id") == (steps[0].details or {}).get("correlation_id")


def test_coordinate_modulo_inactivo_bloquea_paso_y_no_llama_al_agente(db, client, coord, monkeypatch):
    u, c = _user(db)
    real = module_gate.active_modules
    monkeypatch.setattr(module_gate, "active_modules", lambda d, us: {**real(d, us), "agents": False})
    r = post_coord(client, u, ["PERSEO"])
    assert r.status_code == 200
    b = r.json()
    assert b["success"] is False and b["steps"][0]["status"] == "blocked" and "módulo" in b["steps"][0]["summary"]
    assert coord["PERSEO"].seen == []
    assert rows(db, c.id, step="ORQUESTAR", action="route_to_agent", status="blocked_module")


def test_coordinate_thalos_sin_superusuario_bloqueado_y_con_superusuario_ejecuta(db, client, coord):
    u, c = _user(db)
    assert post_coord(client, u, ["PERSEO", "thalos"]).status_code == 403
    assert coord["THALOS"].seen == [] and coord["PERSEO"].seen == []
    su, _ = _user(db, superuser=True)
    r = post_coord(client, su, ["THALOS"])
    assert r.status_code == 200 and r.json()["steps"][0]["status"] == "done"


def test_coordinate_fallo_de_agente_no_filtra_el_error_y_se_registra_failed(db, client, coord):
    u, c = _user(db)
    coord["RAFAEL"]._result = RuntimeError("secreto-interno-xyz")
    r = post_coord(client, u, ["PERSEO", "RAFAEL"])
    assert r.status_code == 200 and "secreto-interno" not in r.text
    b = r.json()
    assert b["success"] is False and b["results"]["PERSEO"]["success"] is True
    assert b["results"]["RAFAEL"]["success"] is False and b["results"]["RAFAEL"]["status"] == "failed"
    db.expire_all()
    call = (db.query(AgentActivity).filter(AgentActivity.action_type == "agents_coordinate",
            AgentActivity.user_email == u.email).order_by(AgentActivity.id.desc()).first())
    assert call.status == "failed"


def test_coordinate_validaciones_duplicados_limite_y_tarea(db, client, coord):
    u, c = _user(db)
    r = post_coord(client, u, ["perseo", "PERSEO"])
    assert r.status_code == 200 and r.json()["agents_involved"] == ["PERSEO"] and len(coord["PERSEO"].seen) == 1
    assert post_coord(client, u, ["PERSEO", "RAFAEL", "JUSTICIA", "AFRODITA", "THALOS"]).status_code in (403, 422)
    su, _ = _user(db, superuser=True)
    assert post_coord(client, su, ["PERSEO", "RAFAEL", "JUSTICIA", "AFRODITA", "THALOS"]).status_code == 422
    assert post_coord(client, u, ["PERSEO"], task="   ").status_code == 422
    assert post_coord(client, u, ["PERSEO"], task="x" * 4001).status_code == 422
    assert post_coord(client, u, ["NOPE"]).status_code == 404


def test_coordinate_cross_tenant_cada_usuario_su_empresa(db, client, coord):
    u1, c1 = _user(db)
    u2, c2 = _user(db)
    for u in (u1, u2):
        post_coord(client, u, ["RAFAEL"], context={"company_id": c1.id, "user_id": u1.id})
    s1, s2 = coord["RAFAEL"].seen
    assert (s1["user_id"], s1["company_id"]) == (u1.id, c1.id)
    assert (s2["user_id"], s2["company_id"]) == (u2.id, c2.id)
    assert rows(db, c2.id, step="ACTUAR", action="plan_step") and not any(
        (r_.user_email == u1.email) for r_ in db.query(AgentActivity).filter(AgentActivity.company_id == c2.id))


def test_zeus_core_ya_no_tiene_via_propia_de_coordinacion():
    assert not hasattr(ZeusCore, "coordinate_multi_agent_task")
