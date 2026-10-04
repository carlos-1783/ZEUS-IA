"""
Regresión E1b (hallazgo de revisor durante E1, severidad Media-Alta):

`fiscal_engine.get_fiscal_profile(db, user_id)` filtraba el perfil fiscal
(`FiscalProfile`) por `user_id` en vez de por empresa. Esta función de SERVICIO
(distinta de los endpoints HTTP /tpv/fiscal-profile ya corregidos en E1) se
llama internamente desde `tpv_service.process_sale` (TPV) y
`crm_office_service.register_record_charge` (CRM oficina) para decidir si
aplicar recargo de equivalencia a una venta/cobro real.

En una empresa con 2+ usuarios (owner que configuró el perfil fiscal + un
segundo cajero/encargado vinculado vía UserCompany, pero que no es el
`user_id` que creó originalmente la fila `FiscalProfile`), el segundo usuario
al vender NO encontraba el perfil fiscal de SU PROPIA empresa: la venta se
procesaba sin recargo de equivalencia aunque la empresa lo tuviera activado.

Estos tests fijan el comportamiento correcto:
  * una venta real (`TPVService.process_sale`) hecha por el SEGUNDO usuario
    aplica el recargo de equivalencia del perfil fiscal de la empresa
    (configurado originalmente por el owner);
  * el aislamiento cross-tenant se mantiene: un usuario de OTRA empresa sin
    perfil fiscal propio no hereda el recargo de la empresa ajena.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.models.company import Company, UserCompany
from app.models.fiscal import FiscalProfile, TPVSale
from app.models.user import User

from services.fiscal_engine import get_fiscal_profile
from services.tpv_service import BusinessProfile, PaymentMethod, TPVService


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _mk_user(db: Session, *, tag: str) -> User:
    suf = uuid.uuid4().hex[:8]
    user = User(
        email=f"e1b_{tag}_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name=f"E1b {tag}",
        is_active=True,
        role="owner",
    )
    db.add(user)
    db.flush()
    return user


def _mk_company(db: Session, *, tag: str) -> Company:
    suf = uuid.uuid4().hex[:8]
    company = Company(company_name=f"E1b Co {tag} {suf}", slug=f"e1b-{tag}-{suf}")
    db.add(company)
    db.flush()
    return company


def _link(db: Session, user: User, company: Company, *, role: str = "owner") -> None:
    db.add(UserCompany(user_id=user.id, company_id=company.id, role=role))


def _two_users_same_company(db: Session):
    """owner (configura el perfil fiscal) + segundo cajero, misma empresa vía UserCompany."""
    company = _mk_company(db, tag="shared")
    owner = _mk_user(db, tag="owner")
    second = _mk_user(db, tag="second")
    _link(db, owner, company, role="owner")
    _link(db, second, company, role="member")
    db.commit()
    db.refresh(owner)
    db.refresh(second)
    db.refresh(company)
    return owner, second, company


def _outsider_with_company(db: Session):
    """Usuario de una empresa DISTINTA, sin perfil fiscal propio configurado."""
    other_company = _mk_company(db, tag="other")
    outsider = _mk_user(db, tag="outsider")
    _link(db, outsider, other_company, role="owner")
    db.commit()
    db.refresh(outsider)
    db.refresh(other_company)
    return outsider, other_company


def _cart_line(*, price: float, iva_rate: float, quantity: int = 1) -> dict:
    price_with_iva = price * (1 + iva_rate / 100)
    return {
        "product_id": f"PROD-{uuid.uuid4().hex[:6]}",
        "name": "Producto prueba",
        "price": price,
        "price_with_iva": price_with_iva,
        "quantity": quantity,
        "subtotal": price * quantity,
        "subtotal_with_iva": price_with_iva * quantity,
        "iva_rate": iva_rate,
        "category": "General",
    }


def test_get_fiscal_profile_filters_by_company_not_by_creator_user_id(db: Session):
    """Unit: get_fiscal_profile debe devolver el perfil de la EMPRESA, no solo el
    creado bajo el user_id exacto, y no debe filtrar por company_id ajeno."""
    owner, second, company = _two_users_same_company(db)
    outsider, other_company = _outsider_with_company(db)

    profile = FiscalProfile(
        user_id=owner.id,
        company_id=company.id,
        vat_regime="recargo_equivalencia",
        apply_recargo_equivalencia=True,
        recargo_rate=Decimal("5.2"),
    )
    db.add(profile)
    db.commit()

    # Antes del fix: get_fiscal_profile(db, second.id) -> None (filtraba por
    # user_id == second.id, que nunca creó la fila). Con el fix, pasando el
    # company_id de la venta en curso, el segundo usuario SI encuentra el
    # perfil de su empresa.
    found = get_fiscal_profile(db, second.id, company_id=company.id)
    assert found is not None
    assert found.id == profile.id
    assert found.apply_recargo_equivalencia is True

    # Aislamiento cross-tenant: el outsider (otra empresa, sin perfil propio)
    # no debe heredar el perfil/recargo de la empresa ajena.
    not_found = get_fiscal_profile(db, outsider.id, company_id=other_company.id)
    assert not_found is None


def test_process_sale_by_second_user_applies_company_recargo_equivalencia(db: Session):
    """Integración real: una venta de TPV (process_sale) hecha por el SEGUNDO
    usuario debe aplicar el recargo de equivalencia del perfil fiscal de SU
    empresa (configurado originalmente por el owner), no un perfil vacío."""
    owner, second, company = _two_users_same_company(db)

    profile = FiscalProfile(
        user_id=owner.id,
        company_id=company.id,
        vat_regime="recargo_equivalencia",
        apply_recargo_equivalencia=True,
        # fiscal_engine.build_fiscal_items_from_cart multiplica directamente
        # base_amount * recargo_rate (sin dividir entre 100), igual que indica
        # el comentario del modelo ("ej. 5.2% = 0.052"): el valor almacenado
        # debe ser la fracción, no el porcentaje.
        recargo_rate=Decimal("0.052"),
    )
    db.add(profile)
    db.commit()

    svc = TPVService()
    svc.set_business_profile(BusinessProfile.OTROS, user_id=second.id)

    cart_line = _cart_line(price=100.0, iva_rate=21.0)

    result = svc.process_sale(
        payment_method=PaymentMethod.EFECTIVO,
        cart_lines=[cart_line],
        user_id=second.id,
        db=db,
        company_id=company.id,
    )

    assert result.get("success") is True, result
    tpv_sale_id = result["ticket"]["fiscal_snapshot_id"] if "ticket" in result else result.get("fiscal_snapshot_id")
    assert tpv_sale_id, result

    sale = db.query(TPVSale).filter(TPVSale.id == tpv_sale_id).first()
    assert sale is not None
    assert sale.user_id == second.id
    assert sale.company_id == company.id
    # 100 base * 5.2% = 5.20 de recargo de equivalencia (antes del fix: 0 /
    # None, porque el segundo usuario no encontraba el perfil de su empresa).
    assert sale.recargo_amount is not None
    assert Decimal(sale.recargo_amount) == Decimal("5.20")


def test_process_sale_by_outsider_does_not_leak_other_company_recargo(db: Session):
    """Aislamiento cross-tenant real a nivel de venta: un usuario de OTRA
    empresa sin perfil fiscal propio NO hereda el recargo de equivalencia de
    la empresa ajena (confirmado tras el fix de scoping)."""
    owner, second, company = _two_users_same_company(db)
    outsider, other_company = _outsider_with_company(db)

    profile = FiscalProfile(
        user_id=owner.id,
        company_id=company.id,
        vat_regime="recargo_equivalencia",
        apply_recargo_equivalencia=True,
        recargo_rate=Decimal("0.052"),
    )
    db.add(profile)
    db.commit()

    svc = TPVService()
    svc.set_business_profile(BusinessProfile.OTROS, user_id=outsider.id)

    cart_line = _cart_line(price=100.0, iva_rate=21.0)

    result = svc.process_sale(
        payment_method=PaymentMethod.EFECTIVO,
        cart_lines=[cart_line],
        user_id=outsider.id,
        db=db,
        company_id=other_company.id,
    )

    assert result.get("success") is True, result
    tpv_sale_id = result["ticket"]["fiscal_snapshot_id"] if "ticket" in result else result.get("fiscal_snapshot_id")
    assert tpv_sale_id, result

    sale = db.query(TPVSale).filter(TPVSale.id == tpv_sale_id).first()
    assert sale is not None
    assert sale.company_id == other_company.id
    # Sin perfil fiscal propio -> sin recargo (no debe filtrarse el de la
    # empresa `company`, que es ajena a `other_company`).
    assert not sale.recargo_amount
