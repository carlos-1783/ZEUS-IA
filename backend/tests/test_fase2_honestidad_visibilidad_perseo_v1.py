"""Fase 2 / honestidad final #25 — el estado de PERSEO ya no se copia del flag de AFRODITA."""

from __future__ import annotations

from config import afrodita_flags_v1
from config.settings import settings as agent_settings
from services import system_visibility_v1 as vis


def _perseo(payload):
    return next(a for a in payload["agents"] if a["name"] == "PERSEO")


def _thalos_justicia(payload):
    by = {a["name"]: a for a in payload["agents"]}
    return by["THALOS"], by["JUSTICIA"]


def test_perseo_depende_de_openai_no_de_afrodita(monkeypatch):
    monkeypatch.setattr(agent_settings, "OPENAI_API_KEY", "")
    p = _perseo(vis.execution_status_payload())
    assert p["status"] == "DISCONNECTED" and p["execution_ready"] is False
    assert p["execution_mode"] == "SIMULATED"

    monkeypatch.setattr(agent_settings, "OPENAI_API_KEY", "sk-solo-test")
    payload = vis.execution_status_payload()
    p = _perseo(payload)
    assert p["status"] == "PARTIAL" and p["execution_mode"] == "REAL"
    assert payload["flags"]["PERSEO_LLM_CONFIGURED"] is True
    assert "sk-solo-test" not in str(payload)


def test_flag_afrodita_no_afecta_a_perseo(monkeypatch):
    monkeypatch.setattr(agent_settings, "OPENAI_API_KEY", "")
    real_flags = afrodita_flags_v1.get_afrodita_safety_flags()
    monkeypatch.setattr(
        vis, "get_afrodita_safety_flags",
        lambda: {**real_flags, "AFRODITA_EXECUTION_ENABLED": True, "AFRODITA_READ_ONLY_MODE": False},
    )
    assert _perseo(vis.execution_status_payload())["status"] == "DISCONNECTED"


def test_notas_actualizadas():
    thalos, justicia = _thalos_justicia(vis.execution_status_payload())
    assert "SIMULADO" not in thalos["notes"] and "stub" not in justicia["notes"]
    assert "eIDAS" in justicia["notes"]
