"""J9a: enrutado unico por palabras completas, control por modulos activos, contexto a todos los
agentes y prompt de sistema integro por agente. Sin red ni LLM: el modelo se sustituye por stubs que
cuentan y capturan las llamadas."""

from __future__ import annotations

import json
import os
import uuid

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
from app.models.user import User
from app.schemas.zeus_action import ZeusAction
from services import module_gate
from services.agent_routing import route_message

ZEUS = "/api/v1/chat/ZEUS CORE/chat"
TPV_MSG = "¿cuánto he vendido hoy en el TPV?"
ANALYTICS_MSG = "enséñame las estadísticas"


# ----------------------------------------------------------------------------- enrutado puro
@pytest.mark.parametrize(
    "msg,agent",
    [
        ("lanza una campaña de instagram para el lunes", "PERSEO"),
        ("necesito mejorar el SEO de la web", "PERSEO"),
        ("prepara la factura y el IVA del trimestre", "RAFAEL"),
        ("¿cuándo presento el modelo 303 a Hacienda?", "RAFAEL"),
        ("redacta el contrato y la cláusula de RGPD", "JUSTICIA"),
        ("¿qué dice la ley sobre las cookies?", "JUSTICIA"),
        ("revisa la nómina y los turnos de la plantilla", "AFRODITA"),
        ("quiero pedir vacaciones y fichar", "AFRODITA"),
    ],
)
def test_frases_reales_por_dominio(msg, agent):
    d = route_message(msg)
    assert d.agent == agent and d.reason == "matched", (msg, d)


@pytest.mark.parametrize(
    "msg",
    [
        "organiza el equipo",               # "ip" dentro de "equipo"
        "actualiza el catálogo",            # "log" dentro de "catálogo"
        "habla con Leyre",                  # "ley" dentro de "Leyre"
        "mi hermano es diplomado",          # "ip" dentro de "diplomado"
        "el equipo del catálogo de Leyre es diplomado",
    ],
)
def test_falsos_positivos_de_subcadena_no_enrutan(msg):
    d = route_message(msg, is_superuser=True)
    assert d.agent is None and d.reason == "no_domain", (msg, d)


def test_sin_agente_claro_no_hay_default_perseo():
    for msg in ("hola, ¿qué tal?", "gracias", "", "¿qué hora es?"):
        d = route_message(msg)
        assert d.agent is None
    # empate entre dominios: tampoco se adivina
    assert route_message("factura del contrato").agent is None
    assert route_message("factura del contrato").reason == "ambiguous"


def test_thalos_solo_para_superusuario():
    msg = "revisa los logs y la ip del firewall"
    assert route_message(msg, is_superuser=True).agent == "THALOS"
    d = route_message(msg, is_superuser=False)
    assert d.agent is None and d.reason == "thalos_requires_superuser"


# --------------------------------------------------------------- ZeusCore.process_request (stubs)
class RecAgent:
    def __init__(self, name):
        self.name = name
        self.calls = []

    def set_zeus_core_ref(self, z):
        pass

    def make_decision(self, msg, additional_context=None):
        self.calls.append(msg)
        return {"success": True, "content": f"{self.name}-ok", "agent": self.name}


@pytest.fixture()
def core():
    z = ZeusCore()
    ag = {n: RecAgent(n) for n in ("PERSEO", "RAFAEL", "THALOS", "JUSTICIA", "AFRODITA")}
    for a in ag.values():
        z.register_agent(a)
    direct = []
    z.make_decision = lambda msg, additional_context=None: (
        direct.append(msg) or {"success": True, "content": "zeus-directo", "agent": "ZEUS CORE"}
    )
    return z, ag, direct


@pytest.mark.parametrize(
    "msg,agent",
    [
        ("lanza una campaña de instagram", "PERSEO"),
        ("calcula el IVA y la factura", "RAFAEL"),
        ("revisa el contrato RGPD", "JUSTICIA"),
        ("¿cómo van las nóminas y los turnos?", "AFRODITA"),
    ],
)
def test_process_request_enruta_al_agente_del_dominio(core, msg, agent):
    z, ag, direct = core
    out = z.process_request({"user_message": msg})
    assert out["selected_agent"] == agent and len(ag[agent].calls) == 1
    assert sum(len(a.calls) for a in ag.values()) == 1 and direct == []


def test_process_request_sin_agente_claro_responde_zeus_no_perseo(core):
    z, ag, direct = core
    for msg in ("organiza el equipo", "revisa el catálogo de Leyre", "hola", "¿qué opinas?"):
        out = z.process_request({"user_message": msg})
        assert out["selected_agent"] == "ZEUS CORE (directo)", msg
    assert all(not a.calls for a in ag.values()) and len(direct) == 4


def test_process_request_thalos_no_para_no_superusuario(core):
    z, ag, direct = core
    out = z.process_request({"user_message": "mira los logs y la ip", "_is_superuser": False})
    assert out["selected_agent"] == "ZEUS CORE (directo)" and not ag["THALOS"].calls
    out = z.process_request({"user_message": "mira los logs y la ip", "_is_superuser": True})
    assert out["selected_agent"] == "THALOS" and len(ag["THALOS"].calls) == 1


# --------------------------------------------------------------- prompt integro por agente
def test_cada_agente_recibe_su_prompt_de_sistema_integro(monkeypatch):
    """messages[0] de la llamada al modelo == prompt literal de config/prompts.json (6 agentes)."""
    import agents.base_agent as base
    from agents.afrodita import Afrodita
    from agents.justicia import Justicia
    from agents.perseo import Perseo
    from agents.rafael import Rafael
    from agents.thalos import Thalos

    captured = []

    def fake_chat_completion(messages, temperature=0.3, max_tokens=2000, **kw):
        captured.append(messages)
        return {
            "success": True, "content": "ok", "model": "stub", "cost": 0.0, "elapsed_time": 0.0,
            "usage": {"total_tokens": 1}, "timestamp": "2026-01-01T00:00:00",
        }

    monkeypatch.setattr(base, "chat_completion", fake_chat_completion)
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "prompts.json")
    with open(path, encoding="utf-8") as fh:
        cfg = json.load(fh)["zeus_prime_v1"]
    expected = {"ZEUS CORE": cfg["system"]["prompt"], **{k: cfg["agents"][k]["prompt"] for k in cfg["agents"]}}
    assert set(expected) == {"ZEUS CORE", "PERSEO", "RAFAEL", "THALOS", "JUSTICIA", "AFRODITA"}

    agents = {
        "ZEUS CORE": ZeusCore(), "PERSEO": Perseo(), "RAFAEL": Rafael(),
        "THALOS": Thalos(), "JUSTICIA": Justicia(), "AFRODITA": Afrodita(),
    }
    for name, agent in agents.items():
        captured.clear()
        agent.make_decision("hola", additional_context={"zeus_global_context": {"company_type": "office"}})
        assert len(captured) == 1, name
        sent = captured[0][0]
        assert sent["role"] == "system", name
        assert sent["content"] == expected[name], f"prompt de {name} alterado o truncado"
        assert len(sent["content"]) > 50, name


# --------------------------------------------------------------- HTTP: modulos activos
class StubAgent:
    def __init__(self, name):
        self.name = name
        self.seen = []

    def set_zeus_core_ref(self, z):
        pass

    def process_request(self, ctx):
        self.seen.append(dict(ctx))
        return {"success": True, "content": "ok-" + self.name}


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
    import services.jarvis_model_comprehension as mc
    import services.unified_agent_runtime as rt

    z = ZeusCore()
    ag = {n: StubAgent(n) for n in ("ZEUS CORE", "PERSEO", "RAFAEL", "THALOS", "JUSTICIA", "AFRODITA")}
    for n, a in ag.items():
        if n != "ZEUS CORE":
            z.register_agent(a)
    llm_calls = []  # llamadas al modelo de comprension + llamadas a agentes via run_chat
    clf_calls = []

    class FakeClf:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    clf_calls.append(kw)
                    raise RuntimeError("no debe llamarse")

    monkeypatch.setattr(mc, "get_client", lambda: FakeClf)
    monkeypatch.setattr(rt, "_get_agents", lambda: dict(ag))
    monkeypatch.setattr(chat_endpoint, "ensure_agent_stack", lambda: None)
    monkeypatch.setattr(chat_endpoint, "AGENTS", {"ZEUS CORE": ag["ZEUS CORE"], **{k: v for k, v in ag.items() if k != "ZEUS CORE"}})
    monkeypatch.setattr(chat_endpoint, "zeus", z)
    c = TestClient(app)
    try:
        yield c, ag, clf_calls
    finally:
        app.dependency_overrides.clear()


def _user(db, company_type="office", superuser=False, name=None):
    suf = uuid.uuid4().hex[:8]
    co = Company(company_name=name or f"J9a {suf}", slug=f"j9a-{suf}", company_type=company_type)
    db.add(co)
    db.flush()
    u = User(email=f"j9a_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
             full_name="J9a", is_active=True, is_superuser=superuser)
    db.add(u)
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=co.id, role="owner"))
    db.commit()
    db.refresh(u)
    db.refresh(co)
    return u, co


def _post(c, user, agent_url, msg, **extra):
    app.dependency_overrides[get_current_active_user] = lambda: user
    return c.post(f"/api/v1/chat/{agent_url}/chat", json={"message": msg, "thread_id": "t-" + uuid.uuid4().hex[:6], **extra})


def _chain(db, company_id, action, status):
    db.expire_all()
    rows = db.query(AgentActivity).filter(AgentActivity.company_id == company_id).all()
    return [r for r in rows if (r.details or {}).get("action") == action and r.status == status]


def test_oficina_pide_tpv_bloqueado_sin_llamar_a_ningun_modelo(db, stack):
    c, ag, clf_calls = stack
    u, co = _user(db, "office")
    r = _post(c, u, "ZEUS CORE", TPV_MSG)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["success"] is False and out["executed_action"] is False
    assert "Tu empresa no tiene activo el módulo TPV" in out["message"]
    assert clf_calls == [] and all(not a.seen for a in ag.values())  # ni clasificador ni agente/LLM
    rows = _chain(db, co.id, "tpv_sales_summary", "blocked_module")
    assert rows and rows[0].details["chain_step"] == "ORQUESTAR" and rows[0].details["module"] == "tpv"


def test_hosteleria_pide_analitica_bloqueado_y_su_tpv_si_funciona(db, stack):
    c, ag, clf_calls = stack
    u, co = _user(db, "bar_restaurant")
    out = _post(c, u, "ZEUS CORE", ANALYTICS_MSG).json()
    assert out["success"] is False and "módulo Analítica" in out["message"]
    assert _chain(db, co.id, "analytics_summary", "blocked_module")
    ok = _post(c, u, "ZEUS CORE", TPV_MSG).json()
    assert ok["success"] is True and ok["executed_action"] is True
    assert not _chain(db, co.id, "tpv_sales_summary", "blocked_module")
    assert clf_calls == [] and all(not a.seen for a in ag.values())


def test_oficina_si_tiene_analitica(db, stack):
    c, _, _ = stack
    u, co = _user(db, "office")
    out = _post(c, u, "ZEUS CORE", ANALYTICS_MSG).json()
    assert out["success"] is True and not _chain(db, co.id, "analytics_summary", "blocked_module")


def test_superusuario_no_queda_bloqueado_por_modulo(db, stack):
    c, _, _ = stack
    u, _ = _user(db, "office", superuser=True)
    assert module_gate.check_action(db, u, "tpv_sales_summary") is None
    assert module_gate.check_agent(db, u, "THALOS") is None


def test_execute_action_bloquea_tambien_la_via_de_aprobaciones(db, stack):
    """Defensa en profundidad: execute_action (aprobaciones, ejecutor de agentes) no ejecuta sin modulo."""
    import asyncio
    from services.zeus_orchestrator_service import execute_action

    u, co = _user(db, "office")
    action = ZeusAction(action_type="tpv_sales_summary", company_id=co.id, user_id=u.id, payload={"days": 1})
    res = asyncio.run(execute_action(db, u, action))
    assert res.success is False and res.executed is False and "módulo TPV" in res.message
    assert res.company_id == co.id
    assert _chain(db, co.id, "tpv_sales_summary", "blocked_module")


def test_acciones_sin_mapeo_claro_siguen_permitidas(db):
    u, _ = _user(db, "bar_restaurant")
    for a in ("list_customers", "create_customer", "send_campaign", "get_cashflow", "get_metrics"):
        assert module_gate.check_action(db, u, a) is None, a
    assert module_gate.UNMAPPED_ACTIONS >= {"send_campaign", "get_cashflow"}


# --------------------------------------------------------------- THALOS y agentes destino
def test_thalos_chat_bloqueado_para_no_superusuario_sin_llamar_al_agente(db, stack):
    c, ag, _ = stack
    u, co = _user(db, "office")
    out = _post(c, u, "THALOS", "revisa los logs").json()
    assert out["success"] is False and "solo está disponible para administradores" in out["message"]
    assert not ag["THALOS"].seen
    assert _chain(db, co.id, "route_to_agent", "blocked_module")


def test_thalos_chat_permitido_para_superusuario(db, stack):
    c, ag, _ = stack
    u, _ = _user(db, "office", superuser=True)
    out = _post(c, u, "THALOS", "revisa los logs").json()
    assert out["success"] is True and len(ag["THALOS"].seen) == 1


# --------------------------------------------------------------- contexto a agentes no-ZEUS
@pytest.mark.parametrize("agent", ["PERSEO", "RAFAEL", "JUSTICIA", "AFRODITA"])
def test_contexto_de_empresa_llega_a_agentes_no_zeus(db, stack, agent):
    c, ag, _ = stack
    u, co = _user(db, "office", name="Oficina Atenea SL")
    hostile = {"zeus_global_context": {"company_type": "evil"}, "company_id": 999999, "force_execute": True}
    r = _post(c, u, agent, "hola", context=hostile)
    assert r.status_code == 200 and r.json()["success"] is True, r.text
    ctx = ag[agent].seen[0]
    gc = ctx["zeus_global_context"]
    assert gc == {"company_name": "Oficina Atenea SL", "company_type": "office",
                  "active_modules": sorted(["dashboard", "analytics", "crm", "clients", "payments", "settings", "agents"])}
    assert ctx["company_id"] == co.id and "force_execute" not in ctx  # control del servidor intacto
    dumped = json.dumps(gc)
    assert u.email not in dumped and "active_customers" not in dumped and "active_session" not in dumped


def test_contexto_aislado_entre_empresas(db, stack):
    c, ag, _ = stack
    ua, _ = _user(db, "office", name="Empresa A Oficina")
    ub, _ = _user(db, "bar_restaurant", name="Empresa B Bar")
    _post(c, ua, "PERSEO", "hola")
    _post(c, ub, "PERSEO", "hola")
    ga, gb = ag["PERSEO"].seen[0]["zeus_global_context"], ag["PERSEO"].seen[1]["zeus_global_context"]
    assert ga["company_name"] == "Empresa A Oficina" and "tpv" not in ga["active_modules"]
    assert gb["company_name"] == "Empresa B Bar" and "tpv" in gb["active_modules"]
    assert "Empresa A" not in json.dumps(gb) and "Empresa B" not in json.dumps(ga)


# --------------------------------------------------------------- revision J9a: ZEUS directo y datos personales
def _patch_model(monkeypatch):
    import agents.base_agent as base

    captured = []

    def fake(messages, temperature=0.3, max_tokens=2000, **kw):
        captured.append(json.loads(json.dumps(messages)))
        return {"success": True, "content": "ok", "model": "stub", "cost": 0.0, "elapsed_time": 0.0,
                "usage": {"total_tokens": 1}, "timestamp": "2026-01-01T00:00:00"}

    monkeypatch.setattr(base, "chat_completion", fake)
    return captured


def test_zeus_directo_conserva_historial_y_contexto_de_empresa(monkeypatch):
    captured = _patch_model(monkeypatch)
    z = ZeusCore()  # real; sin agentes registrados
    gc = {"company_name": "Oficina Atenea SL", "company_type": "office", "active_modules": ["agents", "crm"]}
    out = z.process_request({
        "user_message": "hola, ¿me recuerdas?",
        "conversation_history": [{"role": "user", "content": "soy Pepe"},
                                 {"role": "assistant", "content": "Encantado, Pepe"}],
        "zeus_global_context": gc,
    })
    assert out["selected_agent"] == "ZEUS CORE (directo)"
    assert len(captured) == 1
    msgs = captured[0]
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "user"]
    assert msgs[1]["content"] == "soy Pepe"
    last = msgs[-1]["content"]
    assert "Oficina Atenea SL" in last and "office" in last and "active_modules" in last


def test_thalos_sin_superusuario_responde_zeus_con_contexto(monkeypatch):
    captured = _patch_model(monkeypatch)
    z = ZeusCore()
    out = z.process_request({"user_message": "revisa los logs y la ip", "_is_superuser": False,
                             "conversation_history": [{"role": "user", "content": "soy Pepe"}],
                             "zeus_global_context": {"company_name": "Acme"}})
    assert out["selected_agent"] == "ZEUS CORE (directo)"
    assert "soy Pepe" in json.dumps(captured[0]) and "Acme" in json.dumps(captured[0])


def test_datos_personales_no_llegan_al_modelo_en_ningun_agente(monkeypatch):
    from agents.afrodita import Afrodita
    from agents.justicia import Justicia
    from agents.perseo import Perseo
    from agents.rafael import Rafael
    from agents.thalos import Thalos

    captured = _patch_model(monkeypatch)
    email, uid = "pepe.secreto@example.test", 987654321
    ctx = {"user_email": email, "user_id": uid, "company_id": 7,
           "zeus_global_context": {"company_name": "Acme", "company_type": "office", "active_modules": ["agents"]}}
    agents = [ZeusCore(), Perseo(), Rafael(), Thalos(), Justicia(), Afrodita()]
    for a in agents:
        captured.clear()
        a.make_decision("hola", additional_context=dict(ctx))
        blob = json.dumps(captured[0], ensure_ascii=False)
        assert email not in blob and str(uid) not in blob, a.name
        assert "Acme" in blob, a.name  # el contexto de empresa si llega
    # el contexto original no se muta: el codigo de los agentes (firewall) sigue viendo user_id
    assert ctx["user_id"] == uid and ctx["user_email"] == email


# --------------------------------------------------------------- company_type nulo
def test_company_type_nulo_se_infiere_por_sector_y_bloquea_segun_resultado(db, stack):
    """Documenta (sin cambiar) la inferencia de company_module_config.infer_company_type: con
    company_type NULL se usa metadata.business_type, luego el sector ('servicio/oficina/profesional'
    => office) y, si nada casa, bar_restaurant. Consecuencia: analitica solo activa si se infiere oficina."""
    c, _, _ = stack
    suf = uuid.uuid4().hex[:8]
    users = {}
    for label, sector in (("oficina", "Servicios profesionales"), ("sin_sector", None)):
        co = Company(company_name=f"J9a nulo {label} {suf}", slug=f"j9a-n-{label}-{suf}", company_type=None, sector=sector)
        db.add(co)
        db.flush()
        u = User(email=f"j9a_n_{label}_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
                 full_name="J9a", is_active=True)
        db.add(u)
        db.flush()
        db.add(UserCompany(user_id=u.id, company_id=co.id, role="owner"))
        db.commit()
        db.refresh(u)
        users[label] = u
    assert module_gate.check_action(db, users["oficina"], "analytics_summary") is None
    blocked = module_gate.check_action(db, users["sin_sector"], "analytics_summary")
    assert blocked and "módulo Analítica" in blocked["message"]  # sin pistas => bar_restaurant (defecto)
    assert module_gate.check_action(db, users["sin_sector"], "tpv_sales_summary") is None
