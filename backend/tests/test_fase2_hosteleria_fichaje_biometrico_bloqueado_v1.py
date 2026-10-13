"""Fase 2 / vertical hosteleria — fichaje biometrico bloqueado de forma honesta.

Antes la UI mapeaba "Facial" a method=device y fichaba sin procesar ninguna cara, y el
endpoint legacy aceptaba method=face y lo guardaba como fichaje facial. Ahora:
- POST /api/v1/checkin y /api/checkin con method=face -> 501 con motivo legal, sin
  crear ningun registro.
- POST /api/v1/control-horario/check-in con method=face -> 501, sin registro.
- La config devuelta nunca ofrece 'face' como habilitado e incluye el motivo.
- El fichaje NO biometrico (PIN) sigue funcionando y otra empresa no puede fichar
  empleados ajenos.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.company import Company, UserCompany
from app.models.company_employee import CompanyEmployee
from app.models.time_cost_checkin import TimeCostCheckin
from app.models.time_tracking import TimeTrackingRecord
from app.models.user import User


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _seed(db, tag):
    suf = uuid.uuid4().hex[:8]
    c = Company(company_name=f"Rest {tag} {suf}", slug=f"rest-{tag}-{suf}")
    u = User(email=f"rest_{tag}_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
             full_name=tag, is_active=True)
    db.add_all([c, u])
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    code = f"E{suf}"
    db.add(CompanyEmployee(company_id=c.id, employee_code=code, full_name=f"Emp {tag}",
                           hourly_rate=10.0, tpv_pin_hash=get_password_hash("1234")))
    db.commit()
    db.refresh(u)
    return u, c.id, code


def _h(u):
    return {"Authorization": f"Bearer {create_access_token({'sub': u.email, 'email': u.email})}"}


def _counts(db, cid):
    db.expire_all()
    return (
        db.query(TimeCostCheckin).filter(TimeCostCheckin.company_id == cid).count(),
        db.query(TimeTrackingRecord).filter(TimeTrackingRecord.company_id == cid).count(),
    )


@pytest.mark.parametrize("path", ["/api/v1/checkin", "/api/checkin"])
def test_checkin_facial_501_sin_registro(db, path):
    u, cid, code = _seed(db, "a")
    before = _counts(db, cid)
    r = TestClient(app).post(path, json={"company_id": cid, "employee_id": code, "type": "entrada",
                                         "method": "face"}, headers=_h(u))
    assert r.status_code == 501, r.text
    assert "biometric" in r.text.lower() or "biométric" in r.text.lower() or "biometrico" in r.text.lower()
    assert r.headers.get("X-Zeus-Block") == "biometric_checkin_blocked"
    assert _counts(db, cid) == before


def test_control_horario_legacy_facial_501(db):
    u, cid, code = _seed(db, "a")
    before = _counts(db, cid)
    r = TestClient(app).post("/api/v1/control-horario/check-in",
                             json={"employee_id": code, "method": "face"}, headers=_h(u))
    assert r.status_code == 501, r.text
    assert _counts(db, cid) == before


def test_config_no_ofrece_facial_y_explica_motivo(db):
    u, _, _ = _seed(db, "a")
    info = TestClient(app).get("/api/v1/control-horario/bootstrap", headers=_h(u)).json()["info"]
    assert "face" not in (info["config"].get("methods_enabled") or [])
    assert "RGPD" in info["blocked_methods"]["face"]


def test_fichaje_pin_funciona_y_otra_empresa_no_ficha_empleados_ajenos(db):
    a, cid_a, code_a = _seed(db, "a")
    b, _, _ = _seed(db, "b")
    client = TestClient(app)
    ok = client.post("/api/v1/checkin", json={"company_id": cid_a, "employee_id": code_a, "type": "entrada",
                                              "method": "pin", "pin": "1234"}, headers=_h(a))
    assert ok.status_code == 200, ok.text
    assert ok.json()["company_id"] == cid_a
    ajeno = client.post("/api/v1/checkin", json={"company_id": cid_a, "employee_id": code_a, "type": "salida",
                                                 "method": "pin", "pin": "1234"}, headers=_h(b))
    assert ajeno.status_code == 403
