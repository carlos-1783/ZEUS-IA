import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

@pytest.fixture(scope="module")
def test_client():
    with TestClient(app) as client:
        yield client

@pytest.fixture(scope="module")
def test_user():
    return {
        "email": "marketingdigital per,seo@gmail.com",
        "password": "Carnay19!"
    }

@pytest.fixture(scope="module")
def test_token(test_client, test_user):
    response = test_client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={
            "email": test_user["email"],
            "password": test_user["password"]
        }
    )
    assert response.status_code == 200
    return response.json()["access_token"]

@pytest.fixture(scope="module")
def authorized_client(test_client, test_token):
    test_client.headers.update({"Authorization": f"Bearer {test_token}"})
    return test_client
