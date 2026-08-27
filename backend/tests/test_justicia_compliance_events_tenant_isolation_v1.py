"""
Hallazgo descubierto durante el cierre de "toolkit legal = stub"
(AUDIT_JUSTICIA_ESTADO_FINAL.md): `GET /api/v1/justice/status` y
`GET /api/v1/justice/audit` exponían el COUNT crudo y global de
`compliance_events` a CUALQUIER usuario autenticado, aunque esa tabla no
tiene company_id/user_id (agrega ThalosAlert/CompanyEmployee/PerseoJob/
Expense de TODAS las empresas). Confirmado empíricamente con dos tenants
reales vía curl: el tenant B veía `compliance_events: 2` generado
exclusivamente por acciones del tenant A.

El listado completo (`GET /api/v1/justice/compliance-events`) ya estaba
gateado a superusuario (AUDIT_THALOS_ESTRUCTURAL.md, sección 3); este test
cierra el mismo hueco para el COUNT agregado que `audit_status`/
`run_real_audit` seguían exponiendo sin gate.
"""

from __future__ import annotations

import uuid

import pytest  # pyright: ignore[reportMissingImports]
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.compliance_event import ComplianceEvent
from app.models.user import User
from services.justice_audit_service import audit_status, run_real_audit


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_user(db: Session, *, is_superuser: bool = False) -> User:
    suf = uuid.uuid4().hex[:8]
    user = User(
        email=f"compliance_iso_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name="Compliance Isolation Tester",
        is_active=True,
        is_superuser=is_superuser,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_audit_status_hides_global_compliance_count_from_normal_user(db: Session):
    db.add(ComplianceEvent(event_type="security_alert", severity="high", source="THALOS"))
    db.commit()

    normal_user = _seed_user(db, is_superuser=False)
    body = audit_status(db, normal_user)

    assert body["compliance_events"] is None
    assert "compliance_events_note" in body
    assert "superusuario" in body["compliance_events_note"]


def test_audit_status_shows_real_compliance_count_to_superuser(db: Session):
    db.add(ComplianceEvent(event_type="security_alert", severity="high", source="THALOS"))
    db.commit()

    admin = _seed_user(db, is_superuser=True)
    body = audit_status(db, admin)

    assert isinstance(body["compliance_events"], int)
    assert body["compliance_events"] >= 1
    assert "compliance_events_note" not in body


def test_run_real_audit_hides_global_compliance_count_from_normal_user(monkeypatch, db: Session):
    from app.core.config import settings

    monkeypatch.setattr(settings, "JUSTICE_REAL_AUDIT_ENABLED", True, raising=False)

    db.add(ComplianceEvent(event_type="security_alert", severity="high", source="THALOS"))
    db.commit()

    normal_user = _seed_user(db, is_superuser=False)
    result = run_real_audit(db, normal_user)

    assert result["success"] is True
    assert result["compliance_events_count"] is None
    assert "compliance_events_note" in result
