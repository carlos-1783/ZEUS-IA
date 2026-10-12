"""Fase 2 / vertical hosteleria — fichaje QR con token real de la empresa.

Antes method=qr aceptaba cualquier cadena no vacia y la UI fabricaba el token.
Ahora el token debe ser el QR firmado de la empresa: inventado o de otra empresa -> 403
y sin registro; el de la empresa -> fichaje real. El QR solo lo obtiene quien
pertenece a la empresa (otra empresa -> 403).
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
    c = Company(company_name=f"QR {tag} {suf}", slug=f"qr-{tag}-{suf}")
    u = User(email=f"qr_{tag}_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
             full_name=tag, is_active=True)
    db.add_all([c, u])
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    code = f"Q{suf}"
    db.add(CompanyEmployee(company_id=c.id, employee_code=code, full_name=f"Emp {tag}", hourly_rate=12.0))
    db.commit()
    db.refresh(u)
    return u, c.id, code


def _h(u):
    return {"Authorization": f"Bearer {create_access_token({'sub': u.email, 'email': u.email})}"}


def _n(db, cid):
    db.expire_all()
    return db.query(TimeCostCheckin).filter(TimeCostCheckin.company_id == cid).count()


def test_qr_inventado_o_ajeno_rechazado_y_el_real_ficha(db):
    a, cid_a, code_a = _seed(db, "a")
    b, cid_b, _ = _seed(db, "b")
    client = TestClient(app)

    qr_a = client.get(f"/api/v1/checkin/qr-token?company_id={cid_a}", headers=_h(a))
    assert qr_a.status_code == 200, qr_a.text
    tok_a = qr_a.json()["qr_token"]
    tok_b = client.get("/api/v1/checkin/qr-token", headers=_h(b)).json()["qr_token"]
    assert tok_a != tok_b

    body = {"company_id": cid_a, "employee_id": code_a, "type": "entrada", "method": "qr"}
    for fake in (f"ui-{code_a}-1700000000", tok_b, tok_a[:-1] + ("0" if tok_a[-1] != "0" else "1")):
        r = client.post("/api/v1/checkin", json={**body, "qr_token": fake}, headers=_h(a))
        assert r.status_code == 403, (fake, r.text)
    assert _n(db, cid_a) == 0

    ok = client.post("/api/v1/checkin", json={**body, "qr_token": tok_a}, headers=_h(a))
    assert ok.status_code == 200, ok.text
    assert _n(db, cid_a) == 1


def test_otra_empresa_no_obtiene_el_qr(db):
    a, cid_a, _ = _seed(db, "a")
    b, _, _ = _seed(db, "b")
    r = TestClient(app).get(f"/api/v1/checkin/qr-token?company_id={cid_a}", headers=_h(b))
    assert r.status_code == 403
    assert TestClient(app).get("/api/v1/checkin/qr-token").status_code == 401
