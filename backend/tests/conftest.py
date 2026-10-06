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


class _FakeSendGridResponse:
    status_code = 202
    headers = {"X-Message-Id": "test-message-id"}


class _FakeSendGridClient:
    """Sustituye SOLO al cliente externo de SendGrid: no abre red."""

    def __init__(self):
        self.sent = []

    def send(self, message):
        self.sent.append(message)
        return _FakeSendGridResponse()


class _FakeTwilioMessage:
    sid = "SMtest000000000000000000000000000"
    status = "queued"


class _FakeTwilioMessages:
    def __init__(self):
        self.created = []

    def create(self, **kwargs):
        self.created.append(kwargs)
        return _FakeTwilioMessage()


class _FakeTwilioClient:
    def __init__(self):
        self.messages = _FakeTwilioMessages()


@pytest.fixture(scope="module", autouse=True)
def no_external_messaging():
    """Autouse en toda la suite: ningun test debe alcanzar SendGrid/Twilio reales. Aisla de SendGrid/Twilio reales (DNS y envios con credenciales del entorno).

    Solo reemplaza `client` en los singletons email_service / whatsapp_service; el resto de
    la logica (flags, registro de actividad, resultado) sigue ejecutandose igual."""
    from services.email_service import email_service
    from services.whatsapp_service import whatsapp_service

    old_email, old_wa = email_service.client, whatsapp_service.client
    email_service.client = _FakeSendGridClient()
    whatsapp_service.client = _FakeTwilioClient()
    try:
        yield
    finally:
        email_service.client, whatsapp_service.client = old_email, old_wa


@pytest.fixture(autouse=True)
def no_real_classifier_model(monkeypatch):
    """J8b: ningun test alcanza el modelo real del clasificador de JARVIS (aunque otro test deje una
    OPENAI_API_KEY en settings). Sin modelo rige el criterio estricto J8. Los tests del clasificador
    inyectan su propio cliente simulado con monkeypatch (se aplica despues de este fixture)."""
    import services.jarvis_model_comprehension as mc

    monkeypatch.setattr(mc, "get_client", lambda: None)
