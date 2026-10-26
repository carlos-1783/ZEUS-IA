"""GET /cashflow/balance y /cashflow/summary con ?company_id de OTRA empresa -> 403.

Antes `cid = company_id or primaria`: el usuario de A leia el saldo y los movimientos reales de B (app como
postgres) o recibia un 200 a cero (con RLS). Ahora la empresa sale de la sesion (crm_office_service.
resolve_company_for_user): ajena -> 403; la propia o sin parametro -> igual que antes. Flujo HTTP real.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.db.base import SessionLocal
from app.main import app
from app.models.cashflow_ledger import CashflowLedgerEntry

API = "/api/v1/cashflow"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _account(c: TestClient, tag: str, amount_in: float):
    suf = uuid.uuid4().hex[:8]
    p = {"email": f"cfajena_{tag}_{suf}@example.com", "password": "TestPass1", "full_name": f"CF {tag}",
         "phone": "612345678", "company_name": f"CF {tag} {suf}", "business_type": "restaurant"}
    r = c.post("/api/v1/auth/register", json=p)
    assert r.status_code == 201, r.text
    cid = r.json()["company_id"]
    db = SessionLocal()
    try:
        db.add(CashflowLedgerEntry(company_id=cid, amount=amount_in, direction="in", source="test_cashflow"))
        db.commit()
    finally:
        db.close()
    tok = c.post("/api/v1/auth/login", data={"username": p["email"], "password": p["password"]}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}, cid


@pytest.mark.parametrize("path", ["/balance", "/summary"])
def test_other_company_is_403(client, path):
    ha, _ = _account(client, "a", 10.0)
    _, cid_b = _account(client, "b", 999.0)
    r = client.get(f"{API}{path}", headers=ha, params={"company_id": cid_b})
    assert r.status_code == 403, r.text


def test_own_company_and_no_parameter_unchanged(client):
    ha, cid_a = _account(client, "own", 42.5)
    no_param = client.get(f"{API}/balance", headers=ha)
    own = client.get(f"{API}/balance", headers=ha, params={"company_id": cid_a})
    assert no_param.status_code == own.status_code == 200
    assert no_param.json() == own.json() == {"success": True, "company_id": cid_a, "balance": 42.5}
    s1 = client.get(f"{API}/summary", headers=ha)
    s2 = client.get(f"{API}/summary", headers=ha, params={"company_id": cid_a})
    assert s1.status_code == s2.status_code == 200 and s1.json() == s2.json()


def test_nonexistent_company_is_403(client):
    ha, _ = _account(client, "ghost", 1.0)
    assert client.get(f"{API}/balance", headers=ha, params={"company_id": 987654321}).status_code == 403
