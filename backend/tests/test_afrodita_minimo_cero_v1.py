"""AFRODITA: un minimo de stock 0 (o NULL) significa «sin minimo», nunca «bajo minimos», en TODAS las vistas.

Antes company_inventory_status ya trataba 0 como «sin minimo», pero merge_products_view (GET
/afrodita/ops/v1/inventory, warehouse_summary) y el filtro GET /products/?low_stock=true comparaban
`stock <= minimo` tal cual: un producto con stock 0 y minimo 0 salia «bajo minimos» en unas vistas y no en
otras. Ahora todas usan la misma regla (minimo > 0 para poder estar bajo minimos). Control: minimo 5 con
stock 3 sigue siendo «bajo minimos» en todas.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.base import SessionLocal
from app.main import app
from app.models.erp import Product, ProductCategory, ProductStatus
from app.models.user import User
from services.afrodita_ops_service_v1 import company_inventory_status, merge_products_view, warehouse_summary

API = "/api/v1"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def setup(client):
    suf = uuid.uuid4().hex[:8]
    p = {"email": f"afromin0_{suf}@example.com", "password": "TestPass1", "full_name": "Min0",
         "phone": "612345678", "company_name": f"Min0 {suf}", "business_type": "restaurant"}
    r = client.post(f"{API}/auth/register", json=p)
    assert r.status_code == 201, r.text
    cid = r.json()["company_id"]
    tok = client.post(f"{API}/auth/login", data={"username": p["email"], "password": p["password"]}).json()["access_token"]
    db = SessionLocal()
    names = {}
    try:
        for key, qty, thr in (("cero_cero", 0.0, 0.0), ("stock_cero_min_null", 0.0, None),
                              ("tres_min_cero", 3.0, 0.0), ("control_tres_min_cinco", 3.0, 5.0)):
            name = f"{key}-{suf}"
            prod = Product(company_id=cid, sku=f"M0-{uuid.uuid4().hex[:8]}", name=name, price=1.0,
                           track_inventory=True, quantity_on_hand=qty, low_stock_threshold=thr if thr is not None else 0.0,
                           category=ProductCategory.GOODS, status=ProductStatus.ACTIVE)
            db.add(prod)
            db.commit()
            if thr is None:
                db.execute(text("UPDATE products SET low_stock_threshold = NULL WHERE id = :i"), {"i": prod.id})
                db.commit()
            names[key] = name
        user_id = r.json()["user_id"]
    finally:
        db.close()
    return {"h": {"Authorization": f"Bearer {tok}"}, "cid": cid, "names": names, "user_id": user_id}


NO_MIN = ("cero_cero", "stock_cero_min_null", "tres_min_cero")


def test_merged_view_and_warehouse(setup):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == setup["user_id"]).first()
        items = {i["name"]: i for i in merge_products_view(db, user)["items"]}
        low_names = {i["name"] for i in warehouse_summary(db, user)["low_stock_items"]}
    finally:
        db.close()
    for key in NO_MIN:
        assert items[setup["names"][key]]["low_stock"] is False, key
        assert setup["names"][key] not in low_names, key
    assert items[setup["names"]["control_tres_min_cinco"]]["low_stock"] is True
    assert setup["names"]["control_tres_min_cinco"] in low_names


def test_company_inventory_status(setup):
    db = SessionLocal()
    try:
        inv = company_inventory_status(db, setup["cid"])
    finally:
        db.close()
    low_names = {i["name"] for i in inv["low_stock_items"]}
    by_name = {i["name"]: i for i in inv["items"]}
    for key in NO_MIN:
        assert setup["names"][key] not in low_names, key
        assert by_name[setup["names"][key]]["min_stock"] is None, key
    assert setup["names"]["control_tres_min_cinco"] in low_names


def test_http_views(client, setup):
    inv = client.get(f"{API}/afrodita/ops/v1/inventory", headers=setup["h"])
    assert inv.status_code == 200, inv.text
    items = {i["name"]: i for i in inv.json()["items"]}
    lst = client.get(f"{API}/products/", headers=setup["h"], params={"low_stock": "true", "limit": 100})
    assert lst.status_code == 200, lst.text
    low_names = {p["name"] for p in lst.json()["data"]}
    for key in NO_MIN:
        assert items[setup["names"][key]]["low_stock"] is False, key
        assert setup["names"][key] not in low_names, key
    assert items[setup["names"]["control_tres_min_cinco"]]["low_stock"] is True
    assert setup["names"]["control_tres_min_cinco"] in low_names
