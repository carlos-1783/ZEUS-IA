"""Fase 2 / honestidad final #10 — el texto de las herramientas del workspace dice lo que paso.

Antes `_text_generic` devolvia siempre "completado correctamente. Resultado validado", tambien
con error o con real_execution=False.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints.workspaces import _text_generic
from app.core.auth import get_current_active_user
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.company import Company, UserCompany
from app.models.user import User


def test_texto_segun_resultado():
    assert _text_generic("X", {"real_execution": True}) == "X: ejecución real completada."
    falso = _text_generic("X", {"real_execution": False})
    assert "sin ejecución real" in falso and "correctamente" not in falso
    err = _text_generic("X", {"real_execution": False, "error": "boom", "message": "no hay motor"})
    assert err.startswith("X: no completado") and "no hay motor" in err
    assert "no completado" in _text_generic("X", {"success": False, "message": "m"})
    assert "no indica" in _text_generic("X", {})
    for r in ({}, {"real_execution": False}, {"error": "e"}):
        assert "Resultado validado" not in _text_generic("X", r)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def test_gdpr_workspace_texto_real(db):
    suf = uuid.uuid4().hex[:8]
    c = Company(company_name=f"Txt {suf}", slug=f"txt-{suf}")
    u = User(email=f"txt_{suf}@example.test", hashed_password=get_password_hash("TestPass1"), is_active=True)
    db.add_all([c, u])
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    db.commit()
    db.refresh(u)
    app.dependency_overrides[get_current_active_user] = lambda: u
    try:
        r = TestClient(app).post("/api/v1/workspaces/justicia/gdpr-audit", json={"systems": ["crm"]})
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["result"].get("real_execution") is True
    assert body["text"] == "Auditoría GDPR: ejecución real completada."
