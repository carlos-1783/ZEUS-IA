"""POST /scan/qr con company_id de OTRA empresa -> 403 antes de escribir nada.

Antes services/scan_flow_service_v1._company_id usaba el company_id del cliente tal cual: un usuario de la
empresa A podia crear clientes, facturas, eventos de escaneo o aprobaciones en la empresa B (comprobado con la
app conectada como postgres). Ahora solo se acepta una empresa del propio usuario; sin company_id se usa su
empresa primaria como siempre. Flujo HTTP real (registro, login, THALOS) sobre la BD desechable de tests.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.base import SessionLocal
from app.main import app

API = "/api/v1"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _account(c: TestClient, tag: str):
    suf = uuid.uuid4().hex[:8]
    p = {"email": f"scanajena_{tag}_{suf}@example.com", "password": "TestPass1", "full_name": f"Scan {tag}",
         "phone": "612345678", "company_name": f"Scan {tag} {suf}", "business_type": "restaurant"}
    r = c.post(f"{API}/auth/register", json=p)
    assert r.status_code == 201, r.text
    cid = r.json()["company_id"]
    tok = c.post(f"{API}/auth/login", data={"username": p["email"], "password": p["password"]}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}, cid


def _rows(cid: int) -> dict:
    db = SessionLocal()
    try:
        return {t: db.execute(text(f"SELECT count(*) FROM {t} WHERE company_id = :c"), {"c": cid}).scalar()
                for t in ("customers", "invoices", "scan_events", "zeus_pending_approvals", "cashflow_ledger")}
    finally:
        db.close()


def _qr(amount: str) -> str:
    return f"ZEUS|Cliente {uuid.uuid4().hex[:6]}|{amount}|EUR|q{uuid.uuid4().hex[:6]}@example.com"


@pytest.mark.parametrize("amount", ["12.10", "750.00"])  # rama directa (<500) y rama con aprobacion (>=500)
def test_qr_into_other_company_is_403_and_writes_nothing(client, amount):
    ha, cid_a = _account(client, "a")
    _, cid_b = _account(client, "b")
    before_b, before_a = _rows(cid_b), _rows(cid_a)
    r = client.post(f"{API}/scan/qr", headers=ha, json={"data": _qr(amount), "company_id": cid_b})
    assert r.status_code == 403, r.text
    assert _rows(cid_b) == before_b
    assert _rows(cid_a) == before_a


def test_qr_with_own_company_or_without_company_still_works(client):
    ha, cid_a = _account(client, "own")
    r = client.post(f"{API}/scan/qr", headers=ha, json={"data": _qr("12.10"), "company_id": cid_a})
    assert r.status_code == 200, r.text
    r = client.post(f"{API}/scan/qr", headers=ha, json={"data": _qr("12.10")})
    assert r.status_code == 200, r.text
    assert _rows(cid_a)["scan_events"] == 2


def test_qr_with_nonexistent_company_is_403(client):
    ha, _ = _account(client, "ghost")
    r = client.post(f"{API}/scan/qr", headers=ha, json={"data": _qr("12.10"), "company_id": 987654321})
    assert r.status_code == 403, r.text
