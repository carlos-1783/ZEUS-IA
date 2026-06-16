"""E2E zeus_final_closure_v2 — sales, checkin, lead flows."""

from __future__ import annotations

import uuid

import pytest  # pyright: ignore[reportMissingImports]
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.cashflow_ledger import CashflowLedgerEntry
from app.models.company import Company, UserCompany
from app.models.user import User
from app.schemas.customer import CustomerCreate
from services.cashflow_ledger_service import get_balance, record_movement
from services.zeus_human_approval_v1 import requires_approval, resolve_approval
from services.zeus_scoring_engine_v1 import convert_lead_to_customer, create_lead, score_lead
from services.zeus_core_metrics_v1 import get_core_metrics
import services.crm_office_service as crm_svc
from services.time_cost_engine_v1 import register_checkin, refresh_partial_costs
from app.models.company_employee import CompanyEmployee


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed(db: Session):
    suf = uuid.uuid4().hex[:8]
    user = User(
        email=f"v2_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name="V2 Tester",
        is_active=True,
    )
    company = Company(company_name=f"V2 Co {suf}", slug=f"v2-{suf}")
    db.add_all([user, company])
    db.flush()
    db.add(UserCompany(user_id=user.id, company_id=company.id, role="owner"))
    emp = CompanyEmployee(
        company_id=company.id,
        full_name="Worker",
        employee_code="W001",
        hourly_rate=25.0,
        is_active=True,
    )
    db.add(emp)
    db.commit()
    db.refresh(user)
    db.refresh(company)
    db.refresh(emp)
    return user, company, emp


def test_full_sales_flow_cashflow(db: Session):
    user, company, _ = _seed(db)
    cust = crm_svc.create_customer(
        db, user, CustomerCreate(name="Buyer SA", email=f"buyer_{uuid.uuid4().hex[:6]}@test.com")
    )
    assert cust.id
    record_movement(
        db,
        company_id=company.id,
        amount=120.0,
        direction="in",
        source="TEST_SALE",
        user_id=user.id,
        customer_id=cust.id,
    )
    assert get_balance(db, company_id=company.id) == 120.0
    assert db.query(CashflowLedgerEntry).filter(CashflowLedgerEntry.company_id == company.id).count() >= 1
    metrics = get_core_metrics(db, user=user)
    assert "revenue" in metrics
    assert "staff_cost" in metrics


def test_checkin_cost_flow(db: Session):
    user, company, emp = _seed(db)
    entrada = register_checkin(
        db,
        user=user,
        company_id=company.id,
        employee_id=emp.employee_code,
        checkin_type="entrada",
        method="qr",
        metadata={"qr_token": "e2e"},
    )
    assert entrada["session_id"]
    refresh_partial_costs(db, company_id=company.id)
    salida = register_checkin(
        db,
        user=user,
        company_id=company.id,
        employee_id=emp.employee_code,
        checkin_type="salida",
        method="device",
        metadata={"device_id": "e2e"},
    )
    assert salida["session_status"] == "closed"
    assert salida.get("cost_eur") is not None


def test_lead_to_customer_flow(db: Session):
    user, company, _ = _seed(db)
    lead = create_lead(
        db,
        user=user,
        name="Prospect SL",
        email=f"lead_{uuid.uuid4().hex[:6]}@test.com",
        estimated_value=5000.0,
    )
    scored = score_lead(db, user=user, lead_id=lead.id)
    assert scored["lead_score"] is not None
    from services.zeus_agenda_optimizer_v1 import propose_meeting_slots, schedule_meeting

    slots = propose_meeting_slots(db, user=user, lead_id=lead.id)
    assert slots["proposed_slots"]
    scheduled = schedule_meeting(
        db, user=user, lead_id=lead.id, start_iso=slots["proposed_slots"][0]["start"]
    )
    assert scheduled["scheduled"] is True
    converted = convert_lead_to_customer(db, user=user, lead_id=lead.id)
    assert converted["customer_id"]


def test_human_approval_gate(db: Session):
    user, company, _ = _seed(db)
    assert requires_approval("send_campaign") is True
    assert requires_approval("get_metrics") is False
