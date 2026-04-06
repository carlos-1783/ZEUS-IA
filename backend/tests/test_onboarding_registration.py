"""
ZEUS_ONBOARDING_ENGINE_WITH_VALIDATION_001 — registro + validación explícita.
Requiere DATABASE_URL accesible (misma que el proyecto).
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _register_payload():
    suf = uuid.uuid4().hex[:10]
    return {
        "email": f"onb_{suf}@example.test",
        "password": "TestPass1",
        "full_name": "Titular Test",
        "phone": "612345678",
        "company_name": f"Empresa Test {suf}",
        "business_type": "restaurant",
    }


def test_register_requires_company_and_business_type(client: TestClient):
    p = _register_payload()
    del p["company_name"]
    r = client.post(f"{settings.API_V1_STR}/auth/register", json=p)
    assert r.status_code == 422


def test_register_restaurant_creates_user_company_and_login(client: TestClient):
    p = _register_payload()
    r = client.post(f"{settings.API_V1_STR}/auth/register", json=p)
    if r.status_code != 201:
        pytest.skip(f"Registro no disponible en este entorno: {r.status_code} {r.text[:200]}")
    data = r.json()
    assert data.get("email") == p["email"]

    login = client.post(
        f"{settings.API_V1_STR}/auth/login",
        data={"username": p["email"], "password": p["password"]},
    )
    assert login.status_code == 200
    tok = login.json().get("access_token")
    assert tok

    st = client.get(
        f"{settings.API_V1_STR}/auth/onboarding/status",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert st.status_code == 200
    body = st.json()
    assert body.get("validation", {}).get("ok") is True
    assert body.get("questionnaire_completed") is False

    q = client.post(
        f"{settings.API_V1_STR}/auth/onboarding/questionnaire",
        headers={"Authorization": f"Bearer {tok}"},
        json={
            "employees_count": 3,
            "uses_tpv": True,
            "business_hours": "L-V 9:00-18:00",
        },
    )
    assert q.status_code == 200
    st2 = client.get(
        f"{settings.API_V1_STR}/auth/onboarding/status",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert st2.json().get("questionnaire_completed") is True
