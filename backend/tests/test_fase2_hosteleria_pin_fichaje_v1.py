"""Fase 2 / vertical hosteleria — PIN de fichaje ("Código manual") asignable de verdad.

El motor de fichajes exige company_employees.tpv_pin_hash para method=pin, pero nada lo
asignaba: el método era inutilizable. Ahora el dueño/encargado fija el PIN de un empleado
de SU empresa (solo se guarda el hash), y con ese PIN se ficha. Otra empresa -> 404 sin
tocar nada; empleado (rol member) -> 403; PIN no numérico o fuera de 4-8 dígitos -> 422.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.company import Company, UserCompany
from app.models.company_employee import CompanyEmployee
from app.models.thalos_security_event import ThalosSecurityEvent
from app.models.time_cost_checkin import TimeCostCheckin
from app.models.user import User


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _seed(db, tag, role="owner"):
    suf = uuid.uuid4().hex[:8]
    c = Company(company_name=f"PIN {tag} {suf}", slug=f"pin-{tag}-{suf}")
    u = User(email=f"pin_{tag}_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
             full_name=tag, is_active=True)
    db.add_all([c, u])
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role=role))
    code = f"P{suf}"
    db.add(CompanyEmployee(company_id=c.id, employee_code=code, full_name=f"Emp {tag}", hourly_rate=12.0))
    db.commit()
    db.refresh(u)
    return u, c.id, code


def _h(u):
    return {"Authorization": f"Bearer {create_access_token({'sub': u.email, 'email': u.email})}"}


def _emp(db, cid, code):
    db.expire_all()
    return db.query(CompanyEmployee).filter_by(company_id=cid, employee_code=code).one()


def _checkins(db, cid):
    db.expire_all()
    return db.query(TimeCostCheckin).filter(TimeCostCheckin.company_id == cid).count()


def test_dueno_asigna_pin_y_se_ficha_con_el(db):
    a, cid_a, code_a = _seed(db, "a")
    client = TestClient(app)
    body = {"company_id": cid_a, "employee_id": code_a, "type": "entrada", "method": "pin", "pin": "4821"}

    # Antes de asignar: el motor rechaza (sin PIN configurado) y no registra nada.
    r0 = client.post("/api/v1/checkin", json=body, headers=_h(a))
    assert r0.status_code == 422, r0.text
    assert _checkins(db, cid_a) == 0

    r = client.put(f"/api/v1/control-horario/employees/{code_a}/pin", json={"pin": "4821"}, headers=_h(a))
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["pin_configured"] is True and out["changed"] is False
    assert "4821" not in r.text  # nunca se devuelve el PIN

    emp = _emp(db, cid_a, code_a)
    assert emp.tpv_pin_hash and emp.tpv_pin_hash != "4821"  # nunca en claro
    assert verify_password("4821", emp.tpv_pin_hash)

    # Log real del cambio (evento THALOS de la empresa).
    ev = (db.query(ThalosSecurityEvent)
          .filter(ThalosSecurityEvent.event_type == "employee_pin_set",
                  ThalosSecurityEvent.company_id == cid_a).all())
    assert len(ev) == 1

    # PIN incorrecto -> 403 sin registro; el correcto ficha de verdad.
    bad = client.post("/api/v1/checkin", json={**body, "pin": "0000"}, headers=_h(a))
    assert bad.status_code == 403, bad.text
    assert _checkins(db, cid_a) == 0
    ok = client.post("/api/v1/checkin", json=body, headers=_h(a))
    assert ok.status_code == 200, ok.text
    assert _checkins(db, cid_a) == 1

    # Cambio de PIN: el antiguo deja de valer.
    r2 = client.put(f"/api/v1/control-horario/employees/{code_a}/pin", json={"pin": "73519046"}, headers=_h(a))
    assert r2.status_code == 200 and r2.json()["changed"] is True
    emp = _emp(db, cid_a, code_a)
    assert verify_password("73519046", emp.tpv_pin_hash) and not verify_password("4821", emp.tpv_pin_hash)

    # El roster informa de que hay PIN, sin exponerlo.
    roster = client.get("/api/v1/control-horario/bootstrap", headers=_h(a)).json()["employees"]
    mine = [e for e in roster if e["id"] == code_a][0]
    assert mine["pin_configured"] is True
    assert "tpv_pin_hash" not in mine


def test_otra_empresa_404_sin_tocar_el_pin(db):
    a, cid_a, code_a = _seed(db, "a")
    b, _, _ = _seed(db, "b")
    r = TestClient(app).put(f"/api/v1/control-horario/employees/{code_a}/pin", json={"pin": "1234"}, headers=_h(b))
    assert r.status_code == 404, r.text
    assert _emp(db, cid_a, code_a).tpv_pin_hash is None


def test_miembro_no_encargado_403(db):
    m, cid_m, code_m = _seed(db, "m", role="member")
    r = TestClient(app).put(f"/api/v1/control-horario/employees/{code_m}/pin", json={"pin": "1234"}, headers=_h(m))
    assert r.status_code == 403, r.text
    assert _emp(db, cid_m, code_m).tpv_pin_hash is None


@pytest.mark.parametrize("pin", ["123", "123456789", "12a4", "    ", "12 34"])
def test_pin_invalido_422(db, pin):
    a, cid_a, code_a = _seed(db, "a")
    r = TestClient(app).put(f"/api/v1/control-horario/employees/{code_a}/pin", json={"pin": pin}, headers=_h(a))
    assert r.status_code == 422, r.text
    assert _emp(db, cid_a, code_a).tpv_pin_hash is None


def test_sin_sesion_401(db):
    _, _, code = _seed(db, "x")
    assert TestClient(app).put(f"/api/v1/control-horario/employees/{code}/pin", json={"pin": "1234"}).status_code == 401
