"""J5f: webhooks entrantes firmados (Twilio/WhatsApp, email inbound) y onboarding sin enumeracion.
Sin red ni LLM: se sustituyen solo process_incoming_message / process_incoming_email."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from twilio.request_validator import RequestValidator

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.thalos_security_event import ThalosSecurityEvent
from app.models.user import User
from services.whatsapp_service import whatsapp_service
from services.email_service import email_service

P = "/api/v1"
FAKE_TOKEN = "fake-twilio-token-for-tests"
FAKE_SECRET = "fake-inbound-secret-for-tests"
FORM = {"From": "whatsapp:+34600000000", "To": "whatsapp:+14155238886", "Body": "hola", "MessageSid": "SMx"}
TWILIO_ROUTES = [f"{P}/webhooks/twilio", f"{P}/integrations/whatsapp/webhook"]


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def wa(monkeypatch):
    m = AsyncMock(return_value={"success": True, "response": "ok", "whatsapp_status": {"success": True}})
    monkeypatch.setattr(whatsapp_service, "process_incoming_message", m)
    return m


def _sign(path, params, token=FAKE_TOKEN, base="http://testserver"):
    return RequestValidator(token).compute_signature(base + path, params)


@pytest.mark.parametrize("path", TWILIO_ROUTES)
def test_twilio_sin_firma_403_y_no_procesa(client, wa, monkeypatch, path):
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", FAKE_TOKEN)
    r = client.post(path, data=FORM)
    assert r.status_code == 403
    wa.assert_not_called()


@pytest.mark.parametrize("path", TWILIO_ROUTES)
def test_twilio_firma_invalida_403(client, wa, monkeypatch, path):
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", FAKE_TOKEN)
    r = client.post(path, data=FORM, headers={"X-Twilio-Signature": _sign(path, FORM, token="otro")})
    assert r.status_code == 403
    wa.assert_not_called()


@pytest.mark.parametrize("path", TWILIO_ROUTES)
def test_twilio_firma_valida_procesa(client, wa, monkeypatch, path):
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", FAKE_TOKEN)
    r = client.post(path, data=FORM, headers={"X-Twilio-Signature": _sign(path, FORM)})
    assert r.status_code == 200, r.text
    wa.assert_awaited_once()


def test_twilio_firma_valida_tras_proxy_forwarded(client, wa, monkeypatch):
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", FAKE_TOKEN)
    path = TWILIO_ROUTES[0]
    sig = _sign(path, FORM, base="https://api.ejemplo.test")
    r = client.post(path, data=FORM, headers={
        "X-Twilio-Signature": sig, "X-Forwarded-Proto": "https", "X-Forwarded-Host": "api.ejemplo.test"})
    assert r.status_code == 200
    wa.assert_awaited_once()


def test_twilio_public_base_url_configurada(client, wa, monkeypatch):
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", FAKE_TOKEN)
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "https://publica.ejemplo.test")
    path = TWILIO_ROUTES[1]
    r = client.post(path, data=FORM, headers={"X-Twilio-Signature": _sign(path, FORM, base="https://publica.ejemplo.test")})
    assert r.status_code == 200


@pytest.mark.parametrize("path", TWILIO_ROUTES)
def test_twilio_token_no_configurado_503(client, wa, monkeypatch, path):
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "")
    r = client.post(path, data=FORM, headers={"X-Twilio-Signature": _sign(path, FORM)})
    assert r.status_code == 503
    wa.assert_not_called()


def test_twilio_denegacion_registra_evento_thalos(client, db, wa, monkeypatch):
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", FAKE_TOKEN)
    client.post(TWILIO_ROUTES[0], data=FORM)
    ev = (db.query(ThalosSecurityEvent).filter(ThalosSecurityEvent.source == "twilio_signature")
          .order_by(ThalosSecurityEvent.id.desc()).first())
    assert ev is not None and ev.action_taken == "deny" and ev.decision_rule == "twilio_signature_missing"


EMAIL = f"{P}/integrations/email/webhook"
EFORM = {"from": "a@example.test", "subject": "s", "text": "cuerpo"}


@pytest.fixture()
def em(monkeypatch):
    m = AsyncMock(return_value={"success": True})
    monkeypatch.setattr(email_service, "process_incoming_email", m)
    return m


def test_email_sin_secreto_configurado_503(client, em, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_INBOUND_WEBHOOK_SECRET", "")
    r = client.post(f"{EMAIL}?secret={FAKE_SECRET}", data=EFORM)
    assert r.status_code == 503
    em.assert_not_called()


def test_email_sin_secreto_en_peticion_403(client, em, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_INBOUND_WEBHOOK_SECRET", FAKE_SECRET)
    assert client.post(EMAIL, data=EFORM).status_code == 403
    em.assert_not_called()


def test_email_secreto_incorrecto_403(client, em, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_INBOUND_WEBHOOK_SECRET", FAKE_SECRET)
    assert client.post(f"{EMAIL}?secret=mal", data=EFORM).status_code == 403
    assert client.post(EMAIL, data=EFORM, headers={"X-Inbound-Secret": "mal"}).status_code == 403
    em.assert_not_called()


def test_email_secreto_correcto_procesa(client, em, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_INBOUND_WEBHOOK_SECRET", FAKE_SECRET)
    assert client.post(f"{EMAIL}?secret={FAKE_SECRET}", data=EFORM).status_code == 200
    assert client.post(EMAIL, data=EFORM, headers={"X-Inbound-Secret": FAKE_SECRET}).status_code == 200
    assert em.await_count == 2


def _mk_user(db):
    suf = uuid.uuid4().hex[:8]
    u = User(email=f"j5f_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
             full_name="J5f", is_active=True, is_superuser=False)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_onboarding_anonimo_no_enumera(client, db):
    u = _mk_user(db)
    for email in (u.email, "no-existe-j5f@example.test"):
        assert client.get(f"{P}/onboarding/status/{email}").status_code == 401
        assert client.post(f"{P}/onboarding/complete-onboarding?email={email}").status_code == 401


def test_onboarding_autenticado_solo_propio_y_sin_enumeracion(client, db):
    u = _mk_user(db)
    otro = _mk_user(db)
    tok = client.post(f"{P}/auth/login", data={"username": u.email, "password": "TestPass1"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    own = client.get(f"{P}/onboarding/status/{u.email}", headers=h)
    assert own.status_code == 200 and own.json()["user_id"] == u.id
    r_exist = client.get(f"{P}/onboarding/status/{otro.email}", headers=h)
    r_none = client.get(f"{P}/onboarding/status/no-existe-j5f@example.test", headers=h)
    assert r_exist.status_code == r_none.status_code == 403
    assert r_exist.json() == r_none.json()
    assert client.post(f"{P}/onboarding/complete-onboarding", headers=h).status_code == 410
