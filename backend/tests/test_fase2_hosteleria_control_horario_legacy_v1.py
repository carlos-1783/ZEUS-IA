"""Fase 2 / vertical hosteleria — endpoints legacy de fichaje delegados en el motor v1.

/control-horario/check-in|check-out|break-start|break-end usaban el singleton global
control_horario_service (active_records en memoria por employee_id, compartido entre
empresas). Dos empresas con el mismo codigo de empleado se pisaban. Ahora delegan en
time_cost_engine_v1 (empresa, PIN, QR firmado, 501 biometrico) y no hay estado global.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.company import Company, UserCompany
from app.models.company_employee import CompanyEmployee
from app.models.time_tracking import RecordStatus, TimeTrackingRecord
from app.models.user import User
from services.checkin_qr_token import issue_company_qr_token
from services.control_horario_singleton import control_horario_service

P = "/api/v1/control-horario"
SHARED_CODE = f"E{uuid.uuid4().hex[:6]}"  # mismo codigo de empleado en las dos empresas


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _seed(db, tag, pin):
    suf = uuid.uuid4().hex[:8]
    c = Company(company_name=f"LG {tag} {suf}", slug=f"lg-{tag}-{suf}")
    u = User(email=f"lg_{tag}_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
             full_name=tag, is_active=True)
    db.add_all([c, u])
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    db.add(CompanyEmployee(company_id=c.id, employee_code=SHARED_CODE, full_name=f"Emp {tag}",
                           hourly_rate=10.0, tpv_pin_hash=get_password_hash(pin)))
    db.commit()
    db.refresh(u)
    return u, c.id


def _h(u):
    return {"Authorization": f"Bearer {create_access_token({'sub': u.email, 'email': u.email})}"}


def _active(db, cid):
    db.expire_all()
    return (db.query(TimeTrackingRecord)
            .filter(TimeTrackingRecord.company_id == cid, TimeTrackingRecord.employee_id == SHARED_CODE,
                    TimeTrackingRecord.status == RecordStatus.ACTIVE).count())


def test_mismo_codigo_en_dos_empresas_no_se_mezcla(db):
    a, cid_a = _seed(db, "a", "1111")
    b, cid_b = _seed(db, "b", "2222")
    client = TestClient(app)

    ra = client.post(f"{P}/check-in", json={"employee_id": SHARED_CODE, "method": "code", "pin": "1111"},
                     headers=_h(a))
    assert ra.status_code == 200, ra.text
    assert ra.json()["company_id"] == cid_a and ra.json()["via"] == "/api/v1/checkin"
    # El PIN de A no vale para el empleado homonimo de B.
    assert client.post(f"{P}/check-in", json={"employee_id": SHARED_CODE, "method": "code", "pin": "1111"},
                       headers=_h(b)).status_code == 403
    rb = client.post(f"{P}/check-in", json={"employee_id": SHARED_CODE, "method": "code", "pin": "2222"},
                     headers=_h(b))
    assert rb.status_code == 200, rb.text
    assert _active(db, cid_a) == 1 and _active(db, cid_b) == 1

    # Pausa y salida en A no tocan la sesion de B.
    assert client.post(f"{P}/break-start", json={"employee_id": SHARED_CODE, "method": "code", "pin": "1111"},
                       headers=_h(a)).status_code == 200
    assert client.post(f"{P}/break-end", json={"employee_id": SHARED_CODE, "method": "code", "pin": "1111"},
                       headers=_h(a)).status_code == 200
    out = client.post(f"{P}/check-out", json={"employee_id": SHARED_CODE, "method": "code", "pin": "1111"},
                      headers=_h(a))
    assert out.status_code == 200, out.text
    assert _active(db, cid_a) == 0 and _active(db, cid_b) == 1

    # B no ve los registros de A en su panel.
    recs_b = client.get(f"{P}/bootstrap", headers=_h(b)).json()["today_records"]
    db.expire_all()
    ids_a = {r.id for r in db.query(TimeTrackingRecord).filter(TimeTrackingRecord.company_id == cid_a).all()}
    assert ids_a and not ({r.get("id") for r in recs_b} & ids_a)

    # Ningun estado por empleado en el singleton global.
    assert control_horario_service.active_records == {}
    assert control_horario_service.employees == {}
    assert control_horario_service.schedules == {}


def test_validaciones_v1_en_legacy(db):
    a, cid_a = _seed(db, "a", "1111")
    _, cid_b = _seed(db, "b", "2222")
    client = TestClient(app)
    body = {"employee_id": SHARED_CODE}
    assert client.post(f"{P}/check-in", json={**body, "method": "face"}, headers=_h(a)).status_code == 501
    assert client.post(f"{P}/check-in", json={**body, "method": "qr", "qr_token": "inventado"},
                       headers=_h(a)).status_code == 403
    assert client.post(f"{P}/check-in", json={**body, "method": "qr", "qr_token": issue_company_qr_token(cid_b)},
                       headers=_h(a)).status_code == 403
    assert client.post(f"{P}/check-in", json={**body, "method": "code"}, headers=_h(a)).status_code == 422
    assert client.post(f"{P}/check-in", json={**body, "method": "location"}, headers=_h(a)).status_code == 422
    assert client.post(f"{P}/check-in", json={**body, "method": "qr"}).status_code == 401
    assert _active(db, cid_a) == 0
    ok = client.post(f"{P}/check-in", json={**body, "method": "qr", "qr_token": issue_company_qr_token(cid_a)},
                     headers=_h(a))
    assert ok.status_code == 200, ok.text
    assert _active(db, cid_a) == 1


def test_calculate_hours_desde_bd_y_por_empresa(db):
    a, cid_a = _seed(db, "a", "1111")
    b, _ = _seed(db, "b", "2222")
    now = datetime.now(timezone.utc)
    db.add(TimeTrackingRecord(user_id=a.id, company_id=cid_a, employee_id=SHARED_CODE,
                              check_in_time=now - timedelta(hours=5), check_out_time=now - timedelta(hours=1),
                              hours_worked=4.0, status=RecordStatus.COMPLETED))
    db.commit()
    rng = {"employee_id": SHARED_CODE, "start_date": (now - timedelta(days=1)).isoformat(),
           "end_date": (now + timedelta(days=1)).isoformat()}
    client = TestClient(app)
    ra = client.post(f"{P}/calculate-hours", json=rng, headers=_h(a)).json()
    rb = client.post(f"{P}/calculate-hours", json=rng, headers=_h(b)).json()
    assert ra["total_hours"] == 4.0 and ra["records_count"] == 1
    assert rb["total_hours"] == 0 and rb["records_count"] == 0
