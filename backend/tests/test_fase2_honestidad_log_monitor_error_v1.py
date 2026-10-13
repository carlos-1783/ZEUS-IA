"""Fase 2 / honestidad final #23 — log-monitor: si el escaneo real falla ya no se traga el error
(`except: pass`): queda en log (logger.exception), en la respuesta y en el texto, y el badge
deja de decir REAL."""

from __future__ import annotations

import asyncio
import logging
import uuid

import pytest

from app.api.v1.endpoints.workspaces import ThalosLogRequest, workspace_thalos_logs
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.company import Company, UserCompany
from app.models.user import User
import services.thalos_security_engine as engine_mod


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _admin(db):
    suf = uuid.uuid4().hex[:8]
    u = User(email=f"lm_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
             is_active=True, is_superuser=True)
    c = Company(company_name=f"LM {suf}", slug=f"lm-{suf}")
    db.add_all([u, c])
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    db.commit()
    db.refresh(u)
    return u


def test_fallo_del_escaneo_real_se_reporta(db, monkeypatch, caplog):
    admin = _admin(db)

    def _boom(*a, **k):
        raise RuntimeError("motor de logs caido")

    monkeypatch.setattr(engine_mod, "scan_logs", _boom)
    with caplog.at_level(logging.ERROR):
        out = asyncio.run(workspace_thalos_logs(ThalosLogRequest(logs=[]), current_user=admin, db=db))
    assert out["result"]["real_scan_error"] == "RuntimeError: motor de logs caido"
    assert "El escaneo real de logs falló" in out["text"]
    assert out["real_execution"] is False
    assert out["thalos_control"]["ui_badge"] != "REAL"
    assert any("fallo el escaneo real" in r.getMessage() for r in caplog.records)


def test_escaneo_real_ok(db):
    admin = _admin(db)
    out = asyncio.run(workspace_thalos_logs(ThalosLogRequest(logs=[]), current_user=admin, db=db))
    assert out["real_execution"] is True and "real_scan_error" not in out["result"]
    assert out["thalos_control"]["ui_badge"] == "REAL"
    assert "Escaneo real de logs" in out["text"]
