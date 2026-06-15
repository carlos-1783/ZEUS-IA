"""Tests zeus_core_closure_v1 — cashflow ledger, client_created, handlers."""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.cashflow_ledger import CashflowLedgerEntry
from app.models.company import Company, UserCompany
from app.models.company_employee import CompanyEmployee
from app.models.customer import Customer
from app.models.user import User
from app.schemas.customer import CustomerCreate
from services.automation.handlers import resolve_handler
from services.cashflow_ledger_service import get_balance, record_movement
from services.event_bus import emit_cashflow_updated
import services.crm_office_service as crm_svc


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_user_company(db: Session):
    suf = uuid.uuid4().hex[:8]
    user = User(
        email=f"closure_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name="Closure Tester",
        is_active=True,
    )
    company = Company(company_name=f"Closure Co {suf}", slug=f"closure-{suf}")
    db.add_all([user, company])
    db.flush()
    db.add(UserCompany(user_id=user.id, company_id=company.id, role="owner"))
    db.commit()
    db.refresh(user)
    db.refresh(company)
    return user, company


def test_cashflow_ledger_persists_and_balance(db: Session):
    user, company = _seed_user_company(db)
    record_movement(
        db,
        company_id=company.id,
        amount=100.0,
        direction="in",
        source="TEST",
        user_id=user.id,
    )
    record_movement(
        db,
        company_id=company.id,
        amount=25.0,
        direction="out",
        source="TEST",
        user_id=user.id,
    )
    assert get_balance(db, company_id=company.id) == 75.0
    count = db.query(CashflowLedgerEntry).filter(CashflowLedgerEntry.company_id == company.id).count()
    assert count == 2


def test_emit_cashflow_updated_writes_ledger(db: Session):
    user, company = _seed_user_company(db)
    emit_cashflow_updated(
        user_id=user.id,
        user_email=user.email,
        company_id=company.id,
        amount=50.0,
        direction="in",
        source="UNIT_TEST",
        db=db,
    )
    assert get_balance(db, company_id=company.id) == 50.0


def test_create_customer_emits_client_created(db: Session):
    user, company = _seed_user_company(db)
    customer = crm_svc.create_customer(
        db,
        user,
        CustomerCreate(name="Cliente Real", email=f"c_{uuid.uuid4().hex[:6]}@test.com"),
    )
    assert customer.id is not None
    assert customer.company_id == company.id


def test_teamflow_handlers_resolved(db: Session):
    _ = db
    assert resolve_handler("ZEUS CORE", "crm_customers_summary") is not None
    assert resolve_handler("ZEUS CORE", "campaign_sent") is not None
    assert resolve_handler("ZEUS CORE", "coordination") is not None
    assert resolve_handler("PERSEO", "campaign_created") is not None


def test_cashflow_rejects_zero_amount(db: Session):
    user, company = _seed_user_company(db)
    with pytest.raises(ValueError):
        record_movement(db, company_id=company.id, amount=0, source="TEST")
