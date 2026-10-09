"""J13: varias rutas devolvian `str(e)` sin sanear en el `detail`/`message`/`error` de la
respuesta HTTP, filtrando mensajes internos (SQLAlchemy, rutas de fichero, etc.) al cliente.

Estos tests fuerzan la excepcion real (monkeypatch de la capa que falla, no mocks del
endpoint entero) para cada ruta corregida y comprueban:
  (a) la respuesta HTTP NO contiene el texto de la excepcion original;
  (b) el codigo de estado sigue siendo razonable (no se cambia 2xx/4xx->5xx sin motivo,
      ni 5xx->500 opaco se convierte en falso exito);
  (c) el detalle real SI llega al log del servidor (via caplog), para demostrar que no se
      perdio informacion de depuracion, solo se dejo de exponer al cliente.

Sin red, sin LLM, sin credenciales reales: todo con monkeypatch sobre la capa que falla.
"""

from __future__ import annotations

import json
import logging
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from twilio.request_validator import RequestValidator

from app.api.v1.endpoints import analytics as analytics_endpoint
from app.api.v1.endpoints import control_horario as control_horario_endpoint
from app.api.v1.endpoints import customers as customers_endpoint
from app.api.v1.endpoints import onboarding as onboarding_endpoint
from app.core.auth import get_current_active_superuser, get_current_active_user
from app.core.config import settings
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.db.session import get_db as session_get_db
from app.main import app
from app.models.company import Company, UserCompany
from app.models.user import User
from services.whatsapp_service import whatsapp_service

SECRET = "SECRETO-INTERNO-postgres://user:pw@host/db psycopg2.OperationalError columna xyz no existe"
P = "/api/v1"


class BrokenSession:
    """Sesion de BD falsa: cualquier `query`/`execute` lanza con el SECRET dentro."""

    def query(self, *a, **k):
        raise RuntimeError(SECRET)

    def execute(self, *a, **k):
        raise RuntimeError(SECRET)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


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
    c = TestClient(app)
    try:
        yield c
    finally:
        app.dependency_overrides.clear()


def _user(db, *, superuser: bool = False) -> User:
    suf = uuid.uuid4().hex[:8]
    c = Company(company_name=f"J13 {suf}", slug=f"j13-{suf}")
    db.add(c)
    db.flush()
    u = User(
        email=f"j13_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name="J13",
        is_active=True,
        is_superuser=superuser,
    )
    db.add(u)
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    db.commit()
    db.refresh(u)
    return u


FAKE_USER = SimpleNamespace(id=1, email="fake_j13@example.test", is_superuser=False)


# ---------------------------------------------------------------------------
# activities.py
# ---------------------------------------------------------------------------

def test_activities_get_oculta_excepcion_y_loguea(client, monkeypatch, caplog):
    from services.activity_logger import ActivityLogger

    def boom(*a, **k):
        raise RuntimeError(SECRET)

    monkeypatch.setattr(ActivityLogger, "get_agent_activities", staticmethod(boom))
    app.dependency_overrides[get_current_active_user] = lambda: FAKE_USER
    with caplog.at_level(logging.ERROR, logger="app.api.v1.endpoints.activities"):
        r = client.get(f"{P}/activities/ZEUS")
    assert r.status_code == 500
    assert SECRET not in r.text
    assert r.json()["detail"] == "No se pudieron obtener las actividades. Inténtalo de nuevo."
    assert any(SECRET in rec.getMessage() or SECRET in (rec.exc_text or "") for rec in caplog.records)


def test_activities_log_oculta_excepcion(client, db, monkeypatch):
    from services.activity_logger import ActivityLogger

    def boom(*a, **k):
        raise RuntimeError(SECRET)

    monkeypatch.setattr(ActivityLogger, "log_activity", staticmethod(boom))
    # POST: cubierto por el guard THALOS global (toda ruta mutante bajo /api/), que a su vez
    # depende de get_current_active_user y exige empresa -- hace falta un usuario real con
    # empresa (ver services/thalos_request_guard_v1.py), un SimpleNamespace sin empresa no basta.
    u = _user(db)
    app.dependency_overrides[get_current_active_user] = lambda: u
    r = client.post(
        f"{P}/activities/log",
        json={
            "agent_name": "ZEUS",
            "action_type": "test",
            "action_description": "prueba",
        },
    )
    assert r.status_code == 500
    assert SECRET not in r.text
    assert r.json()["detail"] == "No se pudo registrar la actividad. Inténtalo de nuevo."


# ---------------------------------------------------------------------------
# admin.py
# ---------------------------------------------------------------------------

def test_admin_stats_oculta_excepcion(client, db):
    su = _user(db, superuser=True)
    app.dependency_overrides[get_current_active_superuser] = lambda: su
    app.dependency_overrides[session_get_db] = lambda: BrokenSession()
    r = client.get(f"{P}/admin/stats")
    assert r.status_code == 500
    assert SECRET not in r.text
    assert r.json()["detail"] == "No se pudieron obtener las estadísticas. Inténtalo de nuevo."


def test_admin_bootstrap_internal_company_oculta_excepcion(client, db, monkeypatch):
    su = _user(db, superuser=True)
    app.dependency_overrides[get_current_active_superuser] = lambda: su
    # POST: tambien pasa por el guard THALOS global, que depende de get_current_active_user
    # (independiente de get_current_active_superuser) y exige empresa.
    app.dependency_overrides[get_current_active_user] = lambda: su

    def boom(*a, **k):
        raise RuntimeError(SECRET)

    monkeypatch.setattr("services.internal_company_bootstrap.run_bootstrap", boom)
    r = client.post(f"{P}/admin/bootstrap-internal-company")
    assert r.status_code == 500
    assert SECRET not in r.text
    assert (
        r.json()["detail"]
        == "No se pudo completar el bootstrap de la empresa interna. Inténtalo de nuevo."
    )


# ---------------------------------------------------------------------------
# analytics.py
# ---------------------------------------------------------------------------

def test_analytics_executive_failsafe_oculta_excepcion(client, db, monkeypatch):
    u = _user(db)
    app.dependency_overrides[get_current_active_user] = lambda: u

    def boom(*a, **k):
        raise RuntimeError(SECRET)

    monkeypatch.setattr(analytics_endpoint, "build_executive_analytics", boom)
    r = client.get(f"{P}/analytics/executive")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is False
    assert SECRET not in r.text
    assert body["error"] == "No se pudieron calcular los KPIs ejecutivos."


def test_analytics_summary_failsafe_oculta_excepcion(client, db, monkeypatch):
    u = _user(db)
    app.dependency_overrides[get_current_active_user] = lambda: u

    def boom(*a, **k):
        raise RuntimeError(SECRET)

    monkeypatch.setattr(analytics_endpoint, "build_analytics_summary", boom)
    r = client.get(f"{P}/analytics/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is False
    assert SECRET not in r.text
    assert body["error"] == "No se pudo calcular el resumen de analítica."


# ---------------------------------------------------------------------------
# auth.py (login -> jornada)
# ---------------------------------------------------------------------------

def test_login_jornada_error_oculta_excepcion(db, caplog):
    """`create_tokens` arma el dict `jornada` con el error saneado. NOTA: /login, /token y
    /refresh declaran `response_model=Token` (sin campo `jornada`), asi que FastAPI ya lo
    filtra de la respuesta HTTP real por contrato de schema -- se prueba aqui la funcion
    directamente para fijar que, aunque ese filtrado cambiara, el dict en si ya no lleva
    el texto crudo de la excepcion (defensa en profundidad)."""
    import asyncio

    from app.api.v1.endpoints.auth import create_tokens
    import services.employee_work_session_service as ws

    suf = uuid.uuid4().hex[:8]
    u = User(
        email=f"j13login_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name="J13 Login",
        is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)

    def boom(*a, **k):
        raise RuntimeError(SECRET)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(ws, "begin_work_session_on_login", boom)
        with caplog.at_level(logging.ERROR, logger="app.api.v1.endpoints.auth"):
            result = asyncio.run(create_tokens(db, u))
    assert result["jornada"]["error"] == "No se pudo iniciar la jornada laboral."
    assert SECRET not in str(result)
    assert any(SECRET in rec.getMessage() for rec in caplog.records)


# ---------------------------------------------------------------------------
# control_horario.py
# ---------------------------------------------------------------------------

def test_control_horario_employees_oculta_excepcion_y_loguea(client, db, monkeypatch, caplog):
    u = _user(db)
    app.dependency_overrides[get_current_active_user] = lambda: u

    def boom(*a, **k):
        raise RuntimeError(SECRET)

    monkeypatch.setattr(control_horario_endpoint, "_active_status_from_db", boom)
    with caplog.at_level(logging.ERROR, logger="app.api.v1.endpoints.control_horario"):
        r = client.get(f"{P}/control-horario/employees")
    assert r.status_code == 500
    assert SECRET not in r.text
    assert r.json()["detail"] == "No se pudo obtener la lista de empleados. Inténtalo de nuevo."
    assert any(SECRET in (rec.exc_text or "") or SECRET in rec.getMessage() for rec in caplog.records)


# ---------------------------------------------------------------------------
# customers.py
# ---------------------------------------------------------------------------

def test_customers_create_oculta_excepcion(client, db, monkeypatch):
    u = _user(db)
    app.dependency_overrides[get_current_active_user] = lambda: u

    def boom(*a, **k):
        raise RuntimeError(SECRET)

    monkeypatch.setattr(customers_endpoint.crm_svc, "create_customer", boom)
    r = client.post(f"{P}/customers", json={"name": "Cliente J13"})
    assert r.status_code == 500
    assert SECRET not in r.text
    assert r.json()["detail"] == "No se pudo crear el cliente. Inténtalo de nuevo."


# ---------------------------------------------------------------------------
# document_approval.py
# ---------------------------------------------------------------------------

def test_document_approval_pending_oculta_excepcion(client, db):
    u = _user(db)
    app.dependency_overrides[get_current_active_user] = lambda: u
    app.dependency_overrides[session_get_db] = lambda: BrokenSession()
    r = client.get(f"{P}/documents/pending")
    assert r.status_code == 500
    assert SECRET not in r.text
    assert (
        r.json()["detail"]
        == "No se pudieron obtener los documentos pendientes. Inténtalo de nuevo."
    )


# ---------------------------------------------------------------------------
# health.py
# ---------------------------------------------------------------------------

def test_health_detailed_oculta_excepcion_bd(client):
    app.dependency_overrides[session_get_db] = lambda: BrokenSession()
    r = client.get(f"{P}/health/detailed")
    assert r.status_code == 200
    body = r.json()
    assert SECRET not in r.text
    assert body["status"] == "unhealthy"
    assert body["database"] == "unhealthy"
    assert body["fiscal_schema"]["status"] in ("error", "ok", "gaps")


def test_health_ready_oculta_excepcion_bd(client):
    app.dependency_overrides[session_get_db] = lambda: BrokenSession()
    r = client.get(f"{P}/health/ready")
    assert r.status_code == 503
    assert SECRET not in r.text
    assert r.json()["detail"] == "Service not ready"


# ---------------------------------------------------------------------------
# metrics.py
# ---------------------------------------------------------------------------

def test_metrics_summary_failsafe_oculta_excepcion(client, db, monkeypatch):
    u = _user(db)
    app.dependency_overrides[get_current_active_user] = lambda: u

    def boom(*a, **k):
        raise RuntimeError(SECRET)

    import services.analytics_service as analytics_service

    monkeypatch.setattr(analytics_service, "build_analytics_summary", boom)
    r = client.get(f"{P}/metrics/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is False
    assert SECRET not in r.text
    assert body["error"] == "No se pudo calcular el resumen del dashboard."


# ---------------------------------------------------------------------------
# onboarding.py
# ---------------------------------------------------------------------------

def test_onboarding_verify_payment_oculta_excepcion(client, monkeypatch):
    from services.stripe_service import stripe_service

    monkeypatch.setattr(stripe_service, "is_configured", lambda: True)

    import stripe

    def boom(*a, **k):
        raise RuntimeError(SECRET)

    monkeypatch.setattr(stripe.PaymentIntent, "retrieve", staticmethod(boom))
    r = client.get(f"{P}/onboarding/verify-payment/pi_test123")
    assert r.status_code == 500
    assert SECRET not in r.text
    assert r.json()["detail"] == "No se pudo verificar el pago. Inténtalo de nuevo."


def test_onboarding_create_account_oculta_excepcion(client, monkeypatch):
    monkeypatch.setattr(
        onboarding_endpoint,
        "_verify_stripe_payment_intent",
        lambda pid, plan: SimpleNamespace(customer="cus_test_j13", status="succeeded"),
    )

    async def boom(**kwargs):
        raise RuntimeError(SECRET)

    monkeypatch.setattr(onboarding_endpoint, "send_welcome_email", boom)
    suf = uuid.uuid4().hex[:8]
    payload = {
        "company_name": f"Empresa J13 {suf}",
        "email": f"j13create_{suf}@example.com",
        "full_name": "J13 Create",
        "employees": 2,
        "plan": "startup",
        "payment_intent_id": "pi_test_j13",
    }
    r = client.post(f"{P}/onboarding/create-account", json=payload)
    assert r.status_code == 500
    assert SECRET not in r.text
    assert r.json()["detail"] == "No se pudo crear la cuenta. Inténtalo de nuevo."


# ---------------------------------------------------------------------------
# webhooks.py (Twilio: firma valida, el fallo es DESPUES de verificarla)
# ---------------------------------------------------------------------------

FORM = {"From": "whatsapp:+34600000000", "To": "whatsapp:+14155238886", "Body": "hola", "MessageSid": "SMx"}
FAKE_TWILIO_TOKEN = "fake-twilio-token-for-j13-tests"


def _sign(path, params, token=FAKE_TWILIO_TOKEN, base="http://testserver"):
    return RequestValidator(token).compute_signature(base + path, params)


def test_webhooks_twilio_oculta_excepcion_tras_firma_valida(client, monkeypatch):
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", FAKE_TWILIO_TOKEN)
    path = f"{P}/webhooks/twilio"
    boom = AsyncMock(side_effect=RuntimeError(SECRET))
    monkeypatch.setattr(whatsapp_service, "process_incoming_message", boom)
    r = client.post(path, data=FORM, headers={"X-Twilio-Signature": _sign(path, FORM)})
    assert r.status_code == 500
    assert SECRET not in r.text
    assert r.json()["detail"] == "Error processing Twilio webhook"
    boom.assert_awaited_once()


# ---------------------------------------------------------------------------
# J13b: fugas residuales encontradas por el revisor durante J13 (fuera de su
# alcance declarado en ese momento) -- mismo patron: mensaje generico al
# cliente, detalle real solo al log.
# ---------------------------------------------------------------------------

def test_admin_delete_customer_oculta_excepcion_sqlalchemy_y_loguea(client, db, monkeypatch, caplog):
    """admin_account_service.delete_user_account envolvia un SQLAlchemyError crudo en el
    ValueError que admin.py reenvia tal cual en el HTTPException (400)."""
    from sqlalchemy.exc import SQLAlchemyError

    su = _user(db, superuser=True)
    target = _user(db)
    app.dependency_overrides[get_current_active_superuser] = lambda: su
    # POST mutante: pasa tambien por el guard THALOS global que depende de
    # get_current_active_user (independiente de get_current_active_superuser).
    app.dependency_overrides[get_current_active_user] = lambda: su
    app.dependency_overrides[session_get_db] = lambda: db

    def boom(*a, **k):
        raise SQLAlchemyError(SECRET)

    monkeypatch.setattr(db, "commit", boom)

    with caplog.at_level(logging.ERROR, logger="services.admin_account_service"):
        r = client.post(
            f"{P}/admin/customers/{target.id}/delete",
            json={"confirm_email": target.email, "reason": "test_account"},
        )
    assert r.status_code == 400
    assert SECRET not in r.text
    assert r.json()["detail"] == "Error al eliminar la cuenta. Inténtalo de nuevo o contacta soporte."
    assert any(SECRET in (rec.exc_text or "") or SECRET in rec.getMessage() for rec in caplog.records)


def test_websocket_jwt_error_oculta_excepcion_y_loguea(client, monkeypatch, caplog):
    """websocket.py enviaba str(e) crudo del error JWT (no de audiencia) directo al
    cliente por send_text, y tambien en el `reason` del close frame."""
    import app.api.v1.endpoints.websocket as ws_endpoint
    from jose.exceptions import ExpiredSignatureError

    def boom(*a, **k):
        raise ExpiredSignatureError(SECRET)

    monkeypatch.setattr(ws_endpoint, "get_current_websocket_user", boom)

    with caplog.at_level(logging.ERROR, logger="app.api.v1.endpoints.websocket"):
        with client.websocket_connect(f"{P}/ws/j13b-test-client?token=fake.jwt.token") as ws:
            raw = ws.receive_text()

    assert SECRET not in raw
    body = json.loads(raw)
    assert body["code"] == "jwt_validation_error"
    assert SECRET not in body["details"]
    assert any(SECRET in rec.getMessage() or SECRET in (rec.exc_text or "") for rec in caplog.records)


def test_webhooks_stripe_invalid_payload_oculta_excepcion_y_loguea(client, monkeypatch, caplog):
    """webhooks.py Stripe: ValueError al parsear el payload se devolvia como
    `Invalid payload: {e}`, filtrando el detalle crudo de la libreria stripe."""
    import stripe

    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_j13b_fake")

    def boom(*a, **k):
        raise ValueError(SECRET)

    monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(boom))

    with caplog.at_level(logging.ERROR, logger="app.api.v1.endpoints.webhooks"):
        r = client.post(
            f"{P}/webhooks/stripe",
            data=b"{}",
            headers={"Stripe-Signature": "t=1,v1=fake"},
        )
    assert r.status_code == 400
    assert SECRET not in r.text
    assert r.json()["detail"] == "Invalid payload"
    assert any(SECRET in (rec.exc_text or "") or SECRET in rec.getMessage() for rec in caplog.records)


def test_webhooks_stripe_invalid_signature_oculta_excepcion_y_loguea(client, monkeypatch, caplog):
    """Idem para SignatureVerificationError: `Invalid signature: {e}` filtraba el
    mensaje crudo de stripe (puede incluir fragmentos del payload/firma)."""
    import stripe

    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_j13b_fake")

    def boom(*a, **k):
        raise stripe.error.SignatureVerificationError(SECRET, "sig_header_value")

    monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(boom))

    with caplog.at_level(logging.ERROR, logger="app.api.v1.endpoints.webhooks"):
        r = client.post(
            f"{P}/webhooks/stripe",
            data=b"{}",
            headers={"Stripe-Signature": "t=1,v1=fake"},
        )
    assert r.status_code == 400
    assert SECRET not in r.text
    assert r.json()["detail"] == "Invalid signature"
    assert any(SECRET in (rec.exc_text or "") or SECRET in rec.getMessage() for rec in caplog.records)
