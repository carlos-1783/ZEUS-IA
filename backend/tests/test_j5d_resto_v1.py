"""JARVIS J5d-resto: SKU por empresa (no global), void de factura con scope de
tenant, y reglas de negocio sobre pagos (VOID / sobrepago).

Tres puntos cubiertos:
  1. products: UniqueConstraint(company_id, sku) en vez de UNIQUE(sku) global,
     y la comprobacion del endpoint acotada a la empresa del usuario (ya no
     hay oraculo de enumeracion cruzada entre empresas).
  2. invoices: /void ya usaba get_invoice_orm_or_404 (scope de tenant) --
     se confirma aqui con un test explicito (defensa en profundidad).
  3. invoices: /payments rechaza pagos sobre una factura VOID y rechaza
     sobrepago (amount_paid > total), sin romper el pago normal valido.

NOTA sobre fixtures: las dos empresas (A y B) se registran UNA SOLA VEZ para
todo el modulo (fixtures `scope="module"`), no una vez por test. El endpoint
/auth/register tiene un rate limit estricto (10 req/min/IP, ver
app/core/security_middleware.py::_bucket_and_limit) pensado para una unica
cuenta real por minuto, no para una suite de tests que registra decenas de
cuentas efimeras seguidas -- registrar solo 2 veces evita skips por 429
ajenos a la logica que este fichero quiere probar.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.base import SessionLocal
from app.main import app
from app.models.erp import Invoice, InvoiceStatus

pytestmark = pytest.mark.usefixtures("no_external_messaging")
API = settings.API_V1_STR


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _register_and_login(client):
    suf = uuid.uuid4().hex[:10]
    payload = {
        "email": f"j5dresto_{suf}@example.com", "password": "TestPass1",
        "full_name": "Titular J5dResto", "phone": "612345678",
        "company_name": f"Empresa J5dResto {suf}", "business_type": "restaurant",
    }
    r = client.post(f"{API}/auth/register", json=payload)
    if r.status_code != 201:
        pytest.skip(f"Registro no disponible: {r.status_code}")
    login = client.post(f"{API}/auth/login", data={"username": payload["email"], "password": payload["password"]})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.fixture(scope="module")
def h_a(client):
    """Empresa A: registrada una sola vez para todo el modulo."""
    return _register_and_login(client)


@pytest.fixture(scope="module")
def h_b(client):
    """Empresa B: registrada una sola vez para todo el modulo."""
    return _register_and_login(client)


def _product_payload(sku):
    return {
        "sku": sku, "name": f"Producto {sku}", "price": 10.0,
        "tax_rate": 0.0, "category": "goods", "status": "active",
    }


def _create_invoice(client, h):
    c = client.post(f"{API}/customers", headers=h, json={
        "name": "Cliente Real Test", "email": f"cli_{uuid.uuid4().hex[:8]}@example.com",
    })
    assert c.status_code == 201, c.text
    r = client.post(f"{API}/invoices/", headers=h, json={
        "customer_id": c.json()["data"]["id"], "invoice_type": "invoice", "status": "draft", "issue_date": "2026-01-10",
        "items": [{"description": "Servicio", "quantity": 2, "unit_price": 50.0, "tax_rate": 21.0}],
    })
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


def _db_status(inv_id):
    db = SessionLocal()
    try:
        return db.query(Invoice).filter(Invoice.id == inv_id).one().status
    finally:
        db.close()


# --- Punto 1: SKU por empresa, no global -----------------------------------

def test_sku_shared_between_companies_is_allowed(client, h_a, h_b):
    """Decision de negocio adoptada por el cambio ya hecho (migracion 0062 +
    erp.py): dos empresas distintas SI pueden usar el mismo SKU. B crea el
    SKU primero; A debe poder crear el mismo SKU sin que la API se lo impida
    (y sin filtrar que existe en B)."""
    sku = f"SKU-{uuid.uuid4().hex[:8]}"

    r_b = client.post(f"{API}/products/", headers=h_b, json=_product_payload(sku))
    assert r_b.status_code == 201, r_b.text

    r_a = client.post(f"{API}/products/", headers=h_a, json=_product_payload(sku))
    assert r_a.status_code == 201, r_a.text
    assert r_a.json()["data"]["sku"] == sku


def test_sku_duplicate_within_same_company_rejected(client, h_a):
    """Crear el mismo SKU dos veces DENTRO de la misma empresa debe fallar."""
    sku = f"SKU-{uuid.uuid4().hex[:8]}"

    r1 = client.post(f"{API}/products/", headers=h_a, json=_product_payload(sku))
    assert r1.status_code == 201, r1.text

    r2 = client.post(f"{API}/products/", headers=h_a, json=_product_payload(sku))
    assert r2.status_code == 400, r2.text


def test_sku_update_within_same_company_rejected_but_cross_company_allowed(client, h_a, h_b):
    """PUT de producto: mismo criterio que en create (acotado a empresa)."""
    sku_a1 = f"SKU-{uuid.uuid4().hex[:8]}"
    sku_a2 = f"SKU-{uuid.uuid4().hex[:8]}"
    sku_b = f"SKU-{uuid.uuid4().hex[:8]}"

    p_a1 = client.post(f"{API}/products/", headers=h_a, json=_product_payload(sku_a1))
    assert p_a1.status_code == 201, p_a1.text
    p_a2 = client.post(f"{API}/products/", headers=h_a, json=_product_payload(sku_a2))
    assert p_a2.status_code == 201, p_a2.text
    p_b = client.post(f"{API}/products/", headers=h_b, json=_product_payload(sku_b))
    assert p_b.status_code == 201, p_b.text

    # A intenta renombrar su producto 2 al SKU de su propio producto 1 -> 400
    upd_same_company = client.put(
        f"{API}/products/{p_a2.json()['data']['id']}", headers=h_a, json={"sku": sku_a1},
    )
    assert upd_same_company.status_code == 400, upd_same_company.text

    # A intenta renombrar su producto 2 al SKU usado por B -> permitido
    upd_cross_company = client.put(
        f"{API}/products/{p_a2.json()['data']['id']}", headers=h_a, json={"sku": sku_b},
    )
    assert upd_cross_company.status_code == 200, upd_cross_company.text


def test_variant_sku_duplicate_within_same_product_rejected_but_allowed_on_other_product(client, h_a):
    """UniqueConstraint(product_id, sku) en ProductVariant: el duplicado solo
    importa DENTRO del mismo producto, no entre productos (ni siquiera de la
    misma empresa)."""
    p1 = client.post(f"{API}/products/", headers=h_a, json=_product_payload(f"SKU-{uuid.uuid4().hex[:8]}"))
    assert p1.status_code == 201, p1.text
    p2 = client.post(f"{API}/products/", headers=h_a, json=_product_payload(f"SKU-{uuid.uuid4().hex[:8]}"))
    assert p2.status_code == 201, p2.text

    variant_sku = f"VAR-{uuid.uuid4().hex[:8]}"
    v1 = client.post(f"{API}/products/{p1.json()['data']['id']}/variants", headers=h_a, json={
        "sku": variant_sku, "name": "Variante 1",
    })
    assert v1.status_code == 201, v1.text

    # Mismo SKU en el MISMO producto -> rechazado
    dup = client.post(f"{API}/products/{p1.json()['data']['id']}/variants", headers=h_a, json={
        "sku": variant_sku, "name": "Variante Duplicada",
    })
    assert dup.status_code == 400, dup.text

    # Mismo SKU en OTRO producto (misma empresa) -> permitido
    other_product = client.post(f"{API}/products/{p2.json()['data']['id']}/variants", headers=h_a, json={
        "sku": variant_sku, "name": "Variante Otro Producto",
    })
    assert other_product.status_code == 201, other_product.text


# --- Punto 2: void respeta el tenant (defensa en profundidad) --------------

def test_void_other_company_404_and_owner_can_void(client, h_a, h_b):
    inv = _create_invoice(client, h_a)

    # B (ajena) no puede anular la factura de A
    r_other = client.post(f"{API}/invoices/{inv}/void", headers=h_b)
    assert r_other.status_code == 404, r_other.text
    assert _db_status(inv) == InvoiceStatus.DRAFT

    # A anula la suya sin problema
    r_owner = client.post(f"{API}/invoices/{inv}/void", headers=h_a)
    assert r_owner.status_code == 200, r_owner.text
    assert _db_status(inv) == InvoiceStatus.VOID


# --- Punto 3: pago sobre VOID / sobrepago -----------------------------------

def test_payment_on_void_invoice_rejected(client, h_a):
    inv = _create_invoice(client, h_a)
    assert client.post(f"{API}/invoices/{inv}/void", headers=h_a).status_code == 200
    assert _db_status(inv) == InvoiceStatus.VOID

    r = client.post(f"{API}/invoices/{inv}/payments", headers=h_a, json={
        "amount": 10.0, "payment_method": "cash", "status": "completed",
    })
    assert r.status_code == 409, r.text
    assert _db_status(inv) == InvoiceStatus.VOID


def test_overpayment_rejected(client, h_a):
    inv = _create_invoice(client, h_a)  # total 121.0

    r = client.post(f"{API}/invoices/{inv}/payments", headers=h_a, json={
        "amount": 500.0, "payment_method": "cash", "status": "completed",
    })
    assert r.status_code == 400, r.text
    assert _db_status(inv) == InvoiceStatus.DRAFT


def test_normal_payment_still_works_no_regression(client, h_a):
    inv = _create_invoice(client, h_a)  # total 121.0

    r = client.post(f"{API}/invoices/{inv}/payments", headers=h_a, json={
        "amount": 121.0, "payment_method": "cash", "status": "completed",
    })
    assert r.status_code == 201, r.text
    assert _db_status(inv) == InvoiceStatus.PAID


def test_partial_payment_then_overpayment_on_remainder_rejected(client, h_a):
    """amount_due se recalcula tras cada pago: un segundo pago que exceda el
    resto pendiente (no el total original) tambien debe rechazarse."""
    inv = _create_invoice(client, h_a)  # total 121.0

    r1 = client.post(f"{API}/invoices/{inv}/payments", headers=h_a, json={
        "amount": 100.0, "payment_method": "cash", "status": "completed",
    })
    assert r1.status_code == 201, r1.text
    assert _db_status(inv) == InvoiceStatus.PARTIALLY_PAID

    # Quedan 21.0 pendientes; pedir 30.0 debe fallar.
    r2 = client.post(f"{API}/invoices/{inv}/payments", headers=h_a, json={
        "amount": 30.0, "payment_method": "cash", "status": "completed",
    })
    assert r2.status_code == 400, r2.text
    assert _db_status(inv) == InvoiceStatus.PARTIALLY_PAID

    # El resto exacto (21.0) si debe aceptarse.
    r3 = client.post(f"{API}/invoices/{inv}/payments", headers=h_a, json={
        "amount": 21.0, "payment_method": "cash", "status": "completed",
    })
    assert r3.status_code == 201, r3.text
    assert _db_status(inv) == InvoiceStatus.PAID


def test_overpayment_by_one_cent_rejected_exact_remainder_accepted(client, h_a):
    """Limite exacto (hallazgo del revisor-independiente): la tolerancia del
    check de sobrepago debe ser solo la de redondeo de coma flotante (1e-6),
    nunca un margen de negocio. Resto pendiente exacto 21.00: un pago de
    21.01 (un centimo de sobrepago REAL) debe rechazarse; el pago exacto del
    resto (21.00) debe aceptarse."""
    inv = _create_invoice(client, h_a)  # total 121.0

    r1 = client.post(f"{API}/invoices/{inv}/payments", headers=h_a, json={
        "amount": 100.0, "payment_method": "cash", "status": "completed",
    })
    assert r1.status_code == 201, r1.text
    assert _db_status(inv) == InvoiceStatus.PARTIALLY_PAID

    # Quedan 21.00 pendientes exactos; 21.01 es un centimo de mas -> 400.
    r_over = client.post(f"{API}/invoices/{inv}/payments", headers=h_a, json={
        "amount": 21.01, "payment_method": "cash", "status": "completed",
    })
    assert r_over.status_code == 400, r_over.text
    assert _db_status(inv) == InvoiceStatus.PARTIALLY_PAID

    # El resto exacto (21.00) si se acepta.
    r_exact = client.post(f"{API}/invoices/{inv}/payments", headers=h_a, json={
        "amount": 21.00, "payment_method": "cash", "status": "completed",
    })
    assert r_exact.status_code == 201, r_exact.text
    assert _db_status(inv) == InvoiceStatus.PAID
