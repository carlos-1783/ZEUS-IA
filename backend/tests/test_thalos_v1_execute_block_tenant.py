"""
Regresión del hallazgo ALTO de AUDIT_FIX_THALOS_SHIELD.md (sección 6, ronda 1):
THALOS.BLOCK (`services/thalos_executor.py::block_user`) no validaba que
`user_email` (el usuario a bloquear) perteneciera al `company_id` del
solicitante. Estos tests cubren la vía REST oficial
(`app/api/v1/endpoints/thalos_v1.py::thalos_v1_execute`), que debe traducir
el `status="forbidden"` de `block_user` en un 403 real (mismo estilo que
`services/tpv_service.py:1068`, "La venta no pertenece a su empresa.").

`can_run_active_execution` se monkeypatchea a `True` porque, con la
clasificación actual de módulos (`MODULE_CLASSIFICATION["auditoria_real"] =
"REAL_SAFE"`), `block_user` nunca alcanza `REAL_ACTIVE` por configuración de
producto (ver hallazgo declarado en AUDIT_FIX_THALOS_SHIELD.md sección 7) --
así se prueba de forma aislada el comportamiento de aislamiento multi-tenant
en sí, sin depender de esa configuración por ahora inalcanzable en este
entorno.
"""

from __future__ import annotations

import uuid

import pytest  # pyright: ignore[reportMissingImports]
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.v1.endpoints import thalos_v1
from app.api.v1.endpoints.thalos_v1 import ThalosExecuteRequest, thalos_v1_execute
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


def _seed_company(db: Session):
    suf = uuid.uuid4().hex[:8]
    user = User(
        email=f"thalos_v1_exec_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name="Thalos V1 Execute Tester",
        is_active=True,
    )
    company = Company(company_name=f"Thalos V1 Execute Co {suf}", slug=f"thalos-v1-exec-{suf}")
    db.add_all([user, company])
    db.flush()
    db.add(UserCompany(user_id=user.id, company_id=company.id, role="owner"))
    db.commit()
    return user, company


def test_thalos_v1_execute_block_user_cross_tenant_returns_403(db: Session, monkeypatch):
    monkeypatch.setattr(thalos_v1, "can_run_active_execution", lambda module, action=None: True)
    monkeypatch.setattr(settings, "THALOS_EXECUTION_ENABLED", True)
    monkeypatch.setattr(settings, "THALOS_AUTO_BLOCK", True)

    requester, company_a = _seed_company(db)
    victim, company_b = _seed_company(db)

    body = ThalosExecuteRequest(action="block_user", user_email=victim.email)

    with pytest.raises(HTTPException) as excinfo:
        thalos_v1_execute(body, current_user=requester, db=db)

    assert excinfo.value.status_code == 403

    db.refresh(victim)
    assert victim.is_active is True


def test_thalos_v1_execute_block_user_same_tenant_not_forbidden(db: Session, monkeypatch):
    """Control negativo: mismo tenant no debe disparar el 403 de aislamiento
    (puede seguir bloqueado/skipped por otras razones reales, pero no por
    `forbidden`)."""
    monkeypatch.setattr(thalos_v1, "can_run_active_execution", lambda module, action=None: True)
    monkeypatch.setattr(settings, "THALOS_EXECUTION_ENABLED", True)
    monkeypatch.setattr(settings, "THALOS_AUTO_BLOCK", False)

    requester, company_a = _seed_company(db)
    teammate = User(
        email=f"thalos_v1_teammate_{uuid.uuid4().hex[:8]}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name="Teammate",
        is_active=True,
    )
    db.add(teammate)
    db.flush()
    db.add(UserCompany(user_id=teammate.id, company_id=company_a.id, role="member"))
    db.commit()

    body = ThalosExecuteRequest(action="block_user", user_email=teammate.email)
    result = thalos_v1_execute(body, current_user=requester, db=db)

    assert result["status"] != "forbidden"
    assert result["executed"] is False  # dry_run: THALOS_AUTO_BLOCK=False

    db.refresh(teammate)
    assert teammate.is_active is True
