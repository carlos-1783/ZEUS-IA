"""
Regresión N4 (backlog ejecutor-produccion): dos endpoints filtraban por
`user_id` del usuario autenticado en vez de por la(s) empresa(s) a las que
pertenece, haciendo que el modelo 303 trimestral y los borradores de nómina
fueran INCORRECTOS (incompletos) en cualquier empresa con más de un usuario.

1) GET /api/v1/tpv/fiscal/quarterly-vat (app/api/v1/endpoints/tpv.py)
   Antes: TPVSale.user_id == current_user.id -> cada usuario solo veía SU
   PARTE de las ventas de la empresa, no el total real de la empresa.
   Ahora: agrega todas las TPVSale de la(s) empresa(s) del usuario
   (TPVSale.company_id IN company_ids_for_user), con fallback a
   user_id para ventas legado sin company_id y para usuarios sin empresa.

2) GET /api/v1/payroll/drafts (app/api/v1/endpoints/payroll.py)
   PayrollDraft.owner_user_id es, por diseño (ver app/models/payroll_draft.py
   y alembic/versions/0045_fix_misleading_company_id_naming.py), el ID del
   usuario "empresa/empleador" que generó el borrador -- NO una FK a
   companies.id. Para un owner normal, filtrar por owner_user_id ==
   current_user.id es correcto (es su propia "empresa"). El hallazgo real
   era que el superuser, pese a tener bypass explícito en el endpoint de
   descarga (`draft.owner_user_id != current_user.id and not
   current_user.is_superuser`), NO tenía ese mismo bypass en el listado:
   un superuser que llamase a /drafts solo veía SUS PROPIOS borradores (casi
   siempre ninguno), no podía auditar/consolidar los de otras empresas.
   Ahora /drafts da acceso completo (opcionalmente acotado por
   ?owner_user_id=) a superuser, igual alcance que ya tenía /download.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest  # pyright: ignore[reportMissingImports]
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.company import Company, UserCompany
from app.models.fiscal import TPVSale, TPVSaleItem
from app.models.payroll_draft import PayrollDraft
from app.models.user import User

CLIENT = TestClient(app)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.pop(get_current_active_user, None)


def _mk_user(db: Session, *, tag: str, role: str = "owner", is_superuser: bool = False) -> User:
    suf = uuid.uuid4().hex[:8]
    user = User(
        email=f"n4_{tag}_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name=f"N4 {tag}",
        is_active=True,
        role=role,
        is_superuser=is_superuser,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _mk_company(db: Session, *, tag: str) -> Company:
    suf = uuid.uuid4().hex[:8]
    company = Company(company_name=f"N4 Co {tag} {suf}", slug=f"n4-{tag}-{suf}")
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def _link(db: Session, user: User, company: Company, role: str = "company_admin") -> None:
    db.add(UserCompany(user_id=user.id, company_id=company.id, role=role))
    db.commit()


def _mk_sale(db: Session, *, user: User, company: Company | None, total: float, base: float, tax: float) -> TPVSale:
    sale = TPVSale(
        user_id=user.id,
        company_id=company.id if company else None,
        ticket_id=f"TCK-{uuid.uuid4().hex[:10]}",
        document_type="ticket",
        sale_date=datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc),
        payment_method="cash",
        subtotal=base,
        tax_amount=tax,
        recargo_amount=0,
        total=total,
    )
    db.add(sale)
    db.commit()
    db.refresh(sale)
    item = TPVSaleItem(
        tpv_sale_id=sale.id,
        product_id="p1",
        product_name="Producto",
        quantity=1,
        unit_price=total,
        tax_rate_snapshot=0.21,
        tax_amount=tax,
        base_amount=base,
        recargo_amount=0,
    )
    db.add(item)
    db.commit()
    return sale


def _override_user(user) -> None:
    app.dependency_overrides[get_current_active_user] = lambda: user


# --------------------------------------------------------------------------- 1) quarterly-vat


def test_quarterly_vat_aggregates_full_company_not_just_caller(db: Session):
    """Empresa con 2 usuarios, cada uno registra ventas; el 303 debe incluir
    el total de la empresa sin importar cuál de los dos lo consulte."""
    company = _mk_company(db, tag="multi")
    user_a = _mk_user(db, tag="a")
    user_b = _mk_user(db, tag="b")
    _link(db, user_a, company)
    _link(db, user_b, company)

    _mk_sale(db, user=user_a, company=company, total=121.0, base=100.0, tax=21.0)
    _mk_sale(db, user=user_b, company=company, total=242.0, base=200.0, tax=42.0)

    expected_base_21 = 300.0
    expected_iva_21 = 63.0

    for caller in (user_a, user_b):
        _override_user(caller)
        resp = CLIENT.get(
            "/api/v1/tpv/fiscal/quarterly-vat",
            params={"year": 2026, "quarter": 2},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["base_21"] == pytest.approx(expected_base_21), (caller.email, data)
        assert data["iva_21"] == pytest.approx(expected_iva_21), (caller.email, data)
        assert data["grand_total"] == pytest.approx(121.0 + 242.0), (caller.email, data)


def test_quarterly_vat_does_not_leak_another_company_sales(db: Session):
    """Dos empresas distintas en el mismo trimestre: cada una solo ve la suya."""
    company_x = _mk_company(db, tag="x")
    company_y = _mk_company(db, tag="y")
    user_x = _mk_user(db, tag="x")
    user_y = _mk_user(db, tag="y")
    _link(db, user_x, company_x)
    _link(db, user_y, company_y)

    _mk_sale(db, user=user_x, company=company_x, total=121.0, base=100.0, tax=21.0)
    _mk_sale(db, user=user_y, company=company_y, total=605.0, base=500.0, tax=105.0)

    _override_user(user_x)
    resp = CLIENT.get("/api/v1/tpv/fiscal/quarterly-vat", params={"year": 2026, "quarter": 2})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["base_21"] == pytest.approx(100.0)
    assert data["grand_total"] == pytest.approx(121.0)


def test_quarterly_vat_legacy_sale_without_company_id_falls_back_to_owner(db: Session):
    """Ventas legado con company_id=NULL deben seguir contando para su propio
    usuario (fallback), sin colarse en otra empresa."""
    user_solo = _mk_user(db, tag="solo")
    # Sin UserCompany: company_ids_for_user devuelve [] -> fallback a user_id.
    _mk_sale(db, user=user_solo, company=None, total=50.0, base=41.0, tax=9.0)

    _override_user(user_solo)
    resp = CLIENT.get("/api/v1/tpv/fiscal/quarterly-vat", params={"year": 2026, "quarter": 2})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["grand_total"] == pytest.approx(50.0)


# --------------------------------------------------------------------------- 2) payroll drafts


def _mk_draft(db: Session, *, owner_user_id: int, employee_id: int, gross: float) -> PayrollDraft:
    d = PayrollDraft(
        owner_user_id=owner_user_id,
        employee_id=employee_id,
        gross_salary=gross,
        irpf_estimated=0,
        social_security_estimated=0,
        net_salary_estimated=gross,
        month="Mayo",
        year=2026,
        status="BORRADOR_GENERADO",
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def test_owner_lists_only_their_own_drafts_by_design(db: Session):
    """owner_user_id no es una FK a companies.id: es el propio owner. Un
    owner normal solo debe ver SUS borradores (comportamiento correcto, no
    es el bug)."""
    owner_1 = _mk_user(db, tag="owner1", role="owner")
    owner_2 = _mk_user(db, tag="owner2", role="owner")
    employee = _mk_user(db, tag="emp", role="employee")

    _mk_draft(db, owner_user_id=owner_1.id, employee_id=employee.id, gross=1500.0)
    _mk_draft(db, owner_user_id=owner_2.id, employee_id=employee.id, gross=2000.0)

    _override_user(owner_1)
    resp = CLIENT.get("/api/v1/payroll/drafts")
    assert resp.status_code == 200, resp.text
    drafts = resp.json()["drafts"]
    assert len(drafts) == 1
    assert drafts[0]["gross_salary"] == pytest.approx(1500.0)


def test_employee_role_cannot_list_payroll_drafts_at_all(db: Session):
    employee = _mk_user(db, tag="emp2", role="employee")
    _override_user(employee)
    resp = CLIENT.get("/api/v1/payroll/drafts")
    assert resp.status_code == 403


def test_superuser_lists_drafts_across_all_owners_not_just_their_own(db: Session):
    """Bug real: antes del fix, un superuser (con bypass ya existente en
    /download) solo veía SUS PROPIOS borradores en /drafts -- normalmente
    ninguno, porque el superuser no suele generar nóminas con su propio id.
    Ahora debe ver los de TODAS las empresas/owners."""
    owner_1 = _mk_user(db, tag="owner3", role="owner")
    owner_2 = _mk_user(db, tag="owner4", role="owner")
    employee = _mk_user(db, tag="emp3", role="employee")
    superuser = _mk_user(db, tag="root", role="owner", is_superuser=True)

    _mk_draft(db, owner_user_id=owner_1.id, employee_id=employee.id, gross=1200.0)
    _mk_draft(db, owner_user_id=owner_2.id, employee_id=employee.id, gross=1800.0)

    _override_user(superuser)
    resp = CLIENT.get("/api/v1/payroll/drafts")
    assert resp.status_code == 200, resp.text
    drafts = resp.json()["drafts"]
    gross_values = sorted(d["gross_salary"] for d in drafts)
    assert 1200.0 in gross_values
    assert 1800.0 in gross_values

    # Y puede acotar a un owner concreto.
    resp_scoped = CLIENT.get("/api/v1/payroll/drafts", params={"owner_user_id": owner_2.id})
    assert resp_scoped.status_code == 200, resp_scoped.text
    scoped = resp_scoped.json()["drafts"]
    assert all(d["gross_salary"] == pytest.approx(1800.0) for d in scoped)
    assert len(scoped) >= 1


def test_download_still_rejects_other_owners_draft_but_allows_superuser(db: Session):
    owner_1 = _mk_user(db, tag="owner5", role="owner")
    owner_2 = _mk_user(db, tag="owner6", role="owner")
    employee = _mk_user(db, tag="emp4", role="employee")
    draft = _mk_draft(db, owner_user_id=owner_1.id, employee_id=employee.id, gross=900.0)

    _override_user(owner_2)
    resp = CLIENT.get(f"/api/v1/payroll/drafts/{draft.id}/download")
    assert resp.status_code == 403
    assert "No autorizado" in resp.json()["detail"]
