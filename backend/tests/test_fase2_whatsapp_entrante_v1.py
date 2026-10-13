"""Fase 2 / auditoria final #16 WhatsApp: flag desactivado por defecto, sin auto-respuesta sin empresa, PII minimizada.

Dobles SOLO en test (cliente Twilio y envio de email); endpoints, THALOS y BD reales
(desechable). Ver envios_consentimiento_comun.py."""

from __future__ import annotations

from envios_consentimiento_comun import *  # noqa: F401,F403
from envios_consentimiento_comun import (  # noqa: F401  (fixtures)
    client, db, mail, public_base, twilio, _auth, _campaign, _customer, _outbound, _phone, _seed,
)


# ------------------------------------------------------------------ #16 WhatsApp entrante


def test_flag_whatsapp_desactivado_por_defecto(monkeypatch):
    monkeypatch.delenv("TWILIO_WHATSAPP_ENABLED", raising=False)
    svc = WhatsAppService()
    assert svc.whatsapp_enabled is False and svc.is_configured() is False
    monkeypatch.setenv("TWILIO_WHATSAPP_ENABLED", "true")
    assert WhatsAppService().whatsapp_enabled is True


def test_entrante_sin_mapeo_a_empresa_no_responde_ni_llama_al_llm(db, twilio, monkeypatch):
    import asyncio

    import agents.zeus_core as zc

    def _never(*a, **k):
        raise AssertionError("no debe invocarse el agente sin empresa asociada")

    monkeypatch.setattr(zc.ZeusCore, "process_request", _never, raising=False)
    phone = _phone()
    out = asyncio.run(whatsapp_service.process_incoming_message(
        from_number=f"whatsapp:{phone}", message_body="Quiero mis datos bancarios 1234", to_number="whatsapp:+14155238886"))
    assert out["success"] is True and out["auto_reply"] is False and out["reason"] == "sin_empresa_asociada"
    assert twilio.sent == []
    db.expire_all()
    acts = (db.query(AgentActivity).filter(AgentActivity.action_type == "whatsapp_inbound_unrouted")
            .order_by(AgentActivity.id.desc()).limit(1).all())
    assert acts, "debe quedar registrado"
    dump = str(acts[0].details) + str(acts[0].action_description)
    assert phone not in dump and "bancarios" not in dump
    assert acts[0].details["from_masked"] == oc.mask_phone(phone)


def test_envio_whatsapp_no_registra_cuerpo_ni_telefono_completo(db, twilio):
    import asyncio

    phone = _phone()
    out = asyncio.run(whatsapp_service.send_message(phone, "secreto 9999"))
    assert out["success"] is True
    db.expire_all()
    act = (db.query(AgentActivity).filter(AgentActivity.action_type == "whatsapp_sent")
           .order_by(AgentActivity.id.desc()).first())
    dump = str(act.details) + str(act.action_description)
    assert phone not in dump and "secreto" not in dump
