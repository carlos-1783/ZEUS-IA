"""Fase 2 / vertical hosteleria — perfil y config del Control Horario sin estado global.

El singleton control_horario_service guardaba business_profile/config del proceso: la
config de la ultima empresa que hacia una peticion aparecia en la respuesta de otra.
Ahora se calculan por peticion desde BD; con peticiones intercaladas cada empresa ve
solo lo suyo y el singleton no guarda nada.
"""

from __future__ import annotations

import copy
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.company import Company, UserCompany
from app.models.user import User
from services.control_horario_service import ControlHorarioService, HorarioBusinessProfile
from services.control_horario_singleton import control_horario_service

P = "/api/v1/control-horario"


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _seed(db, tag, profile):
    suf = uuid.uuid4().hex[:8]
    c = Company(company_name=f"PF {tag} {suf}", slug=f"pf-{tag}-{suf}")
    u = User(email=f"pf_{tag}_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
             full_name=tag, is_active=True, control_horario_business_profile=profile)
    db.add_all([c, u])
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    db.commit()
    db.refresh(u)
    return u


def _h(u):
    return {"Authorization": f"Bearer {create_access_token({'sub': u.email, 'email': u.email})}"}


def _expected(profile: str):
    cfg = copy.deepcopy(ControlHorarioService().get_business_config(HorarioBusinessProfile(profile)))
    cfg["methods_enabled"] = [m for m in cfg["methods_enabled"] if m != "face"]
    return cfg


def _check(resp_json, profile):
    body = resp_json.get("info", resp_json)
    assert body["business_profile"] == profile, body["business_profile"]
    assert body["config"] == _expected(profile)


def test_peticiones_intercaladas_no_mezclan_config(db):
    a = _seed(db, "a", "restaurante")
    b = _seed(db, "b", "remoto")
    client = TestClient(app)
    ha, hb = _h(a), _h(b)

    for _ in range(2):
        _check(client.get(P, headers=ha).json(), "restaurante")
        _check(client.get(P, headers=hb).json(), "remoto")
        _check(client.get(f"{P}/status", headers=ha).json(), "restaurante")
        _check(client.get(f"{P}/bootstrap", headers=hb).json(), "remoto")
        _check(client.get(f"{P}/bootstrap", headers=ha).json(), "restaurante")
        _check(client.get(f"{P}/status", headers=hb).json(), "remoto")

    # A cambia su perfil: B no se entera; A si.
    r = client.post(f"{P}/set-business-profile", json={"business_profile": "logística"}, headers=ha)
    assert r.status_code == 200, r.text
    assert r.json()["config"] == _expected("logística")
    _check(client.get(f"{P}/status", headers=hb).json(), "remoto")
    _check(client.get(f"{P}/status", headers=ha).json(), "logística")

    # El singleton no guarda perfil ni config de nadie.
    assert control_horario_service.business_profile is None
    assert control_horario_service.config == {}
