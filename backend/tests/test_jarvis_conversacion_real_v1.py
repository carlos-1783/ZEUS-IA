"""Cierre JARVIS / Tarea 1 — la conversacion llega de verdad al modelo.

Extremo a extremo por HTTP con el runtime REAL (run_chat → agente → base_agent.make_decision →
openai_service.chat_completion). Solo se sustituye el cliente de OpenAI (sin red): se captura lo que
se le envia y se comprueba que (1) el system prompt es el de config/prompts.json, (2) lo que devuelve
el modelo es lo que ve el cliente y (3) ZEUS conversa por defecto: la charla y las peticiones de algo
que no existe no acaban en plan/aclaracion robotica. Incluye el diagnostico del modelo (sin exponer
la clave)."""

from __future__ import annotations

import json
import os
import uuid
from types import SimpleNamespace

import pytest

from app.core.auth import get_current_active_user
from app.main import app
from services import jarvis_plan as plan_mod
from services import openai_service
from services.jarvis_conversation_gate import has_clear_action_intent

from test_jarvis_acciones_ops_v1 import _REAL_RUN_CHAT, _env, _user, client, db  # noqa: F401

MODEL_REPLY = "¡Hola! Todo en orden por aquí. Cuéntame qué tienes en mente."
FAKE_KEY = "sk-test-NO-REAL-0123456789abcdef"


class _FakeCompletions:
    def __init__(self, reply: str):
        self.reply = reply
        self.calls = []

    def create(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.reply), finish_reason="stop")],
            usage=SimpleNamespace(prompt_tokens=12, completion_tokens=8, total_tokens=20),
        )


class _FakeModels:
    def __init__(self, known):
        self.known = set(known)

    def retrieve(self, model):
        if model not in self.known:
            err = Exception(f"The model `{model}` does not exist or you do not have access to it.")
            err.status_code = 404
            raise err
        return SimpleNamespace(id=model)


@pytest.fixture()
def llm(monkeypatch):
    import services.unified_agent_runtime as rt

    monkeypatch.setattr(rt, "run_chat", _REAL_RUN_CHAT)  # runtime real (el fixture _env lo stubea)
    comp = _FakeCompletions(MODEL_REPLY)
    fake = SimpleNamespace(chat=SimpleNamespace(completions=comp), models=_FakeModels({"gpt-4o-mini"}))
    monkeypatch.setattr(openai_service, "get_openai_client", lambda: fake)
    return comp


def _prompts():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "prompts.json")
    with open(path, encoding="utf-8") as fh:
        cfg = json.load(fh)["zeus_prime_v1"]
    return {"ZEUS CORE": cfg["system"]["prompt"], **{k: v["prompt"] for k, v in cfg["agents"].items()}}


def _post(client, user, path, message):
    app.dependency_overrides[get_current_active_user] = lambda: user
    r = client.post(path, json={"message": message, "thread_id": f"t-{uuid.uuid4().hex[:8]}"})
    assert r.status_code == 200, r.text
    return r.json()


def _talked(out, comp, prompts, agent=None, extra_suffix=""):
    """El cliente ve EXACTAMENTE lo que devolvio el modelo, el modelo recibio un system prompt integro
    de config/prompts.json y no hubo plan, accion ni aclaracion. `extra_suffix`: anadido conocido de
    la normalizacion propia del agente (p. ej. la CTA de PERSEO), nunca texto inventado por el test."""
    assert out["success"] is True, out
    assert out["message"] == MODEL_REPLY + extra_suffix
    assert not out.get("executed_action") and not out.get("steps") and not out.get("needs_clarification")
    assert comp.calls, "no se llamo al modelo"
    system = comp.calls[-1]["messages"][0]
    assert system["role"] == "system"
    if agent:
        assert system["content"] == prompts[agent]
    else:
        assert system["content"] in prompts.values()


# ----------------------------------------------------------------------------- puerta de intencion
@pytest.mark.parametrize("msg", [
    "hola zeus, ¿qué tal?",
    "¿cómo va el marketing y las facturas este mes?",
    "qué opinas de la campaña de verano",
    "ayer envié una campaña y fue bien",
    "reserva un vuelo a París",
    "mis clientes están contentos, ¿no crees?",
])
def test_charla_no_es_intencion_de_accion(msg):
    assert has_clear_action_intent(msg) is False


@pytest.mark.parametrize("msg", [
    "envía una oferta del 10% a los clientes VIP",
    "Zeus, crea un cliente Juan Pérez",
    "dame las facturas pendientes y las ventas de hoy",
    "quiero enviar una campaña",
    "¿puedes ver cómo van las ventas?",
    "oye, prepara un borrador de post y luego revisa la seguridad",
])
def test_orden_clara_es_intencion_de_accion(msg):
    assert has_clear_action_intent(msg) is True


# ----------------------------------------------------------------------------- ZEUS conversa
def test_zeus_charla_llega_al_modelo_con_su_prompt_y_el_cliente_ve_la_respuesta(db, client, llm):
    u, _ = _user(db)
    out = _post(client, u, "/api/v1/jarvis/message", "hola zeus, ¿qué tal estás hoy?")
    _talked(out, llm, _prompts(), agent="ZEUS CORE")
    # El runtime anade «Contexto adicional: {...}» detras del mensaje del usuario: el mensaje va al principio.
    assert llm.calls[-1]["messages"][-1]["content"].startswith("hola zeus, ¿qué tal estás hoy?")


def test_zeus_charla_con_dos_dominios_ya_no_dispara_el_plan(db, client, llm):
    msg = "hola zeus, ¿cómo va el marketing y las facturas este mes?"
    # Antes esto era un plan multiagente por reglas («análisis» paso a paso), no una conversacion.
    assert plan_mod.plan_from_rules(msg) is not None
    u, _ = _user(db)
    _talked(_post(client, u, "/api/v1/jarvis/message", msg), llm, _prompts())


def test_zeus_accion_inexistente_responde_hablando(db, client, llm):
    u, _ = _user(db)
    out = _post(client, u, "/api/v1/jarvis/message", "reserva un vuelo a París para el lunes")
    _talked(out, llm, _prompts())


def test_zeus_opinion_sobre_clientes_no_recibe_la_pregunta_robotica(db, client, llm):
    u, _ = _user(db)
    out = _post(client, u, "/api/v1/jarvis/message", "mis clientes están contentos, ¿no crees?")
    _talked(out, llm, _prompts())
    assert "No he podido entender" not in out["message"]


def test_zeus_orden_clara_sigue_por_el_camino_de_accion(db, client, llm):
    """La puerta no apaga las acciones: una consulta real reconocida no llega al modelo."""
    u, _ = _user(db)
    out = _post(client, u, "/api/v1/jarvis/message", "¿cómo fue el cierre de ayer?")
    assert out["executed_action"] and out["execution"]["intent"] == "get_daily_close"
    assert not llm.calls


def test_zeus_negacion_sigue_sin_hacer_nada(db, client, llm):
    u, _ = _user(db)
    out = _post(client, u, "/api/v1/jarvis/message", "no envíes la campaña a los clientes")
    # Respuesta J8 del parser (QUESTION_NEGATED): «…así que no he hecho nada».
    assert out["executed_action"] is False and "no he hecho nada" in out["message"].lower()
    assert not llm.calls


# ----------------------------------------------------------------------------- ordenes de parada sin «no»
_STOP_SIN_NO = [
    "detén el envío de la oferta a todos mis clientes",
    "para el envío de la campaña a mis clientes",
    "frena el envío de la oferta",
    "suspende la campaña de verano",
    "aborta el envío de la promoción",
    "aplaza el envío de la oferta a los clientes",
    "pospón la campaña de la oferta",
    "deja estar la oferta a mis clientes",
    "cancela la campaña de la oferta",
    "detén el envío",
    "para el envío ya",
    "pospón eso, mejor mañana",
    "para",
    "para ya",
    "¡Para!",
    "stop",
    "déjalo estar",
    "cancélalo",
    "para el envío de la campaña a mis clientes",
    "para el envío de la oferta del 10% a todos mis clientes",
    "para la campaña de verano",
]

# Sustantivos, pasados, relatos y acciones con objeto propio: NO son paradas.
_NO_ES_PARADA = [
    "¿cuántas cancelaciones tuve este mes?",
    "el cliente anuló su reserva, ¿qué hago?",
    "suspendí el examen",
    "el evento se aplazó por la lluvia",
    "anula la factura 23",
    # «para» PREPOSICION + objeto (2ª revision): no es la orden «parar».
    "para la campaña de verano, prepara un post con fotos",
    "para el post de mañana, ¿qué foto uso?",
    "para la oferta del 10%, ¿qué texto pongo?",
    "para el plan de marketing necesito ideas",
    "para la campaña de verano envía un correo",
    # 3ª revision: «para» preposicion seguido de cualquier verbo/palabra fuera de la lista blanca.
    "para la oferta de verano usaremos un 15%",
    "para el mensaje de cumpleaños me gusta algo corto",
    "para la campaña de navidad tengo 500 euros",
    "para el envío de mañana usa la plantilla de verano",
    "para el correo de bienvenida pon un tono cercano",
    "cancela el plan premium",
    "espera, ¿cuánto vendí hoy?",
    "envía la oferta para todos mis clientes",
]


@pytest.mark.parametrize("msg", _NO_ES_PARADA)
def test_sustantivos_pasados_y_acciones_con_objeto_no_son_parada(msg):
    from services.jarvis_conversation_gate import is_stop_order

    assert is_stop_order(msg) is False


@pytest.mark.parametrize("msg", _NO_ES_PARADA[:15])
def test_zeus_no_parada_no_recibe_entendido_no_hago_nada(db, client, llm, monkeypatch, msg):
    """Antes del gate (HEAD) estos mensajes iban a la charla o a la aclaracion; no deben contestarse
    «Entendido, no hago nada» como si fueran una orden de parada atendida. Y nada se ejecuta."""
    from app.models.zeus_pending_approval import ZeusPendingApproval
    from services import jarvis_model_comprehension as mc

    monkeypatch.setattr(mc, "get_client", lambda: None)
    u, _ = _user(db)
    out = _post(client, u, "/api/v1/jarvis/message", msg)
    assert "entendido, no hago nada" not in out["message"].lower(), out["message"]
    assert not out.get("executed_action") and not out.get("needs_confirmation")
    db.expire_all()
    assert db.query(ZeusPendingApproval).filter(ZeusPendingApproval.user_id == u.id).count() == 0


@pytest.mark.parametrize("msg", _STOP_SIN_NO)
def test_orden_de_parada_sin_no_no_es_charla(msg):
    from services.jarvis_conversation_gate import is_stop_order, wants_action_path

    assert is_stop_order(msg) is True and wants_action_path(msg) is True


@pytest.mark.parametrize("msg", _STOP_SIN_NO)
def test_zeus_orden_de_parada_sin_no_no_llega_al_modelo_y_no_hace_nada(db, client, llm, monkeypatch, msg):
    """Sin clasificador (sin clave): la orden de parada no va al modelo conversacional ni crea plan,
    aprobacion ni accion; se contesta que no se hace nada, igual que «no envíes…»."""
    from app.models.zeus_pending_approval import ZeusPendingApproval
    from services import jarvis_model_comprehension as mc

    monkeypatch.setattr(mc, "get_client", lambda: None)  # camino de reglas, sin clasificador ni red
    u, _ = _user(db)
    out = _post(client, u, "/api/v1/jarvis/message", msg)
    assert not llm.calls, "una orden de parada no debe llegar al modelo"
    assert out["executed_action"] is False and not out.get("needs_confirmation") and not out.get("steps")
    assert "no hago nada" in out["message"].lower(), out["message"]
    db.expire_all()
    assert db.query(ZeusPendingApproval).filter(ZeusPendingApproval.user_id == u.id).count() == 0


@pytest.mark.parametrize("msg", [
    "detén el envío de la oferta del 10% a todos mis clientes",
    "para el envío de la oferta del 10% a todos mis clientes",
])
def test_parada_con_clasificador_erroneo_affirm_alto_no_ejecuta_nada(db, client, llm, monkeypatch, msg):
    """Clasificador simulado que se equivoca y dice «affirm» con certeza 0.99: lo peor que puede pasar
    es la vista previa J8c con aviso «He entendido que SÍ…» y una aprobacion J3 PENDIENTE. Cero
    ejecuciones, cero envios, y el modelo conversacional no interviene."""
    from app.models.zeus_pending_approval import ZeusPendingApproval
    from services import jarvis_model_comprehension as mc
    from test_jarvis_modelo_v1 import OFFER_ACT, FakeClient, payload

    data = payload(OFFER_ACT, overall=0.99)
    data["actions"][0]["certainty"] = 0.99
    fake = FakeClient(data)
    monkeypatch.setattr(mc, "get_client", lambda: fake)
    u, _ = _user(db)
    out = _post(client, u, "/api/v1/jarvis/message", msg)
    assert fake.calls, "la orden de parada debe pasar por la comprension J8b/J8c"
    assert not llm.calls
    assert out["executed_action"] is False
    if out.get("needs_confirmation"):
        assert out["message"].startswith("He entendido que SÍ"), out["message"]
    db.expire_all()
    rows = db.query(ZeusPendingApproval).filter(ZeusPendingApproval.user_id == u.id).all()
    assert len(rows) <= 1 and all(r.status == "pending" and r.executed_at is None for r in rows)


# ----------------------------------------------------------------------------- PERSEO conversa
def test_perseo_charla_llega_al_modelo_con_su_prompt_y_el_cliente_ve_la_respuesta(db, client, llm):
    u, _ = _user(db)
    out = _post(client, u, "/api/v1/chat/perseo/chat", "hola perseo, ¿qué te parece mi estrategia en redes?")
    # La charla de PERSEO llega tal cual la dijo el modelo: el codigo no le anade ningun CTA.
    _talked(out, llm, _prompts(), agent="PERSEO")
    assert "CTA" not in out["message"] and "Reserva ahora" not in out["message"]


def test_perseo_charla_regresion_sin_cta_en_el_chat_pero_el_entregable_conserva_su_cta(db, client, llm):
    """Regresion: el chat de PERSEO nunca lleva «CTA:» anadido por codigo. El CTA vive en el
    entregable de campana guardado en el workspace (content["cta"]), no en el mensaje."""
    from app.models.document_approval import DocumentApproval
    from services.workspace_deliverables import (
        normalize_perseo_chat_message,
        normalize_perseo_workspace_payload,
    )

    assert normalize_perseo_chat_message(MODEL_REPLY) == MODEL_REPLY
    assert "CTA:" not in normalize_perseo_chat_message("Hola.\n\nTu estrategia en redes va bien.")

    u, _ = _user(db)
    out = _post(client, u, "/api/v1/chat/perseo/chat", "hola perseo, ¿qué te parece mi estrategia en redes?")
    assert out["success"] is True and "CTA:" not in out["message"]
    assert out["message"] == MODEL_REPLY

    db.expire_all()
    doc = (
        db.query(DocumentApproval)
        .filter(DocumentApproval.user_id == u.id, DocumentApproval.agent_name == "PERSEO")
        .order_by(DocumentApproval.id.desc())
        .first()
    )
    assert doc is not None, "el chat de PERSEO debe seguir guardando su entregable en el workspace"
    content = (doc.document_payload or {}).get("content") or {}
    assert content.get("cta") == "Reserva ahora"  # el entregable conserva su CTA como campo
    assert "CTA:" not in str(content.get("copy") or "")  # y el copy no arrastra el sufijo del chat
    shown = normalize_perseo_workspace_payload(doc.document_payload)
    assert shown["content"]["cta"] == "Reserva ahora"


# ----------------------------------------------------------------------------- diagnostico
def _diag(monkeypatch, key, model="gpt-4o-mini", live=False):
    from config.settings import settings
    from services import llm_diagnostics as d

    monkeypatch.setattr(settings, "OPENAI_API_KEY", key)
    monkeypatch.setattr(settings, "OPENAI_MODEL", model)
    monkeypatch.setenv("OPENAI_API_KEY", key)
    monkeypatch.delenv("JARVIS_CLASSIFIER_MODEL", raising=False)
    return d.run_llm_diagnostics(live=live)


def test_diagnostico_sin_clave_lo_dice_y_no_llama(monkeypatch, llm):
    rep = _diag(monkeypatch, "")
    assert rep["ok"] is False and rep["key"]["present"] is False
    assert rep["model_check"] is None and rep["live_call"] is None and not llm.calls


def test_diagnostico_con_clave_valida_y_llamada_real_no_expone_la_clave(monkeypatch, llm):
    rep = _diag(monkeypatch, FAKE_KEY, live=True)
    assert rep["ok"] is True, rep["problems"]
    assert rep["key"]["present"] and rep["key"]["starts_with_sk"] and rep["env_matches_settings"]
    assert rep["model_check"]["ok"] and rep["live_call"]["ok"] and rep["live_call"]["reply"]
    assert llm.calls[-1]["model"] == "gpt-4o-mini"  # mismo wrapper que los agentes
    assert "0123456789abcdef" not in json.dumps(rep)


def test_diagnostico_modelo_inaccesible_y_clave_mal_pegada(monkeypatch, llm):
    rep = _diag(monkeypatch, f" {FAKE_KEY}\n", model="gpt-9-inexistente")
    assert rep["ok"] is False
    assert rep["key"]["has_surrounding_whitespace"] is True
    assert rep["model_check"]["ok"] is False and rep["model_check"]["status_code"] == 404
    assert any("espacios" in p for p in rep["problems"]) and any("gpt-9-inexistente" in p for p in rep["problems"])


def test_diagnostico_solo_superusuario(db, client, llm, monkeypatch):
    from config.settings import settings

    monkeypatch.setattr(settings, "OPENAI_API_KEY", FAKE_KEY)
    monkeypatch.setattr(settings, "OPENAI_MODEL", "gpt-4o-mini")
    u, _ = _user(db)
    app.dependency_overrides[get_current_active_user] = lambda: u
    assert client.get("/api/v1/chat/diagnostics/llm").status_code == 403
    su, _ = _user(db, superuser=True)
    app.dependency_overrides[get_current_active_user] = lambda: su
    r = client.get("/api/v1/chat/diagnostics/llm")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["model_check"]["ok"] is True and body["live_call"] is None
    assert FAKE_KEY not in r.text
