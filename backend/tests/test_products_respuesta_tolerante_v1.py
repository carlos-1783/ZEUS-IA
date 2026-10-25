"""GET /products/ (listado, detalle, variantes, movimientos): la RESPUESTA no aplica reglas de entrada.

Antes ProductInDB / ProductVariantInDB / InventoryMovementInDB heredaban de los schemas de ENTRADA
(price gt=0, sku/name min_length=1, quantity != 0, unit_cost ge=0, campos obligatorios). Una sola fila
que no las cumpliera -- un producto a 0 EUR, una fila antigua con NULL, un movimiento con cantidad 0 --
hacia fallar la serializacion (ResponseValidationError) y GET /products/ devolvia 500 para TODA la empresa.

Se fija:
  1. Producto a 0 EUR creado por la API real -> aparece en listado y detalle con price 0.0.
  2. Producto antiguo con NULLs, variante con NULLs y movimiento con quantity 0 / unit_cost negativo
     (insertados por SQL crudo) -> 200 y esos campos a null (nunca 0, "" ni fechas inventadas).
  3. Otra empresa no ve esas filas (404 / ausentes del listado).
  4. La ENTRADA sigue rechazando lo invalido (precio negativo, nombre/sku vacios, tax_rate > 100...).
Login real (register + /auth/login, Bearer) y TestClient sobre la app real.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import settings
from app.db.base import SessionLocal
from app.main import app
from app.models.company import UserCompany
from app.models.user import User

pytestmark = pytest.mark.usefixtures("no_external_messaging")
API = settings.API_V1_STR


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _register_login(client):
    suf = uuid.uuid4().hex[:10]
    payload = {"email": f"prodtol_{suf}@example.com", "password": "TestPass1", "full_name": "Titular Productos",
               "phone": "612345678", "company_name": f"Tienda Tolerante {suf}", "business_type": "restaurant"}
    r = client.post(f"{API}/auth/register", json=payload)
    if r.status_code != 201:
        pytest.skip(f"Registro no disponible: {r.status_code}")
    login = client.post(f"{API}/auth/login", data={"username": payload["email"], "password": payload["password"]})
    assert login.status_code == 200, login.text
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == payload["email"]).one()
        uc = db.query(UserCompany).filter(UserCompany.user_id == user.id).order_by(UserCompany.id.asc()).first()
        assert uc is not None
        return {"Authorization": f"Bearer {login.json()['access_token']}"}, user.id, uc.company_id
    finally:
        db.close()


@pytest.fixture(scope="module")
def user(client):
    """Titulares por modulo: /auth/register tiene limite de 10/min por IP (SecurityMiddleware)."""
    return _register_login(client)


@pytest.fixture(scope="module")
def other(client):
    return _register_login(client)


def _insert(table: str, **row) -> int:
    """INSERT por SQL crudo (como una fila antigua/legacy), sin ORM ni defaults de Python."""
    names = ", ".join(row)
    params = ", ".join(f":{k}" for k in row)
    db = SessionLocal()
    try:
        db.execute(text(f"INSERT INTO {table} ({names}) VALUES ({params})"), row)
        db.commit()
        return db.execute(text(f"SELECT max(id) FROM {table}")).scalar_one()
    finally:
        db.close()


def _list(client, h):
    r = client.get(f"{API}/products/?limit=1000", headers=h)
    assert r.status_code == 200, r.text
    return {d["id"]: d for d in r.json()["data"]}


# ---------------------------------------------------------------------------- 1. producto a 0 EUR

def test_zero_euro_product_is_created_listed_and_readable(client, user):
    h, _, _ = user
    r = client.post(f"{API}/products/", headers=h, json={"sku": f"FREE-{uuid.uuid4().hex[:6]}",
                                                         "name": "Agua (invitacion)", "price": 0.0})
    assert r.status_code == 201, r.text
    pid = r.json()["data"]["id"]
    assert r.json()["data"]["price"] == 0.0
    assert r.json()["data"]["description"] is None  # descripcion opcional: no se inventa
    assert _list(client, h)[pid]["price"] == 0.0
    one = client.get(f"{API}/products/{pid}", headers=h)
    assert one.status_code == 200, one.text
    assert one.json()["data"]["price"] == 0.0


# ---------------------------------------------------------------------------- 2. NULLs legacy

@pytest.fixture(scope="module")
def legacy(user):
    _, uid, cid = user
    pid = _insert("products", sku=f"LEG-{uuid.uuid4().hex[:6]}", name="Producto antiguo", price=0.0,
                  company_id=cid, created_by=uid)  # todo lo demas NULL (category, status, fechas, stock...)
    vid = _insert("product_variants", product_id=pid, sku="V-LEG", name="")  # nombre vacio y resto NULL
    mid = _insert("inventory_movements", product_id=pid, movement_type="adjustment", quantity=0.0,
                  unit_cost=-1.0, reference="R" * 100)
    return pid, vid, mid


def test_legacy_product_with_nulls_is_listed_with_nulls(client, user, legacy):
    h, _, _ = user
    pid, vid, _ = legacy
    listed = _list(client, h)
    assert pid in listed
    d = listed[pid]
    assert d["price"] == 0.0 and d["name"] == "Producto antiguo"
    for k in ("description", "cost", "tax_rate", "track_inventory", "quantity_on_hand", "low_stock_threshold",
              "category", "status", "created_at", "updated_at"):
        assert d[k] is None, (k, d[k])

    one = client.get(f"{API}/products/{pid}", headers=h)
    assert one.status_code == 200, one.text
    data = one.json()["data"]
    assert data["quantity_on_hand"] is None and data["category"] is None
    v = {x["id"]: x for x in data["variants"]}[vid]
    assert v["name"] == ""
    for k in ("price_override", "cost_override", "quantity_on_hand", "created_at", "updated_at"):
        assert v[k] is None, (k, v[k])


def test_legacy_movement_is_listed(client, user, legacy):
    h, _, _ = user
    pid, _, mid = legacy
    for url in (f"{API}/products/{pid}/inventory/movements", f"{API}/products/movements"):
        r = client.get(url, headers=h)
        assert r.status_code == 200, (url, r.text)
        m = {x["id"]: x for x in r.json()}[mid]
        assert (m["quantity"], m["unit_cost"], m["movement_type"]) == (0.0, -1.0, "adjustment")
        assert m["created_at"] is None and m["variant_id"] is None


def test_other_company_does_not_see_legacy_rows(client, other, legacy):
    h, _, _ = other
    pid, _, mid = legacy
    assert pid not in _list(client, h)
    assert client.get(f"{API}/products/{pid}", headers=h).status_code == 404
    assert client.get(f"{API}/products/{pid}/inventory/movements", headers=h).status_code == 404
    r = client.get(f"{API}/products/movements", headers=h)
    assert r.status_code == 200 and mid not in {x["id"] for x in r.json()}


# ---------------------------------------------------------------------------- 3. la ENTRADA sigue validando

def _body(**over):
    body = {"sku": f"SKU-{uuid.uuid4().hex[:8]}", "name": "Producto", "price": 5.0}
    body.update(over)
    return body


@pytest.mark.parametrize("over,field", [
    ({"price": -0.01}, "price"),
    ({"name": ""}, "name"),
    ({"sku": ""}, "sku"),
    ({"name": None}, "name"),
    ({"tax_rate": 101}, "tax_rate"),
    ({"cost": -1}, "cost"),
    ({"quantity_on_hand": -1}, "quantity_on_hand"),
    ({"category": "food"}, "category"),
])
def test_create_still_rejects_invalid(client, user, over, field):
    h, _, _ = user
    r = client.post(f"{API}/products/", headers=h, json=_body(**over))
    assert r.status_code == 422, r.text
    assert any(field in [str(p) for p in e.get("loc", [])] for e in r.json()["detail"]), r.text


def test_create_rejects_missing_price(client, user):
    h, _, _ = user
    body = _body()
    body.pop("price")
    assert client.post(f"{API}/products/", headers=h, json=body).status_code == 422


def test_empty_description_is_still_accepted(client, user):
    """La descripcion es opcional (columna NULL-able, sin min_length): no se convierte en obligatoria."""
    h, _, _ = user
    r = client.post(f"{API}/products/", headers=h, json=_body(description=""))
    assert r.status_code == 201, r.text
    assert r.json()["data"]["description"] == ""


def test_update_price_rules(client, user):
    h, _, _ = user
    r = client.post(f"{API}/products/", headers=h, json=_body())
    assert r.status_code == 201, r.text
    pid = r.json()["data"]["id"]
    assert client.put(f"{API}/products/{pid}", headers=h, json={"price": -1}).status_code == 422
    assert client.put(f"{API}/products/{pid}", headers=h, json={"name": ""}).status_code == 422
    r = client.put(f"{API}/products/{pid}", headers=h, json={"price": 0})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["price"] == 0.0


def test_variant_price_rules(client, user):
    h, _, _ = user
    r = client.post(f"{API}/products/", headers=h, json=_body())
    pid = r.json()["data"]["id"]
    bad = client.post(f"{API}/products/{pid}/variants", headers=h, json={"sku": "V1", "name": "Rojo",
                                                                          "price_override": -1})
    assert bad.status_code == 422, bad.text
    assert client.post(f"{API}/products/{pid}/variants", headers=h,
                       json={"sku": "V2", "name": ""}).status_code == 422
    ok = client.post(f"{API}/products/{pid}/variants", headers=h, json={"sku": "V3", "name": "Muestra",
                                                                         "price_override": 0})
    assert ok.status_code == 201, ok.text
    assert ok.json()["price_override"] == 0.0
    vid = ok.json()["id"]
    assert client.put(f"{API}/products/variants/{vid}", headers=h, json={"price_override": -2}).status_code == 422


def test_response_schemas_do_not_inherit_input_rules():
    from app.schemas.erp import (InventoryMovementBase, InventoryMovementInDB, ProductBase, ProductInDB,
                                 ProductVariantBase, ProductVariantInDB)
    assert not issubclass(ProductInDB, ProductBase)
    assert not issubclass(ProductVariantInDB, ProductVariantBase)
    assert not issubclass(InventoryMovementInDB, InventoryMovementBase)
    m = ProductInDB.model_validate({"id": 1, "sku": "", "name": "", "price": -3.0, "tax_rate": 300.0,
                                    "variants": [{"id": 2, "price_override": 0.0}]})
    assert m.price == -3.0 and m.status is None and m.variants[0].name is None
    mv = InventoryMovementInDB.model_validate({"id": 1, "quantity": 0.0, "unit_cost": -1.0, "reference": "x" * 300})
    assert mv.quantity == 0.0
