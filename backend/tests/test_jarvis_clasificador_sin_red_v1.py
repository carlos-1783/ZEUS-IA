"""J8b: el clasificador de JARVIS no toca la red en tests aunque haya OPENAI_API_KEY, y el cliente se
inyecta por un punto unico (`set_client_provider`). Toda la red queda bloqueada en estos tests
(socket.connect, getaddrinfo y httpx.Client.send fallan y se cuentan)."""

from __future__ import annotations

import asyncio
import json
import socket
from types import SimpleNamespace

import httpx
import pytest

from app.db.base import SessionLocal
from app.schemas.zeus_task import ZeusTaskObject
from services import jarvis_model_comprehension as mc

OFFER = "envía la oferta del 10% a todos mis clientes"
COMPANY_ID = 987654  # sin actividad registrada: el tope de gasto no bloquea
FAKE_KEY = "sk-test-clasificador-sin-red-0000000000"


def _payload():
    ent = {"names": [], "emails": [], "phones": [], "percentages": [10], "recipients": "all_customers"}
    return {"actions": [{"action_type": "send_campaign", "polarity": "affirm", "certainty": 0.95, "entities": ent}],
            "overall_certainty": 0.95, "needs_clarification": False, "clarification_question": None, "notes": ""}


class FakeClient:
    """chat.completions.create en memoria. Nunca abre red."""

    def __init__(self):
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(_payload())))],
            usage=SimpleNamespace(prompt_tokens=900, completion_tokens=80),
        )


@pytest.fixture()
def red_bloqueada(monkeypatch):
    """Cualquier intento de red EXTERNA falla y queda registrado. Se permite solo el loopback del
    socketpair interno del bucle asyncio en Windows (ProactorEventLoop), que no sale de la maquina."""
    intentos = []

    def _bloq(nombre, original=None):
        def _f(*a, **k):
            if original is not None and len(a) >= 2 and isinstance(a[1], tuple) and a[1][0] in ("127.0.0.1", "::1"):
                return original(*a, **k)
            intentos.append(nombre)
            raise OSError(f"red bloqueada en tests ({nombre})")
        return _f

    monkeypatch.setattr(socket.socket, "connect", _bloq("socket.connect", socket.socket.connect))
    monkeypatch.setattr(socket.socket, "connect_ex", _bloq("socket.connect_ex", socket.socket.connect_ex))
    monkeypatch.setattr(socket, "getaddrinfo", _bloq("getaddrinfo"))
    monkeypatch.setattr(httpx.Client, "send", _bloq("httpx.Client.send"))
    return intentos


@pytest.fixture()
def con_clave(monkeypatch):
    from config.settings import settings

    monkeypatch.setattr(settings, "OPENAI_API_KEY", FAKE_KEY)
    monkeypatch.setenv("OPENAI_API_KEY", FAKE_KEY)
    for k in ("JARVIS_MODEL_COMPREHENSION", "JARVIS_CLASSIFIER_MODEL", "JARVIS_CLASSIFIER_TIMEOUT_SEC",
              "JARVIS_CLASSIFIER_COMPANY_DAILY_BUDGET_USD", "JARVIS_CLASSIFIER_GLOBAL_DAILY_BUDGET_USD",
              "JARVIS_CLASSIFIER_JSON_MODE"):
        monkeypatch.delenv(k, raising=False)
    return FAKE_KEY


def _comprehend(steps):
    db = SessionLocal()
    try:
        strict = ZeusTaskObject(intent="unknown", raw_message=OFFER)
        comp = asyncio.run(mc.comprehend(db, None, COMPANY_ID, OFFER, strict,
                                         lambda *a, **k: steps.append((a, k)) or True))
        return comp, strict
    finally:
        db.close()


def test_con_clave_y_sin_inyeccion_explicita_no_toca_la_red(con_clave, red_bloqueada):
    """Por defecto en tests (conftest): 'sin modelo' -> criterio estricto, cero intentos de red."""
    assert mc.passes_gate(OFFER)
    steps = []
    comp, strict = _comprehend(steps)
    assert comp.task is strict and comp.used_model is False and comp.result == "skipped"
    assert steps == []           # ni siquiera llega a registrar una llamada al modelo
    assert red_bloqueada == []
    assert mc.build_real_client.intentos == []


def test_guardia_impide_construir_el_cliente_real_y_cae_a_reglas(con_clave, red_bloqueada):
    """Si un test restaura el camino de produccion sin inyectar cliente, la guardia del conftest
    impide construir el OpenAI real; comprehend cae a reglas y no hay red. (Se limpia el registro
    para que el teardown de la guardia no haga fallar ESTE test, que lo provoca a proposito.)"""
    mc.set_client_provider(None)
    steps = []
    comp, strict = _comprehend(steps)
    assert comp.task is strict and comp.used_model is False
    assert mc.build_real_client.intentos == [1]
    assert red_bloqueada == []
    mc.build_real_client.intentos.clear()


def test_cliente_inyectado_recibe_la_llamada_con_los_parametros_de_produccion(con_clave, red_bloqueada):
    fake = FakeClient()
    mc.set_client_provider(lambda: fake)
    steps = []
    comp, _ = _comprehend(steps)
    cfg = mc.load_config()

    assert len(fake.calls) == 1
    kw = fake.calls[0]
    assert kw["model"] == cfg.model and kw["temperature"] == 0 and kw["max_tokens"] == cfg.max_tokens
    assert kw["timeout"] == cfg.timeout and kw["response_format"] == {"type": "json_object"}
    assert comp.used_model is True and comp.result == "ok"
    # Nunca ejecuta: solo produce la tarea (la aprobacion humana sigue en el orquestador).
    assert comp.task.intent == "create_campaign_send" and comp.task.discount_percent == 10.0
    assert comp.task.requires_confirmation is True and comp.decision == "affirm_prepare"
    assert [s[0][0] for s in steps] == ["COMPRENDER"]
    assert red_bloqueada == []
    assert mc.build_real_client.intentos == []


def test_set_client_provider_none_restaura_el_camino_real(monkeypatch, con_clave, red_bloqueada):
    """Camino de produccion (sin inyeccion): get_client construye el OpenAI REAL con la clave y sin
    reintentos. Solo se construye (no se llama): la red sigue bloqueada y sin intentos."""
    from openai import OpenAI

    monkeypatch.setattr(mc, "build_real_client", mc.build_real_client.real)
    mc.set_client_provider(None)
    c = mc.get_client()
    assert isinstance(c, OpenAI)
    assert c.api_key == FAKE_KEY and c.max_retries == 0
    assert red_bloqueada == []


def test_camino_real_sin_clave_devuelve_none(monkeypatch, red_bloqueada):
    from config.settings import settings

    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(mc, "build_real_client", mc.build_real_client.real)
    mc.set_client_provider(None)
    assert mc.get_client() is None
    assert red_bloqueada == []
