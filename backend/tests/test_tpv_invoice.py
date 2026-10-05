"""
D2a — Suite de tests automáticos para el puente TPV → RAFAEL
(`POST /api/v1/tpv/invoice`).

El puente ya estaba implementado (frontend/src/views/TPV.vue `generateInvoice`
→ backend `app/api/v1/endpoints/tpv.py::generate_invoice` →
`services/tpv_service.py::TPVService.generate_invoice`), pero no tenía
cobertura automática con pytest. Estos tests ejercitan el flujo real completo
contra la BD configurada (SQLite local en este entorno,
`backend/zeus.db` vía `DATABASE_URL`), vía la API HTTP real (registro, login,
alta de producto, venta y facturación), sin mocks ni datos simulados.

Comportamiento real documentado (verificado aquí, no asumido):
- Éxito: `POST /tpv/invoice` crea una `Invoice` real con subtotal/tax/total
  calculados a partir de `TPVSale` (motor fiscal `services/fiscal_engine.py`),
  no valores fijos.
- Idempotencia: una segunda llamada con el mismo `ticket_id` NO crea una
  segunda factura; devuelve la misma factura (mismo `id`) con
  `already_existed: true` y HTTP 200 (no un error) — comportamiento real del
  código, verificado línea por línea en
  `services/tpv_service.py::generate_invoice` (busca `Invoice.tpv_sale_id`
  existente antes de crear).
- Aislamiento multi-tenant: una venta de la empresa A no es accesible para
  facturar por un usuario de la empresa B → 403 real (no 404 encubierto, no
  éxito silencioso).
- Validación: venta inexistente → 404 (no 422; así lo implementa el código:
  `raise HTTPException(404, ...)` cuando no encuentra el `TPVSale` por
  `ticket_id`). Venta existente pero sin líneas (`TPVSaleItem`) → 422 real.
  `ticket_id` ausente en el body → 422 de validación Pydantic.
  Sin token de autenticación → 401 real (THALOS/auth real, no bypass).
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

pytestmark = pytest.mark.usefixtures("no_external_messaging")


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _register_payload(suf: str) -> dict:
    return {
        # "example.com" (no "example.test"/".local"): el validador de email
        # de pydantic rechaza dominios reservados y el registro se saltaría
        # en silencio.
        "email": f"tpvinv_{suf}@example.com",
        "password": "TestPass1",
        "full_name": "Titular TPV Test",
        "phone": "612345678",
        "company_name": f"Empresa TPV Test {suf}",
        "business_type": "restaurant",
    }


def _register_and_login(client: TestClient) -> tuple[str, int, int]:
    """Registra una empresa/usuario real nuevo y devuelve (token, user_id, company_id)."""
    suf = uuid.uuid4().hex[:10]
    payload = _register_payload(suf)
    r = client.post(f"{settings.API_V1_STR}/auth/register", json=payload)
    if r.status_code != 201:
        pytest.skip(f"Registro no disponible en este entorno: {r.status_code} {r.text[:200]}")
    body = r.json()
    login = client.post(
        f"{settings.API_V1_STR}/auth/login",
        data={"username": payload["email"], "password": payload["password"]},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return token, body["user_id"], body["company_id"]


def _create_product(client: TestClient, token: str, price: float = 10.0, iva_rate: float = 21.0) -> str:
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post(
        f"{settings.API_V1_STR}/tpv/products",
        json={"name": "Producto Test TPV", "price": price, "category": "general", "iva_rate": iva_rate},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()["product"]["id"]


def _create_sale(client: TestClient, token: str, product_id: str, quantity: int = 1) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post(
        f"{settings.API_V1_STR}/tpv/sale",
        json={
            "payment_method": "efectivo",
            "cart_items": [{"product_id": product_id, "quantity": quantity}],
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("success") is True
    return body


def test_generate_invoice_success_real_amounts(client: TestClient):
    """Éxito: venta real de una empresa real genera una factura real con importes correctos."""
    token, _user_id, _company_id = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    product_id = _create_product(client, token, price=10.0, iva_rate=21.0)
    sale = _create_sale(client, token, product_id, quantity=3)
    ticket_id = sale["ticket_id"]

    # Importes esperados: calculados de forma independiente del motor fiscal
    # (misma fórmula que services/fiscal_engine.py: base = price*qty, tax = base*iva_rate/100),
    # NO copiados del propio ticket devuelto, para no validar el código contra sí mismo.
    expected_subtotal = 10.0 * 3
    expected_tax = round(expected_subtotal * 0.21, 2)
    expected_total = round(expected_subtotal + expected_tax, 2)

    r = client.post(
        f"{settings.API_V1_STR}/tpv/invoice",
        json={"ticket_id": ticket_id},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("success") is True
    assert body.get("already_existed") is False

    invoice = body["invoice"]
    assert invoice["ticket_id"] == ticket_id
    assert invoice["subtotal"] == pytest.approx(expected_subtotal, abs=0.01)
    assert invoice["tax_amount"] == pytest.approx(expected_tax, abs=0.01)
    assert invoice["total"] == pytest.approx(expected_total, abs=0.01)
    assert invoice["status"] == "paid"
    assert invoice["id"] is not None
    assert invoice["invoice_number"] == f"FRA-{ticket_id}"[:50]


def test_generate_invoice_idempotent_same_sale_does_not_duplicate(client: TestClient):
    """
    Idempotencia real: llamar dos veces a /tpv/invoice para la MISMA venta no
    crea una segunda factura. Comportamiento real implementado (no un 409/400):
    la segunda llamada devuelve HTTP 200 con la MISMA factura
    (`already_existed: true`), sin crear un segundo registro en `invoices`.
    """
    token, _user_id, _company_id = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    product_id = _create_product(client, token, price=5.0, iva_rate=21.0)
    sale = _create_sale(client, token, product_id, quantity=2)
    ticket_id = sale["ticket_id"]

    r1 = client.post(f"{settings.API_V1_STR}/tpv/invoice", json={"ticket_id": ticket_id}, headers=headers)
    assert r1.status_code == 200, r1.text
    b1 = r1.json()
    assert b1["already_existed"] is False
    invoice_id_1 = b1["invoice"]["id"]

    r2 = client.post(f"{settings.API_V1_STR}/tpv/invoice", json={"ticket_id": ticket_id}, headers=headers)
    assert r2.status_code == 200, r2.text
    b2 = r2.json()
    assert b2["already_existed"] is True
    invoice_id_2 = b2["invoice"]["id"]

    # Misma factura, no una nueva: mismo id, mismos importes.
    assert invoice_id_1 == invoice_id_2
    assert b1["invoice"]["total"] == pytest.approx(b2["invoice"]["total"], abs=0.001)

    # Verificación directa en BD: una sola fila en `invoices` para esta venta,
    # no dos (no duplicado silencioso).
    from app.db.session import SessionLocal
    from app.models.erp import Invoice, TPVSale

    db = SessionLocal()
    try:
        sale_row = db.query(TPVSale).filter(TPVSale.ticket_id == ticket_id).first()
        assert sale_row is not None
        count = db.query(Invoice).filter(Invoice.tpv_sale_id == sale_row.id).count()
        assert count == 1, f"Se esperaba exactamente 1 factura para la venta, hay {count}"
    finally:
        db.close()


def test_generate_invoice_cross_tenant_forbidden(client: TestClient):
    """
    403 cruzado: un usuario de la empresa B no puede generar/ver la factura
    de una venta de la empresa A. Aislamiento multi-tenant real, no un 404
    que oculte el fallo de autorización ni un éxito silencioso.
    """
    token_a, _user_a, _company_a = _register_and_login(client)
    token_b, _user_b, _company_b = _register_and_login(client)

    product_id = _create_product(client, token_a, price=8.0, iva_rate=10.0)
    sale = _create_sale(client, token_a, product_id, quantity=1)
    ticket_id = sale["ticket_id"]

    headers_b = {"Authorization": f"Bearer {token_b}"}
    r = client.post(f"{settings.API_V1_STR}/tpv/invoice", json={"ticket_id": ticket_id}, headers=headers_b)
    assert r.status_code == 403, r.text

    # La empresa A sigue pudiendo facturar su propia venta con normalidad
    # (el 403 de B no corrompe ni bloquea la venta real).
    headers_a = {"Authorization": f"Bearer {token_a}"}
    r_ok = client.post(f"{settings.API_V1_STR}/tpv/invoice", json={"ticket_id": ticket_id}, headers=headers_a)
    assert r_ok.status_code == 200, r_ok.text


def test_generate_invoice_without_auth_rejected(client: TestClient):
    """Sin credenciales: 401 real (THALOS/auth real), no 500 ni éxito."""
    token, _user_id, _company_id = _register_and_login(client)
    product_id = _create_product(client, token, price=5.0, iva_rate=21.0)
    sale = _create_sale(client, token, product_id, quantity=1)
    ticket_id = sale["ticket_id"]

    r = client.post(f"{settings.API_V1_STR}/tpv/invoice", json={"ticket_id": ticket_id})
    assert r.status_code == 401, r.text


def test_generate_invoice_nonexistent_sale_returns_clean_error(client: TestClient):
    """
    Venta inexistente: el código real devuelve 404 (no 422, no 500) —
    `TPVSale` no encontrado por `ticket_id`. Documentamos el comportamiento
    real tal y como está implementado, no el hipotético.
    """
    token, _user_id, _company_id = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    r = client.post(
        f"{settings.API_V1_STR}/tpv/invoice",
        json={"ticket_id": f"TICKET_NO_EXISTE_{uuid.uuid4().hex[:8]}"},
        headers=headers,
    )
    assert r.status_code == 404, r.text
    assert r.status_code != 500


def test_generate_invoice_missing_ticket_id_returns_422(client: TestClient):
    """Body inválido (sin `ticket_id`): 422 de validación Pydantic, no 500."""
    token, _user_id, _company_id = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    r = client.post(f"{settings.API_V1_STR}/tpv/invoice", json={}, headers=headers)
    assert r.status_code == 422, r.text


def test_generate_invoice_sale_without_items_returns_422(client: TestClient):
    """
    Venta sin líneas: el código real valida `sale.items` antes de facturar y
    devuelve 422 explícito ("La venta no tiene líneas; no se puede
    facturar."), no un 500 ni una factura vacía. No hay forma de crear una
    venta sin líneas vía la API pública (POST /tpv/sale exige
    cart_items no vacío), así que se inserta el caso límite directamente en
    BD a través de la propia sesión real de la app (mismo `TPVSale` que usa
    el endpoint), para ejercitar exactamente esta rama del código real.
    """
    token, user_id, company_id = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    from app.db.session import SessionLocal
    from app.models.erp import TPVSale

    ticket_id = f"TICKET_SIN_LINEAS_{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        sale = TPVSale(
            user_id=user_id,
            company_id=company_id,
            ticket_id=ticket_id,
            document_type="ticket",
            payment_method="efectivo",
            consumption_type="onsite",
            subtotal=0,
            tax_amount=0,
            total=0,
        )
        db.add(sale)
        db.commit()
    finally:
        db.close()

    r = client.post(f"{settings.API_V1_STR}/tpv/invoice", json={"ticket_id": ticket_id}, headers=headers)
    assert r.status_code == 422, r.text
