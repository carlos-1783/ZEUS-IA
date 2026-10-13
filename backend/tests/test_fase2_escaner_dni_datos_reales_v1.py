"""Fase 2: el escaner MRZ de DNI guarda datos REALES del documento, sin inventar nada.

- Nombre ICAO: APELLIDOS<<NOMBRE (dos apellidos bien partidos).
- NIF = numero de DNI/NIE validado de los datos opcionales (no el numero de soporte).
- Sin email real NO se crea el cliente: 422 pidiendo el email (antes: scan+xxxx@example.com inventado).
- Un DNI es persona fisica (is_company False).
- Aislamiento: el cliente queda en la empresa del usuario.
"""

from __future__ import annotations

import uuid

import pytest

from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.company import Company, UserCompany
from app.models.customer import Customer
from app.models.user import User
from services.mrz_parser_v1 import _check_digit, parse_mrz
from services.scan_flow_service_v1 import process_dni_scan


def _td1(support="CRV123456", dni="12345678Z", surname="GARCIA<LOPEZ", given="PABLO"):
    l1 = ("IDESP" + support + _check_digit(support) + dni).ljust(30, "<")
    birth, exp = "900101", "300101"
    l2 = birth + _check_digit(birth) + "M" + exp + _check_digit(exp) + "ESP"
    l2 = l2.ljust(29, "<")
    composite = l1[5:30] + l2[0:7] + l2[8:15] + l2[18:29]
    l2 = l2 + _check_digit(composite)
    l3 = (surname + "<<" + given).ljust(30, "<")
    return "\n".join([l1, l2, l3])


def test_parser_two_surnames_and_dni_number():
    p = parse_mrz(_td1())
    assert p["surname"] == "GARCIA LOPEZ" and p["given_names"] == "PABLO"
    assert p["full_name"] == "PABLO GARCIA LOPEZ"
    assert p["document_number"] == "CRV123456"  # soporte, se conserva como dato del documento
    assert p["issuing_country"] == "ESP" and p["personal_number"] == "12345678Z"


def test_parser_invalid_dni_letter_is_not_used_as_nif():
    assert parse_mrz(_td1(dni="12345678A"))["personal_number"] is None


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _owner(db):
    suf = uuid.uuid4().hex[:8]
    c = Company(company_name=f"DNI {suf}", slug=f"dni-{suf}")
    u = User(email=f"dni_{suf}@example.test", hashed_password=get_password_hash("TestPass1"), is_active=True)
    db.add_all([c, u])
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    db.commit()
    db.refresh(u)
    return u, c


def test_dni_scan_without_email_asks_for_it_and_creates_nothing(db):
    from fastapi import HTTPException

    u, c = _owner(db)
    with pytest.raises(HTTPException) as exc:
        process_dni_scan(db, u, mrz=_td1(), company_id=c.id)
    assert exc.value.status_code == 422 and "email" in exc.value.detail
    db.rollback()
    assert db.query(Customer).filter(Customer.company_id == c.id).count() == 0
    assert db.query(Customer).filter(Customer.email.like("scan+%@example.com")).count() == 0


def test_dni_scan_creates_real_person_customer(db):
    u, c = _owner(db)
    out = process_dni_scan(db, u, mrz=_td1(), company_id=c.id, email="pablo@example.com")
    cust = db.query(Customer).filter(Customer.id == out["customer_id"]).one()
    assert cust.company_id == c.id
    assert cust.name == "PABLO GARCIA LOPEZ"
    assert cust.tax_id == "12345678Z"
    assert cust.email == "pablo@example.com"
    assert cust.is_company is False
