"""Tests thalos_safe_audit_v1 — flags, engine, executor (non-destructive)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest  # pyright: ignore[reportMissingImports]
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.agent_activity import AgentActivity
from app.models.cashflow_ledger import CashflowLedgerEntry
from app.models.company import Company, UserCompany
from app.models.thalos_security_event import ThalosLoginAttempt
from app.models.user import User
from services import thalos_executor, thalos_security_engine
from services.thalos_monitoring_service import run_monitoring_cycle


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
        email=f"thalos_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name="Thalos Tester",
        is_active=True,
    )
    company = Company(company_name=f"Thalos Co {suf}", slug=f"thalos-{suf}")
    db.add_all([user, company])
    db.flush()
    db.add(UserCompany(user_id=user.id, company_id=company.id, role="owner"))
    db.commit()
    return user, company


def test_executor_disabled_by_default(db: Session):
    assert settings.THALOS_EXECUTION_ENABLED is False
    result = thalos_executor.execute_action(db, "detect_suspicious_activity")
    assert result["status"] == "skipped"
    assert result["executed"] is False


def test_scan_logs_detects_suspicious_activity(db: Session):
    db.add(
        AgentActivity(
            agent_name="THALOS",
            action_type="auth_check",
            action_description="failed login attempt from 10.0.0.1",
            details={"ip": "10.0.0.1"},
            status="failed",
        )
    )
    db.commit()

    scan = thalos_security_engine.scan_logs(db, hours=24)
    assert scan["pattern_alerts"]
    assert scan["risk_level"] in ("high", "critical", "ok")


def test_failed_login_rule_triggers_block_candidate(db: Session):
    email = f"brute_{uuid.uuid4().hex[:6]}@evil.test"
    now = datetime.now(timezone.utc)
    for _ in range(6):
        db.add(
            ThalosLoginAttempt(
                email=email,
                ip_address="203.0.113.9",
                success=0,
                created_at=now - timedelta(minutes=5),
            )
        )
    db.commit()

    rules = thalos_security_engine.evaluate_decision_rules(db, user_email=email)
    block_rules = [r for r in rules if r.get("action") == "block_user"]
    assert block_rules
    assert block_rules[0]["priority"] == "critical"


def test_block_user_dry_run_without_auto_block(db: Session, monkeypatch):
    monkeypatch.setattr(settings, "THALOS_EXECUTION_ENABLED", True)
    monkeypatch.setattr(settings, "THALOS_AUTO_BLOCK", False)

    user, _ = _seed_company(db)
    result = thalos_executor.block_user(db, user_email=user.email)
    assert result["status"] == "dry_run"
    db.refresh(user)
    assert user.is_active is True


def test_block_user_respects_protected_email(db: Session, monkeypatch):
    monkeypatch.setattr(settings, "THALOS_EXECUTION_ENABLED", True)
    monkeypatch.setattr(settings, "THALOS_AUTO_BLOCK", True)

    result = thalos_executor.block_user(db, user_email="admin")
    assert result["status"] == "blocked_by_safeguard"
    assert result["executed"] is False


def test_cashflow_anomaly_detection(db: Session):
    _, company = _seed_company(db)
    for amount in [50.0, 55.0, 48.0, 52.0, 5000.0]:
        db.add(
            CashflowLedgerEntry(
                company_id=company.id,
                amount=amount,
                direction="in",
                source="test",
            )
        )
    db.commit()

    result = thalos_security_engine.detect_cashflow_anomaly(db, company_id=company.id)
    assert result["anomaly"] is True
    assert result["suspicious_entries"]


def test_monitoring_cycle_respects_flags(db: Session, monkeypatch):
    monkeypatch.setattr(settings, "THALOS_REAL_MONITORING", False)
    monkeypatch.setattr(settings, "THALOS_EXECUTION_ENABLED", False)

    cycle = run_monitoring_cycle(db)
    assert cycle["monitoring_enabled"] is False
    assert cycle["scan"].get("status") == "monitoring_disabled" or "note" in cycle["scan"]
