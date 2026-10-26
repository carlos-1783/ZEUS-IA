"""AFRODITA: precio o stock vacio (NULL) se queda vacio (None), nunca 0 (services/afrodita_ops_service_v1).

Antes `_erp_row`/`_tpv_row` hacian `float(x or 0)` y `company_inventory_status` `float(quantity_on_hand or 0)`:
un producto ERP con control de stock pero cantidad NULL (fila antigua) salia como «0 unidades», se contaba
«sin stock» y el panel pintaba «0» en vez de «—». Un precio NULL salia como 0 €.
Decisiones:
- NULL = dato desconocido -> None en la respuesta (la UI ya muestra «—» para null).
- Stock desconocido NO es «sin stock» ni «bajo minimos»: va a «sin control de stock» (untracked) y no suma
  unidades. Si el TPV gemelo si sabe el stock, se usa el del TPV (mismo criterio que con ERP sin control).
- `low_stock_threshold` NULL sigue siendo «sin minimo» (0), como antes: no es precio ni stock.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from app.db.base import Base, SessionLocal, engine
from app.models.company import Company, UserCompany
from app.models.erp import Product, ProductCategory, ProductStatus, TPVProduct
from app.models.user import User
from services.afrodita_ops_service_v1 import (
    _erp_row,
    _tpv_row,
    company_inventory_status,
    merge_products_view,
    warehouse_summary,
)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def owner(db):
    suf = uuid.uuid4().hex[:8]
    u = User(email=f"afro-null-{suf}@test.local", hashed_password="x", is_active=True, is_superuser=False)
    c = Company(company_name=f"AFRO NULL {suf}", slug=f"afro-null-{suf}", company_type="bar_restaurant")
    db.add_all([u, c])
    db.commit()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    db.commit()
    db.refresh(u)
    db.refresh(c)
    return u, c


def _erp(db, company, name, qty, threshold=5.0, track=True):
    p = Product(company_id=company.id, sku=f"SKU-{uuid.uuid4().hex[:8]}", name=name, price=2.0,
                track_inventory=track, quantity_on_hand=qty, low_stock_threshold=threshold,
                category=ProductCategory.GOODS, status=ProductStatus.ACTIVE)
    db.add(p)
    db.commit()
    if qty is None:
        # El default del modelo (0.0) se aplicaria al pasar None: se deja NULL como una fila antigua de BD.
        db.execute(text("UPDATE products SET quantity_on_hand = NULL WHERE id = :i"), {"i": p.id})
        db.commit()
        db.refresh(p)
        assert p.quantity_on_hand is None
    return p


def _tpv(db, user, company, name, stock):
    p = TPVProduct(user_id=user.id, company_id=company.id, product_id=f"PROD_N_{uuid.uuid4().hex[:10]}",
                   name=name, category="Bebidas", price=1.5, price_with_iva=1.65, iva_rate=10.0, stock=stock)
    db.add(p)
    db.commit()
    return p


def test_rows_keep_null_price_and_stock_as_none():
    # price es NOT NULL en el modelo, pero filas antiguas de BD pueden traerlo NULL: se prueba la conversion.
    erp = SimpleNamespace(id=1, sku="S", name="X", quantity_on_hand=None, low_stock_threshold=None,
                          track_inventory=True, category=None, status=None, price=None)
    row = _erp_row(erp)
    assert row["price"] is None and row["quantity_on_hand"] is None
    assert row["low_stock_threshold"] == 0.0
    tpv = SimpleNamespace(product_id="P", name="Y", stock=None, category="C", price=None, company_id=1)
    assert _tpv_row(tpv)["price"] is None and _tpv_row(tpv)["stock"] is None
    # Un 0 real sigue siendo 0 (no se confunde con vacio)
    erp.price, erp.quantity_on_hand = 0, 0
    assert _erp_row(erp)["price"] == 0.0 and _erp_row(erp)["quantity_on_hand"] == 0.0


def test_inventory_status_null_stock_is_untracked_not_out_of_stock(db, owner):
    u, c = owner
    _erp(db, c, "Harina", None)            # control de stock, cantidad desconocida
    _erp(db, c, "Azucar", 0)               # agotado de verdad
    _erp(db, c, "Sal", 2)                  # bajo minimos (2 <= 5)
    _erp(db, c, "Aceite", None)            # desconocido en ERP...
    _tpv(db, u, c, "Aceite", 7)            # ...pero el TPV gemelo si lo sabe
    inv = company_inventory_status(db, c.id)
    items = {i["name"]: i for i in inv["items"]}
    assert items["Harina"]["stock"] is None
    assert items["Aceite"]["stock"] == 7.0
    assert [i["name"] for i in inv["out_of_stock_items"]] == ["Azucar"]
    assert [i["name"] for i in inv["low_stock_items"]] == ["Sal"]
    assert [i["name"] for i in inv["untracked_items"]] == ["Harina"]
    assert inv["tracked_skus"] == 3 and inv["untracked_skus"] == 1
    assert inv["total_units"] == 9.0  # 0 + 2 + 7: Harina no suma


def test_merged_view_and_warehouse_do_not_turn_null_into_zero(db, owner):
    u, c = owner
    _erp(db, c, "Harina", None)
    _erp(db, c, "Azucar", 0)
    view = merge_products_view(db, u)
    rows = {i["name"]: i for i in view["items"]}
    assert rows["Harina"]["stock"] is None and rows["Harina"]["erp_quantity_on_hand"] is None
    assert rows["Harina"]["low_stock"] is False          # desconocido no es «bajo minimos»
    assert rows["Azucar"]["stock"] == 0.0 and rows["Azucar"]["low_stock"] is True
    wh = warehouse_summary(db, u)
    assert wh["low_stock_count"] == 1 and wh["total_units"] == 0.0
    assert [i["name"] for i in wh["low_stock_items"]] == ["Azucar"]
