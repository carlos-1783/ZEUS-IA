"""E2E zeus_full_real_flow_v3 — QR, DNI, NFC scan pipelines."""

from __future__ import annotations

import uuid

import pytest  # pyright: ignore[reportMissingImports]
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.cashflow_ledger import CashflowLedgerEntry
from app.models.company import Company, UserCompany
from app.models.company_employee import CompanyEmployee
from app.models.customer import Customer
from app.models.erp import Invoice
from app.models.scan_event import ScanEvent
from app.models.user import User
from services.cashflow_ledger_service import get_balance
from services.mrz_parser_v1 import parse_mrz
from services.scan_flow_service_v1 import process_dni_scan, process_nfc_scan, process_qr_scan

# MRZ TD1 ICAO test vector (checksums válidos)
SAMPLE_MRZ = """I<UTOD231458907<<<<<<<
7408122F1204159UTO<<<<<<<<<<<6
ERIKSSON<<ANNA<MARIA<<<<<<<<<<"""


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
        email=f"scan_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name="Scan Tester",
        is_active=True,
    )
    company = Company(company_name=f"Scan Co {suf}", slug=f"scan-{suf}")
    db.add_all([user, company])
    db.flush()
    db.add(UserCompany(user_id=user.id, company_id=company.id, role="owner"))
    emp = CompanyEmployee(
        company_id=company.id,
        full_name="Worker NFC",
        employee_code="W001",
        hourly_rate=20.0,
        is_active=True,
    )
    db.add(emp)
    db.commit()
    db.refresh(user)
    db.refresh(company)
    db.refresh(emp)
    return user, company, emp


def test_mrz_parser_checksums():
    parsed = parse_mrz(SAMPLE_MRZ)
    assert parsed["document_number"] == "D23145890"
    assert parsed["full_name"]


def test_qr_to_invoice(db: Session):
    user, company, _ = _seed(db)
    email = f"qr_buyer_{uuid.uuid4().hex[:6]}@test.com"
    qr = f"ZEUS|QR Buyer|120.00|EUR|{email}"
    out = process_qr_scan(db, user, data=qr, company_id=company.id)
    assert out["executed"] is True
    assert out["invoice_id"]
    assert out["cashflow_updated"] is True
    assert db.query(ScanEvent).filter(ScanEvent.scan_type == "qr").count() >= 1
    assert db.query(Invoice).filter(Invoice.id == out["invoice_id"]).count() == 1
    assert get_balance(db, company_id=company.id) == 120.0


def test_dni_to_customer(db: Session):
    user, company, _ = _seed(db)
    out = process_dni_scan(db, user, mrz=SAMPLE_MRZ, company_id=company.id)
    assert out["executed"] is True
    assert out["customer_id"]
    assert out["lead_score"] is not None
    assert db.query(Customer).filter(Customer.id == out["customer_id"]).count() == 1
    assert db.query(ScanEvent).filter(ScanEvent.scan_type == "dni").count() >= 1


def test_nfc_to_checkin(db: Session):
    user, company, emp = _seed(db)
    token = f"ZEUSCHECK|{emp.employee_code}|2026-05-29T10:00:00Z"
    entrada = process_nfc_scan(db, user, text=token, company_id=company.id, checkin_type="entrada")
    assert entrada["executed"] is True
    assert entrada["session"]
    salida = process_nfc_scan(db, user, text=token, company_id=company.id, checkin_type="salida")
    assert salida["executed"] is True
    assert db.query(ScanEvent).filter(ScanEvent.scan_type == "nfc").count() >= 2
