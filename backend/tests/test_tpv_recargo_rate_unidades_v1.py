"""
Regresion E4 (hallazgo del orquestador, severidad Media): inconsistencia de
unidades en `FiscalProfile.recargo_rate` del recargo de equivalencia.

- `app/models/fiscal.py`: el modelo documenta que el valor almacenado debe ser
  una FRACCION (0.052 para 5.2%).
- `app/api/v1/endpoints/tpv.py` (`FiscalProfileCreate.recargo_rate`): el schema
  HTTP documenta que el campo recibido es un PORCENTAJE (5.2 para 5.2%).
- Antes del fix, `set_fiscal_profile` guardaba `request.recargo_rate` tal cual
  (el porcentaje crudo) en el modelo, y `fiscal_engine.build_fiscal_items_from_cart`
  multiplicaba `base_amount * recargo_rate` asumiendo que ya era una fraccion.
  Resultado: un perfil configurado con "5.2" (tal como pide el propio schema)
  producia un recargo del 520% en cada venta real, en vez del 5.2% correcto.

Decision de unidad tomada: la API HTTP (`tpv.py`) sigue hablando en PORCENTAJE
de cara al cliente/formulario (recibe y devuelve 5.2), pero internamente
convierte a FRACCION antes de guardar en `FiscalProfile.recargo_rate` (0.052),
que es lo que consumen `fiscal_engine.py` y los servicios de venta
(`tpv_service.py`, `crm_office_service.py`) sin dividir entre 100.

Estos tests fijan el comportamiento correcto:
  * guardar un perfil fiscal via HTTP con recargo_rate=5.2 y vender de verdad
    (`TPVService.process_sale`) produce un recargo_amount del 5.2% de la base,
    no del 520%;
  * leer el perfil tras guardarlo devuelve el mismo "5.2" que se envio
    (round-trip porcentaje -> fraccion -> porcentaje sin perdida).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.fiscal import FiscalProfile, TPVSale
from app.models.user import User

from services.tpv_service import BusinessProfile, PaymentMethod, TPVService


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client():
    """Cliente sin lifespan: no ejecuta los eventos de arranque de la app."""
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        app.dependency_overrides.clear()


def _mk_user(db: Session, *, tag: str = "u") -> User:
    suf = uuid.uuid4().hex[:8]
    user = User(
        email=f"e4_recargo_{tag}_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name=f"E4 Recargo {tag}",
        is_active=True,
        role="owner",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _as(client: TestClient, user: User) -> None:
    app.dependency_overrides[get_current_active_user] = lambda: user


def _cart_line(*, price: float, iva_rate: float, quantity: int = 1) -> dict:
    price_with_iva = price * (1 + iva_rate / 100)
    return {
        "product_id": f"PROD-{uuid.uuid4().hex[:6]}",
        "name": "Producto prueba E4",
        "price": price,
        "price_with_iva": price_with_iva,
        "quantity": quantity,
        "subtotal": price * quantity,
        "subtotal_with_iva": price_with_iva * quantity,
        "iva_rate": iva_rate,
        "category": "General",
    }


def test_set_fiscal_profile_stores_fraction_not_percent(db: Session, client: TestClient):
    """El schema HTTP documenta recargo_rate=5.2 para 5.2%. Debe guardarse en
    BD como la fraccion 0.052 (no como 5.2), que es lo que consume el motor
    fiscal."""
    user = _mk_user(db, tag="store")
    _as(client, user)

    resp = client.post(
        "/api/v1/tpv/fiscal-profile",
        json={"vat_regime": "recargo_equivalencia", "apply_recargo_equivalencia": True, "recargo_rate": 5.2},
    )
    assert resp.status_code == 200, resp.text

    profile = db.query(FiscalProfile).filter(FiscalProfile.user_id == user.id).first()
    assert profile is not None
    assert profile.recargo_rate is not None
    assert Decimal(profile.recargo_rate) == Decimal("0.0520")


def test_get_fiscal_profile_round_trips_percent(db: Session, client: TestClient):
    """Guardar 5.2 (porcentaje) y leerlo de vuelta debe devolver 5.2, no 0.052
    ni 520, para que un futuro formulario muestre el mismo valor que el
    usuario introdujo."""
    user = _mk_user(db, tag="roundtrip")
    _as(client, user)

    resp = client.post(
        "/api/v1/tpv/fiscal-profile",
        json={"vat_regime": "recargo_equivalencia", "apply_recargo_equivalencia": True, "recargo_rate": 5.2},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["profile"]["recargo_rate"] == pytest.approx(5.2)

    resp = client.get("/api/v1/tpv/fiscal-profile")
    assert resp.status_code == 200, resp.text
    profile = resp.json()["profile"]
    assert profile is not None
    assert profile["recargo_rate"] == pytest.approx(5.2)


def test_process_sale_applies_correct_recargo_percentage(db: Session, client: TestClient):
    """Integracion real: configurar el perfil fiscal via HTTP con 5.2 (tal
    como documenta el schema) y vender de verdad con TPVService.process_sale
    debe aplicar un recargo del 5.2% de la base, no del 520%."""
    user = _mk_user(db, tag="sale")
    _as(client, user)

    resp = client.post(
        "/api/v1/tpv/fiscal-profile",
        json={"vat_regime": "recargo_equivalencia", "apply_recargo_equivalencia": True, "recargo_rate": 5.2},
    )
    assert resp.status_code == 200, resp.text

    svc = TPVService()
    svc.set_business_profile(BusinessProfile.OTROS, user_id=user.id)

    cart_line = _cart_line(price=100.0, iva_rate=21.0)

    result = svc.process_sale(
        payment_method=PaymentMethod.EFECTIVO,
        cart_lines=[cart_line],
        user_id=user.id,
        db=db,
    )

    assert result.get("success") is True, result
    tpv_sale_id = result["ticket"]["fiscal_snapshot_id"] if "ticket" in result else result.get("fiscal_snapshot_id")
    assert tpv_sale_id, result

    sale = db.query(TPVSale).filter(TPVSale.id == tpv_sale_id).first()
    assert sale is not None

    # 100 base * 5.2% = 5.20 de recargo de equivalencia.
    # Antes del fix: 100 * 5.2 (fraccion mal interpretada) = 520.00 (520%).
    assert sale.recargo_amount is not None
    assert Decimal(sale.recargo_amount) == Decimal("5.20")
    assert Decimal(sale.recargo_amount) != Decimal("520.00")
