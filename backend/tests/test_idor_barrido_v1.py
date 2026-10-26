"""Barrido IDOR (ids que vienen del cliente sin comprobar que son de la empresa de la sesion).

Casos vulnerables encontrados en el barrido y cerrados (A ataca con ids de B; flujo HTTP real):
- POST /zeus-core/workspace-bootstrap con company_id de B -> 403 y ningun documento en B
  (antes guardaba el documento de configuracion en la empresa indicada).
- POST /invoices/ con una linea cuyo product_id es de B -> 404 y nada escrito (antes la linea quedaba
  apuntando al producto de otra empresa).
- POST /perseo/video/generate y /perseo/video-pro/generate con customer_id o lead_id de B -> 404 antes de
  generar ni registrar nada (antes el customer_id ajeno se guardaba en el CRM de A y el lead se ignoraba).
- resolve_tenant_company: un usuario SIN empresas ya no puede operar sobre un tenant cualquiera (403).
- POST /products/{id}/inventory/movements con la ruta de un producto propio y product_id de B en el body ->
  404 y nada escrito (antes el movimiento se creaba sobre el producto de B: InventoryMovement(**body)).
Controles: con ids propios el flujo sigue (201 / no 404).
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.security import get_password_hash
from app.db.base import SessionLocal
from app.main import app
from app.models.crm_lead import CrmLead
from app.models.customer import Customer
from app.models.user import User

API = "/api/v1"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _account(c: TestClient, tag: str):
    suf = uuid.uuid4().hex[:8]
    p = {"email": f"idor_{tag}_{suf}@example.com", "password": "TestPass1", "full_name": f"IDOR {tag}",
         "phone": "612345678", "company_name": f"IDOR {tag} {suf}", "business_type": "restaurant"}
    r = c.post(f"{API}/auth/register", json=p)
    assert r.status_code == 201, r.text
    tok = c.post(f"{API}/auth/login", data={"username": p["email"], "password": p["password"]}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}, r.json()["company_id"]


def _count(sql: str, **params) -> int:
    db = SessionLocal()
    try:
        return int(db.execute(text(sql), params).scalar() or 0)
    finally:
        db.close()


def _seed(model, **kw) -> int:
    db = SessionLocal()
    try:
        row = model(**kw)
        db.add(row)
        db.commit()
        return int(row.id)
    finally:
        db.close()


@pytest.fixture(scope="module")
def ab(client):
    ha, cid_a = _account(client, "a")
    hb, cid_b = _account(client, "b")
    return {"ha": ha, "a": cid_a, "hb": hb, "b": cid_b}


def test_workspace_bootstrap_with_other_company_is_403(client, ab):
    before = _count("SELECT count(*) FROM document_approvals WHERE company_id = :c", c=ab["b"])
    r = client.post(f"{API}/zeus-core/workspace-bootstrap", headers=ab["ha"], json={"company_id": ab["b"]})
    assert r.status_code == 403, r.text
    assert _count("SELECT count(*) FROM document_approvals WHERE company_id = :c", c=ab["b"]) == before
    own = client.post(f"{API}/zeus-core/workspace-bootstrap", headers=ab["ha"], json={"company_id": ab["a"]})
    assert own.status_code == 200, own.text


def _product(client, headers) -> int:
    r = client.post(f"{API}/products/", headers=headers,
                    json={"sku": "S" + uuid.uuid4().hex[:8], "name": "P", "price": 5, "tax_rate": 21})
    assert r.status_code in (200, 201), r.text
    return r.json()["data"]["id"]


def _customer(client, headers) -> int:
    r = client.post(f"{API}/customers", headers=headers,
                    json={"name": "Cli", "email": f"c{uuid.uuid4().hex[:6]}@example.com"})
    assert r.status_code in (200, 201), r.text
    return r.json()["data"]["id"]


def test_invoice_line_with_other_company_product_is_404_and_writes_nothing(client, ab):
    prod_b = _product(client, ab["hb"])
    cust_a = _customer(client, ab["ha"])
    inv_before = _count("SELECT count(*) FROM invoices WHERE company_id = :c", c=ab["a"])
    body = {"customer_id": cust_a, "issue_date": "2026-10-25",
            "items": [{"description": "X", "quantity": 1, "unit_price": 10.0, "tax_rate": 21.0, "product_id": prod_b}]}
    r = client.post(f"{API}/invoices/", headers=ab["ha"], json=body)
    assert r.status_code == 404, r.text
    assert _count("SELECT count(*) FROM invoices WHERE company_id = :c", c=ab["a"]) == inv_before
    assert _count("SELECT count(*) FROM invoice_items WHERE product_id = :p", p=prod_b) == 0
    body["items"][0]["product_id"] = _product(client, ab["ha"])
    assert client.post(f"{API}/invoices/", headers=ab["ha"], json=body).status_code == 201


@pytest.mark.parametrize("route", ["/perseo/video/generate", "/perseo/video-pro/generate"])
@pytest.mark.parametrize("ref", ["customer_id", "lead_id"])
def test_perseo_video_with_other_company_crm_refs_is_404(client, ab, route, ref):
    if ref == "customer_id":
        foreign = _seed(Customer, name="Cli B", company_id=ab["b"])
    else:
        foreign = _seed(CrmLead, name="Lead B", company_id=ab["b"])
    logs_before = _count("SELECT count(*) FROM crm_activity_logs WHERE company_id = :c", c=ab["a"])
    body = {"tenant_id": str(ab["a"]), "image_url": "https://example.com/x.png", ref: foreign}
    r = client.post(f"{API}{route}", headers=ab["ha"], json=body)
    assert r.status_code == 404, r.text
    assert _count("SELECT count(*) FROM crm_activity_logs WHERE company_id = :c", c=ab["a"]) == logs_before
    # control: con una referencia propia NO es 404 (sigue al resto del flujo: ejecucion/ffmpeg/etc.)
    own = _seed(Customer, name="Cli A", company_id=ab["a"]) if ref == "customer_id" else _seed(CrmLead, name="Lead A", company_id=ab["a"])
    r = client.post(f"{API}{route}", headers=ab["ha"], json={**body, ref: own})
    assert r.status_code != 404, r.text


def test_perseo_video_other_tenant_is_403(client, ab):
    r = client.post(f"{API}/perseo/video/generate", headers=ab["ha"],
                    json={"tenant_id": str(ab["b"]), "image_url": "https://example.com/x.png"})
    assert r.status_code == 403, r.text


def test_user_without_companies_cannot_pick_any_tenant(ab):
    from services.perseo_video_engine_v3 import resolve_tenant_company

    db = SessionLocal()
    try:
        u = User(email=f"idor_nocomp_{uuid.uuid4().hex[:8]}@example.com", hashed_password=get_password_hash("x"),
                 is_active=True)
        db.add(u)
        db.commit()
        with pytest.raises(HTTPException) as e:
            resolve_tenant_company(db, u, str(ab["b"]))
        assert e.value.status_code == 403
    finally:
        db.close()


def test_inventory_movement_body_product_of_other_company_is_404(client, ab):
    prod_a = _product(client, ab["ha"])
    prod_b = _product(client, ab["hb"])
    qty_b = _count("SELECT coalesce(quantity_on_hand, 0) FROM products WHERE id = :p", p=prod_b)
    moves_b = _count("SELECT count(*) FROM inventory_movements WHERE product_id = :p", p=prod_b)
    r = client.post(f"{API}/products/{prod_a}/inventory/movements", headers=ab["ha"],
                    json={"movement_type": "purchase", "product_id": prod_b, "quantity": 5})
    assert r.status_code == 404, r.text
    assert _count("SELECT count(*) FROM inventory_movements WHERE product_id = :p", p=prod_b) == moves_b
    assert _count("SELECT coalesce(quantity_on_hand, 0) FROM products WHERE id = :p", p=prod_b) == qty_b
    assert _count("SELECT count(*) FROM inventory_movements WHERE product_id = :p", p=prod_a) == 0
    own = client.post(f"{API}/products/{prod_a}/inventory/movements", headers=ab["ha"],
                      json={"movement_type": "purchase", "product_id": prod_a, "quantity": 5})
    assert own.status_code == 201, own.text
    assert _count("SELECT count(*) FROM inventory_movements WHERE product_id = :p", p=prod_a) == 1
