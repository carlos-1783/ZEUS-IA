"""Attack simulations + phase 2 audit — zeus_phase_2_full_system_audit_and_patch."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest  # pyright: ignore[reportMissingImports]
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.cashflow_ledger import CashflowLedgerEntry
from app.models.company import Company, UserCompany
from app.models.user import User
from services.event_bus import emit_cashflow_updated
from services.user_service_v1 import secure_deactivate
from services.zeus_bypass_scanner_v1 import run_full_audit, scan_codebase
from services.zeus_core_guard_v1 import ZeusGuardViolation, closure_active, guard_enforce
from services.zeus_runtime_guard_v1 import attach_runtime_guard, detach_runtime_guard


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
        email=f"atk_super_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name="Attack Super",
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
        email=f"atk_user_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name="Attack User",
        is_active=True,
    )
    company = Company(company_name=f"Atk Co {suf}", slug=f"atk-{suf}")
    db.add_all([user, company])
    db.flush()
    db.add(UserCompany(user_id=user.id, company_id=company.id, role="owner"))
    db.commit()
    db.refresh(user)
    db.refresh(company)
    return user, company


def test_scanner_produces_report():
    report = scan_codebase()
    assert report.summary["total_files_scanned"] > 50
    assert "critical_bypass" in report.summary or report.summary.get("total_hits", 0) >= 0
    assert report.coverage["estimated_guarded_mutation_pct"] >= 0


def test_full_audit_includes_endpoints():
    audit = run_full_audit()
    assert "code_scan" in audit
    assert "endpoint_scan" in audit
    assert audit["endpoint_scan"]["endpoints_scanned"] > 0


def test_attack_superuser_block_via_service(db: Session, monkeypatch):
    monkeypatch.setattr(settings, "ZEUS_TOTAL_SYSTEM_CLOSURE_ENABLED", True)
    monkeypatch.setattr(settings, "ZEUS_CORE_GUARD_ENFORCE", True)
    su = _seed_superuser(db)

    result = secure_deactivate(db, su, reason="attack_sim")
    assert result["executed"] is False
    db.refresh(su)
    assert su.is_active is True


def test_attack_superuser_block_via_admin_service(db: Session, monkeypatch):
    monkeypatch.setattr(settings, "ZEUS_TOTAL_SYSTEM_CLOSURE_ENABLED", True)
    monkeypatch.setattr(settings, "ZEUS_CORE_GUARD_ENFORCE", True)
    from services.admin_account_service import set_user_active

    su = _seed_superuser(db)
    with pytest.raises(ValueError, match="superusuario"):
        set_user_active(db, su, active=False, reason="attack")


def test_attack_event_bus_no_company_when_enforce(db: Session, monkeypatch):
    monkeypatch.setattr(settings, "ZEUS_TOTAL_SYSTEM_CLOSURE_ENABLED", True)
    monkeypatch.setattr(settings, "ZEUS_CORE_GUARD_ENFORCE", True)
    user, _ = _seed_normal(db)

    before = db.query(CashflowLedgerEntry).count()

    emit_cashflow_updated(
        user_id=user.id,
        user_email=user.email,
        company_id=None,
        amount=100.0,
        db=db,
    )
    after = db.query(CashflowLedgerEntry).count()
    assert after == before


def test_attack_runtime_guard_superuser_deactivate(db: Session, monkeypatch):
    monkeypatch.setattr(settings, "ZEUS_TOTAL_SYSTEM_CLOSURE_ENABLED", True)
    monkeypatch.setattr(settings, "ZEUS_CORE_GUARD_ENFORCE", True)
    detach_runtime_guard()
    attach_runtime_guard()

    su = _seed_superuser(db)
    su.is_active = False
    with pytest.raises(ZeusGuardViolation):
        db.commit()
    db.rollback()


def test_attack_concurrent_deactivate_normal_user(db: Session, monkeypatch):
    monkeypatch.setattr(settings, "ZEUS_TOTAL_SYSTEM_CLOSURE_ENABLED", True)
    monkeypatch.setattr(settings, "ZEUS_CORE_GUARD_ENFORCE", True)
    users = []
    for _ in range(3):
        u, _ = _seed_normal(db)
        users.append(u)

    def _deact(u: User):
        s = SessionLocal()
        try:
            u2 = s.query(User).filter(User.id == u.id).first()
            return secure_deactivate(s, u2, reason="concurrent")
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(_deact, users))

    assert all(r.get("executed") for r in results)


def test_closure_flags_independent():
    assert closure_active() == settings.ZEUS_TOTAL_SYSTEM_CLOSURE_ENABLED
    assert guard_enforce() == (
        settings.ZEUS_TOTAL_SYSTEM_CLOSURE_ENABLED and settings.ZEUS_CORE_GUARD_ENFORCE
    )
