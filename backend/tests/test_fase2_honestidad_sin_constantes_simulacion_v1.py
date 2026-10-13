"""Fase 2 / honestidad final #24 — sin constantes simulation_detected/simulation_allowed=False
que afirmaban algo que nadie comprobaba."""

from __future__ import annotations

import uuid

import pytest

from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.user import User
from services.thalos_monitor_service import audit_from_db


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def test_audit_from_db_sin_constante(db):
    out = audit_from_db(db)
    assert "simulation_detected" not in out and out["data_origin"] == "database"


def test_run_real_audit_sin_constante(db, monkeypatch):
    from app.core.config import settings
    from services.justice_audit_service import run_real_audit

    monkeypatch.setattr(settings, "JUSTICE_REAL_AUDIT_ENABLED", True, raising=False)
    suf = uuid.uuid4().hex[:8]
    u = User(email=f"sc_{suf}@example.test", hashed_password=get_password_hash("TestPass1"), is_active=True)
    db.add(u)
    db.commit()
    db.refresh(u)
    out = run_real_audit(db, u)
    assert out["success"] is True and "simulation_detected" not in out


def test_endpoint_thalos_audit_sin_constante():
    import inspect

    from app.api.v1.endpoints import thalos

    assert "simulation_allowed" not in inspect.getsource(thalos.thalos_audit)
