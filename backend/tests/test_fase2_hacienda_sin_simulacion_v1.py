"""Fase 2 / Step 2 — Hacienda ya no devuelve envios a la AEAT "aceptados" ni CSV inventados."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.company import Company, UserCompany
from app.models.user import User
from services.hacienda_service import HaciendaError, HaciendaService

P = "/api/v1"
_AEAT = ("AEAT_NIF", "AEAT_PASSWORD", "AEAT_CERTIFICATE_PATH")
_FACTURA = {"numero": "F-1", "fecha": "2026-10-01", "cliente_nif": "B12345678", "cliente_nombre": "X",
            "base_imponible": 100.0, "tipo_iva": 21.0, "cuota_iva": 21.0, "total": 121.0}
_M303 = {"trimestre": 3, "ejercicio": 2026, "base_imponible_general": 1000.0,
         "cuota_iva_soportado": 50.0, "cuota_iva_repercutido": 210.0}


def _env(monkeypatch, configured: bool):
    for k in _AEAT:
        if configured:
            monkeypatch.setenv(k, "x")
        else:
            monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("AEAT_ENVIRONMENT", "test")  # el modo que antes simulaba


@pytest.mark.parametrize("configured,code", [(False, 503), (True, 501)])
def test_sii_never_reports_acceptance(monkeypatch, configured, code):
    _env(monkeypatch, configured)
    with pytest.raises(HaciendaError) as exc:
        asyncio.run(HaciendaService().enviar_factura_emitida(dict(_FACTURA)))
    assert exc.value.status_code == code
    text = str(exc.value.detail)
    assert "SIMULADO" not in text and "TEST-CSV" not in text and "csv" not in exc.value.detail
    assert exc.value.detail["enviada"] is False


def test_303_returns_real_draft_marked_not_presented(monkeypatch):
    _env(monkeypatch, True)
    with pytest.raises(HaciendaError) as exc:
        asyncio.run(HaciendaService().presentar_modelo_303(3, 2026, dict(_M303)))
    assert exc.value.status_code == 501
    b = exc.value.detail["borrador_no_presentado"]
    assert b["resultado"] == 160.0 and b["tipo"] == "A ingresar" and b["presentado"] is False
    assert "csv" not in str(exc.value.detail).lower()


def test_status_does_not_claim_available_models(monkeypatch):
    _env(monkeypatch, True)
    st = HaciendaService().get_status()
    assert st["modelos_disponibles"] == [] and st["sii_implemented"] is False
    assert not hasattr(HaciendaService(), "generar_factura_pdf")


def test_endpoints_propagate_honest_status(monkeypatch):
    _env(monkeypatch, False)
    Base.metadata.create_all(bind=engine, tables=[User.__table__, Company.__table__, UserCompany.__table__])
    db = SessionLocal()
    suf = uuid.uuid4().hex[:8]
    c = Company(company_name=f"Hac {suf}", slug=f"hac-{suf}")
    u = User(email=f"hac_{suf}@example.com", hashed_password=get_password_hash("TestPass1"),
             is_active=True, is_superuser=True)
    db.add_all([c, u]); db.flush()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner")); db.commit()
    email = u.email
    db.close()
    client = TestClient(app)
    tok = client.post(f"{P}/auth/login", data={"username": email, "password": "TestPass1"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    r = client.post(f"{P}/integrations/hacienda/factura", json=_FACTURA, headers=h)
    assert r.status_code == 503, r.text
    assert "AEAT_CERTIFICATE_PATH" in r.text and "Aceptada" not in r.text
    r = client.post(f"{P}/integrations/hacienda/modelo-303", json=_M303, headers=h)
    assert r.status_code == 503 and r.json()["detail"]["borrador_no_presentado"]["resultado"] == 160.0
