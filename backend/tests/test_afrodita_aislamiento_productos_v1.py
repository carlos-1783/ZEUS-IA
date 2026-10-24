"""AFRODITA · la vista combinada de productos (TPV + ERP) solo enseña la empresa de la SESIÓN.

Antes `merge_products_view` (GET /afrodita/ops/v1/inventory y /warehouse) leía `company_id IN (todas las
empresas del usuario)` y, además, cualquier `TPVProduct.user_id == user.id` sin mirar la empresa: un
usuario con dos empresas veía mezclados los productos de ambas, y un producto TPV que hubiera dado de
alta en otro tenant seguía apareciendo. Movimientos y rutas igual. Ahora todo se limita a la empresa de
la sesión (la misma que usa `company_inventory_status`: `primary_company_id_for_user`), fail-closed sin
empresa. Login real (token Bearer). Sin red ni LLM.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.company import Company, UserCompany
from app.models.erp import InventoryMovement, Product, TPVProduct
from app.models.ops_route import OpsRoute
from app.models.user import User
from services.afrodita_ops_service_v1 import (
    company_inventory_status,
    list_inventory_movements,
    list_ops_routes,
    merge_products_view,
    warehouse_summary,
)

P = "/api/v1"
OPS = f"{P}/afrodita/ops/v1"


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def client():
    c = TestClient(app)
    try:
        yield c
    finally:
        app.dependency_overrides.clear()


def _company(db, tag):
    suf = uuid.uuid4().hex[:8]
    c = Company(company_name=f"Aisl {tag} {suf}", slug=f"aisl-{tag.lower()}-{suf}", company_type="bar_restaurant")
    db.add(c)
    db.flush()
    return c


def _user(db, tag):
    suf = uuid.uuid4().hex[:8]
    u = User(email=f"aisl_{tag.lower()}_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
             full_name=f"Aisl {tag}", is_active=True)
    db.add(u)
    db.flush()
    return u


def _tpv(db, user, company, name, stock=5):
    p = TPVProduct(user_id=user.id, company_id=company.id, product_id=f"PROD_A_{uuid.uuid4().hex[:10]}",
                   name=name, category="Bebidas", price=1.5, price_with_iva=1.65, iva_rate=10.0, stock=stock)
    db.add(p)
    return p


def _erp(db, user, company, name):
    p = Product(sku=f"AISL-{uuid.uuid4().hex[:8]}", name=name, price=1.0, company_id=company.id,
                track_inventory=True, quantity_on_hand=7.0, low_stock_threshold=10.0)  # bajo minimos
    db.add(p)
    db.flush()
    db.add(InventoryMovement(product_id=p.id, movement_type="adjustment", quantity=1.0,
                             reference=f"ref-{name}", created_by=user.id))
    return p


def _escenario(db):
    """U: empresa de la sesión A (primer vínculo) + segunda empresa B. T: otro tenant con empresa C.
    U dio de alta un producto TPV en C (user_id = U, company_id = C): tampoco debe verse."""
    a, b, c = _company(db, "A"), _company(db, "B"), _company(db, "C")
    u, t = _user(db, "U"), _user(db, "T")
    db.add(UserCompany(user_id=u.id, company_id=a.id, role="owner"))
    db.flush()  # A es el primer vinculo de U -> empresa de la sesion
    db.add(UserCompany(user_id=u.id, company_id=b.id, role="owner"))
    db.add(UserCompany(user_id=t.id, company_id=c.id, role="owner"))
    _tpv(db, u, a, "Caña A")
    _tpv(db, u, b, "Caña B")
    _tpv(db, t, c, "Caña C")
    _tpv(db, u, c, "Caña de U en C")
    _erp(db, u, a, "Harina A")
    _erp(db, u, b, "Harina B")
    _erp(db, t, c, "Harina C")
    for comp, owner in ((a, u), (b, u), (c, t)):
        db.add(OpsRoute(user_id=owner.id, company_id=comp.id, origin=f"Origen {comp.id}",
                        destination=f"Destino {comp.id}", distance=None))
    db.commit()
    for o in (a, b, c, u, t):
        db.refresh(o)
    return u, t, a, b, c


def _login(client, user):
    r = client.post(f"{P}/auth/login", data={"username": user.email, "password": "TestPass1"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ----------------------------------------------------------------------------- servicio
def test_vista_combinada_solo_empresa_de_la_sesion(db):
    u, t, a, b, c = _escenario(db)
    names = sorted(i["name"] for i in merge_products_view(db, u)["items"])
    assert names == ["Caña A", "Harina A"], names
    body = merge_products_view(db, u)
    assert body["count"] == 2 and body["erp_count"] == 1 and body["tpv_count"] == 1
    wh = warehouse_summary(db, u)
    assert wh["total_skus"] == 2 and [i["name"] for i in wh["low_stock_items"]] == ["Harina A"]
    # el otro tenant ve todo lo de SU empresa C (también el producto que dio de alta U en C), nada de A ni B
    names_t = sorted(i["name"] for i in merge_products_view(db, t)["items"])
    assert names_t == ["Caña C", "Caña de U en C", "Harina C"], names_t


def test_movimientos_y_rutas_solo_empresa_de_la_sesion(db):
    u, t, a, b, c = _escenario(db)
    mv = list_inventory_movements(db, u)["movements"]
    assert [m["product_name"] for m in mv] == ["Harina A"]
    routes = list_ops_routes(db, u)["routes"]
    assert [r["origin"] for r in routes] == [f"Origen {a.id}"]


def test_company_inventory_status_no_cambia(db):
    u, t, a, b, c = _escenario(db)
    inv = company_inventory_status(db, a.id)
    assert sorted(i["name"] for i in inv["items"]) == ["Caña A", "Harina A"]


def test_movimiento_solo_sincroniza_el_tpv_de_la_misma_empresa(db):
    """Un movimiento ERP de A ajusta el gemelo TPV de A, nunca el producto homónimo de B ni de otro tenant."""
    from services.afrodita_ops_service_v1 import create_inventory_movement

    u, t, a, b, c = _escenario(db)
    tb = _tpv(db, u, b, "Harina A", stock=30)  # homónimo en B (creado antes que el de A)
    tc = _tpv(db, u, c, "Harina A", stock=30)  # homónimo en otro tenant, con user_id de U
    ta = _tpv(db, u, a, "Harina A", stock=30)
    db.commit()
    pa = db.query(Product).filter(Product.company_id == a.id, Product.name == "Harina A").one()
    out = create_inventory_movement(db, u, product_id=pa.id, movement_type="adjustment", quantity=-4,
                                    company_id=a.id)
    db.commit()
    db.expire_all()
    assert out["tpv_synced"] == ta.product_id
    assert db.get(TPVProduct, ta.id).stock == 26
    assert db.get(TPVProduct, tb.id).stock == 30 and db.get(TPVProduct, tc.id).stock == 30


def test_sin_empresa_fail_closed(db):
    lone = _user(db, "Lone")
    _tpv(db, lone, _company(db, "X"), "Caña huérfana")  # producto TPV con su user_id pero sin vínculo
    db.commit()
    db.refresh(lone)
    assert merge_products_view(db, lone)["items"] == []
    assert warehouse_summary(db, lone)["total_skus"] == 0
    assert list_inventory_movements(db, lone)["movements"] == []
    assert list_ops_routes(db, lone)["routes"] == []


# ----------------------------------------------------------------------------- HTTP con login real
def test_endpoints_con_login_real_aislados(db, client):
    u, t, a, b, c = _escenario(db)
    hu, ht = _login(client, u), _login(client, t)
    r = client.get(f"{OPS}/inventory", headers=hu)
    assert r.status_code == 200, r.text
    assert sorted(i["name"] for i in r.json()["items"]) == ["Caña A", "Harina A"]
    r = client.get(f"{OPS}/warehouse", headers=hu)
    assert r.status_code == 200, r.text
    assert r.json()["total_skus"] == 2
    r = client.get(f"{OPS}/movements", headers=hu)
    assert [m["product_name"] for m in r.json()["movements"]] == ["Harina A"]
    r = client.get(f"{OPS}/routes", headers=hu)
    assert [x["origin"] for x in r.json()["routes"]] == [f"Origen {a.id}"]
    r = client.get(f"{OPS}/inventory", headers=ht)
    assert sorted(i["name"] for i in r.json()["items"]) == ["Caña C", "Caña de U en C", "Harina C"]
    # sin credenciales: rechazo controlado
    r = client.get(f"{OPS}/inventory")
    assert r.status_code in (401, 403), r.text
