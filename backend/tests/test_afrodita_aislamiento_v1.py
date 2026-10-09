"""J9d: aislamiento multi-tenant de AFRODITA OPS/ERP (inventario, movimientos, rutas, productos)
y de los conteos de la auditoria de JUSTICIA. Dos empresas. Sin red ni LLM."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_active_user
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.company import Company, UserCompany
from app.models.erp import InventoryMovement, Product
from app.models.ops_route import OpsRoute
from app.models.user import User
from services.justice_system_audit_v1 import run_system_audit

OPS = "/api/v1/afrodita/ops/v1"


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


@pytest.fixture(autouse=True)
def flags(monkeypatch):
    monkeypatch.setenv("AFRODITA_EXECUTION_ENABLED", "true")
    monkeypatch.setenv("AFRODITA_READ_ONLY_MODE", "false")
    monkeypatch.setenv("AFRODITA_USE_ERP", "true")


def _tenant(db, superuser=False):
    suf = uuid.uuid4().hex[:8]
    c = Company(company_name=f"J9d {suf}", slug=f"j9d-{suf}", company_type="bar_restaurant")
    db.add(c)
    db.flush()
    u = User(email=f"j9d_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
             full_name="J9d", is_active=True, is_superuser=superuser)
    db.add(u)
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    p = Product(sku=f"J9D-{suf}", name=f"Prod {suf}", price=1.0, company_id=c.id,
                track_inventory=True, quantity_on_hand=50.0, low_stock_threshold=1.0)
    db.add(p)
    db.flush()
    m = InventoryMovement(product_id=p.id, movement_type="adjustment", quantity=1.0,
                          reference=f"ref-{suf}", created_by=u.id)
    r = OpsRoute(user_id=u.id, company_id=c.id, origin=f"O{suf}", destination=f"D{suf}", distance=5.0)
    db.add_all([m, r])
    db.commit()
    for o in (c, u, p, r):
        db.refresh(o)
    return u, c, p, r


def _as(user):
    app.dependency_overrides[get_current_active_user] = lambda: user


def test_inventario_solo_de_la_propia_empresa(db, client):
    ua, ca, pa, _ = _tenant(db)
    ub, cb, pb, _ = _tenant(db)
    _as(ua)
    body = client.get(f"{OPS}/inventory").json()
    names = {i["name"] for i in body["items"]}
    assert pa.name in names and pb.name not in names
    _as(ub)
    names = {i["name"] for i in client.get(f"{OPS}/inventory").json()["items"]}
    assert pb.name in names and pa.name not in names


def test_movimientos_solo_de_la_propia_empresa(db, client):
    ua, _, pa, _ = _tenant(db)
    ub, _, pb, _ = _tenant(db)
    _as(ua)
    mv = client.get(f"{OPS}/movements").json()["movements"]
    assert {m["product_id"] for m in mv} == {pa.id}
    _as(ub)
    mv = client.get(f"{OPS}/movements").json()["movements"]
    assert {m["product_id"] for m in mv} == {pb.id}


def test_rutas_solo_de_la_propia_empresa(db, client):
    ua, _, _, ra = _tenant(db)
    ub, _, _, rb = _tenant(db)
    _as(ua)
    ids = {r["id"] for r in client.get(f"{OPS}/routes").json()["routes"]}
    assert ra.id in ids and rb.id not in ids


def test_crear_movimiento_sobre_producto_ajeno_404_stock_intacto(db, client):
    ua, _, pa, _ = _tenant(db)
    ub, _, pb, _ = _tenant(db)
    _as(ua)
    r = client.post(f"{OPS}/movements/create", json={"product_id": pb.id, "quantity": -10, "movement_type": "adjustment"})
    assert r.status_code == 404
    inexistente = client.post(f"{OPS}/movements/create", json={"product_id": 99999999, "quantity": -1})
    assert inexistente.status_code == 404
    assert r.json() == inexistente.json() or r.json()["detail"].startswith("Producto")
    db.expire_all()
    assert db.get(Product, pb.id).quantity_on_hand == 50.0
    assert db.query(InventoryMovement).filter(InventoryMovement.product_id == pb.id).count() == 1


def test_crear_movimiento_sobre_producto_propio_ok(db, client):
    ua, _, pa, _ = _tenant(db)
    _as(ua)
    r = client.post(f"{OPS}/movements/create", json={"product_id": pa.id, "quantity": -10, "movement_type": "adjustment"})
    assert r.status_code == 200, r.text
    db.expire_all()
    assert db.get(Product, pa.id).quantity_on_hand == 40.0


def test_usuario_sin_empresa_fail_closed(db, client):
    _, _, pa, _ = _tenant(db)
    suf = uuid.uuid4().hex[:8]
    lone = User(email=f"lone_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
                full_name="Lone", is_active=True)
    db.add(lone)
    db.commit()
    db.refresh(lone)
    _as(lone)
    assert client.get(f"{OPS}/inventory").json()["items"] == []
    assert client.get(f"{OPS}/movements").json()["movements"] == []
    assert client.get(f"{OPS}/routes").json()["routes"] == []
    assert client.post(f"{OPS}/movements/create", json={"product_id": pa.id, "quantity": -1}).status_code in (403, 404)


def test_create_inventory_movement_company_id_obligatorio(db):
    from services.afrodita_ops_service_v1 import create_inventory_movement

    ua, _, pa, _ = _tenant(db)
    with pytest.raises(TypeError):
        create_inventory_movement(db, ua, product_id=pa.id, movement_type="adjustment", quantity=-1)


def test_products_rest_legacy_aislado(db, client):
    ua, _, pa, _ = _tenant(db)
    ub, _, pb, _ = _tenant(db)
    _as(ua)
    r = client.get("/api/v1/products/")
    assert r.status_code == 200, r.text
    txt = r.text
    assert pa.sku in txt and pb.sku not in txt
    assert client.get(f"/api/v1/products/{pb.id}").status_code == 404
    assert client.get(f"/api/v1/products/{pb.id}/inventory/movements").status_code == 404
    assert client.post(f"/api/v1/products/{pb.id}/inventory/movements",
                       json={"movement_type": "adjustment", "quantity": 1}).status_code in (404, 422)


def _audit_value(body, check):
    for c in body["conclusions"]:
        if c["check"] == check:
            return c["value"]
    raise AssertionError(check)


def test_auditoria_justicia_sin_conteos_globales_para_no_superusuario(db):
    ua, _, _, _ = _tenant(db)
    _tenant(db)
    _tenant(db)
    body = run_system_audit(db, ua)
    assert _audit_value(body, "productos ERP en tabla products") == 1
    assert _audit_value(body, "inventory_movements accesible") == 1
    assert all("global" not in (t.get("detail") or "") for t in body["audit_trace"] if t.get("kind") == "table")


def test_auditoria_justicia_superusuario_ve_globales(db):
    ua, _, _, _ = _tenant(db)
    su, _, _, _ = _tenant(db, superuser=True)
    body = run_system_audit(db, su)
    total = db.query(Product).count()
    assert _audit_value(body, "productos ERP en tabla products") == total
    assert total >= 2
