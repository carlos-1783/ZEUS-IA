"""E2E zeus_total_system_closure_v1 — guard, superuser, financial, agents."""

from __future__ import annotations

import uuid

import pytest  # pyright: ignore[reportMissingImports]
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.company import Company, UserCompany
from app.models.user import User
from app.models.zeus_closure_audit import ZeusClosureAudit
from services.financial_integrity_v1 import assert_financial_record_valid
from services.user_service_v1 import secure_deactivate
from services.zeus_core_guard_v1 import (
    closure_active,
    guard_enforce,
    is_protected_user,
    validate_critical_action,
)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_superuser(db: Session) -> User:
    suf = uuid.uuid4().hex[:8]
    user = User(
        email=f"super_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name="Super User",
        is_active=True,
        is_superuser=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _seed_normal(db: Session):
    suf = uuid.uuid4().hex[:8]
    user = User(
        email=f"user_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name="Normal User",
        is_active=True,
    )
    company = Company(company_name=f"Guard Co {suf}", slug=f"guard-{suf}")
    db.add_all([user, company])
    db.flush()
    db.add(UserCompany(user_id=user.id, company_id=company.id, role="owner"))
    db.commit()
    db.refresh(user)
    db.refresh(company)
    return user, company


def test_flags_default_off():
    assert settings.ZEUS_TOTAL_SYSTEM_CLOSURE_ENABLED is False
    assert settings.ZEUS_CORE_GUARD_ENFORCE is False
    assert closure_active() is False
    assert guard_enforce() is False


def test_superuser_is_protected(db: Session):
    su = _seed_superuser(db)
    assert is_protected_user(su) is True


def test_guard_blocks_superuser_deactivate_when_enforce(db: Session, monkeypatch):
    monkeypatch.setattr(settings, "ZEUS_TOTAL_SYSTEM_CLOSURE_ENABLED", True)
    monkeypatch.setattr(settings, "ZEUS_CORE_GUARD_ENFORCE", True)
    su = _seed_superuser(db)

    gr = validate_critical_action(
        "users",
        "deactivate_user",
        target_user=su,
        db=db,
    )
    assert gr.allowed is False
    assert "superusuario" in gr.human_message.lower() or gr.reason == "protected_user_or_superuser"

    result = secure_deactivate(db, su, reason="test")
    assert result["executed"] is False
    assert su.is_active is True


def test_guard_allows_normal_user_deactivate_when_enforce(db: Session, monkeypatch):
    monkeypatch.setattr(settings, "ZEUS_TOTAL_SYSTEM_CLOSURE_ENABLED", True)
    monkeypatch.setattr(settings, "ZEUS_CORE_GUARD_ENFORCE", True)
    user, _ = _seed_normal(db)

    result = secure_deactivate(db, user, reason="test")
    assert result["executed"] is True
    assert user.is_active is False


def test_financial_requires_company_when_closure(db: Session, monkeypatch):
    monkeypatch.setattr(settings, "ZEUS_TOTAL_SYSTEM_CLOSURE_ENABLED", True)
    monkeypatch.setattr(settings, "ZEUS_CORE_GUARD_ENFORCE", True)

    fin = assert_financial_record_valid(db, company_id=None, amount=100.0)
    assert fin["blocked"] is True


def test_financial_ok_with_company(db: Session, monkeypatch):
    monkeypatch.setattr(settings, "ZEUS_TOTAL_SYSTEM_CLOSURE_ENABLED", True)
    monkeypatch.setattr(settings, "ZEUS_CORE_GUARD_ENFORCE", True)
    _, company = _seed_normal(db)

    fin = assert_financial_record_valid(db, company_id=company.id, amount=50.0)
    assert fin["valid"] is True
    assert fin["blocked"] is False


def test_closure_audit_persisted(db: Session, monkeypatch):
    monkeypatch.setattr(settings, "ZEUS_TOTAL_SYSTEM_CLOSURE_ENABLED", True)
    monkeypatch.setattr(settings, "ZEUS_CORE_GUARD_ENFORCE", False)
    su = _seed_superuser(db)

    validate_critical_action("users", "deactivate_user", target_user=su, db=db)
    db.commit()

    count = db.query(ZeusClosureAudit).count()
    assert count >= 1


def test_db_test_direct_superuser_deactivate_blocked_by_service(db: Session, monkeypatch):
    """db_test: mutación directa sustituida por user_service con guard."""
    monkeypatch.setattr(settings, "ZEUS_TOTAL_SYSTEM_CLOSURE_ENABLED", True)
    monkeypatch.setattr(settings, "ZEUS_CORE_GUARD_ENFORCE", True)
    su = _seed_superuser(db)

    result = secure_deactivate(db, su)
    assert result["executed"] is False
    db.refresh(su)
    assert su.is_active is True
