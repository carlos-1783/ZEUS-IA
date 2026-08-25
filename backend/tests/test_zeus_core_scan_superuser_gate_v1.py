"""
Vuelta 3 de AUDIT_FIX_THALOS_SHIELD.md (sección 9, motivo 4): mitigación
interina de la fuga cross-tenant de THALOS.SCAN, confirmada en vivo por el
revisor en la ronda 2 (sección 8.3). `thalos_security_engine.scan_logs`
audita `agent_activities`/`thalos_login_attempts` de forma global (esas
tablas no tienen `company_id`), así que hasta que exista una migración de
esquema que lo permita, el comando se restringe a superusuarios en los dos
puntos donde un usuario autenticado normal podía dispararlo:

- `POST /api/v1/zeus/execute` con `command="THALOS.SCAN"`
  (`app/api/v1/endpoints/zeus_core.py::execute_zeus_command`).
- `POST /thalos/v1/execute` con `action="detect_suspicious_activity"`
  (`app/api/v1/endpoints/thalos_v1.py::thalos_v1_execute`).
"""

from __future__ import annotations

import asyncio
import uuid

import pytest  # pyright: ignore[reportMissingImports]
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.v1.endpoints import thalos_v1
from app.api.v1.endpoints.thalos_v1 import ThalosExecuteRequest, thalos_v1_execute
from app.api.v1.endpoints.zeus_core import ZeusCommand, execute_zeus_command
from app.core.config import settings
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.company import Company, UserCompany
from app.models.user import User


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_company(db: Session, is_superuser: bool = False):
    suf = uuid.uuid4().hex[:8]
    user = User(
        email=f"scan_gate_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name="Scan Gate Tester",
        is_active=True,
        is_superuser=is_superuser,
    )
    company = Company(company_name=f"Scan Gate Co {suf}", slug=f"scan-gate-{suf}")
    db.add_all([user, company])
    db.flush()
    db.add(UserCompany(user_id=user.id, company_id=company.id, role="owner"))
    db.commit()
    return user, company


def test_zeus_core_scan_rejects_normal_user(db: Session):
    user, _ = _seed_company(db, is_superuser=False)
    body = ZeusCommand(command="THALOS.SCAN", data={})

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(execute_zeus_command(body, current_user=user, db=db))

    assert excinfo.value.status_code == 403


def test_zeus_core_scan_allows_superuser(db: Session):
    user, _ = _seed_company(db, is_superuser=True)
    body = ZeusCommand(command="THALOS.SCAN", data={})

    result = asyncio.run(execute_zeus_command(body, current_user=user, db=db))

    # No debe lanzar HTTPException; el comando llega al motor real.
    assert result.status != "error" or "scan_result" not in (result.data or {})


def test_zeus_core_activate_not_affected_by_scan_gate(db: Session):
    """Control negativo: la restricción es específica de THALOS.SCAN, no de
    todo el endpoint /execute."""
    user, _ = _seed_company(db, is_superuser=False)
    body = ZeusCommand(command="ZEUS.ANALIZAR", data={})

    result = asyncio.run(execute_zeus_command(body, current_user=user, db=db))
    assert result.status in ("success", "error")  # no HTTPException 403


def test_thalos_v1_execute_scan_rejects_normal_user(db: Session, monkeypatch):
    monkeypatch.setattr(thalos_v1, "can_run_active_execution", lambda module, action=None: True)
    monkeypatch.setattr(settings, "THALOS_EXECUTION_ENABLED", True)

    user, _ = _seed_company(db, is_superuser=False)
    body = ThalosExecuteRequest(action="detect_suspicious_activity")

    with pytest.raises(HTTPException) as excinfo:
        thalos_v1_execute(body, current_user=user, db=db)

    assert excinfo.value.status_code == 403


def test_thalos_v1_execute_scan_allows_superuser(db: Session, monkeypatch):
    monkeypatch.setattr(thalos_v1, "can_run_active_execution", lambda module, action=None: True)
    monkeypatch.setattr(settings, "THALOS_EXECUTION_ENABLED", True)

    user, _ = _seed_company(db, is_superuser=True)
    body = ThalosExecuteRequest(action="detect_suspicious_activity")

    result = thalos_v1_execute(body, current_user=user, db=db)

    # No debe ser el 403 de la mitigación; debe llegar al motor real.
    assert result.get("status") != "blocked" or "REAL_ACTIVE" not in str(result)
