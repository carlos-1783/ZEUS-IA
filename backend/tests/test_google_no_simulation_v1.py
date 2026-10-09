"""J5d: el servicio Google ya no devuelve success=True simulado; el endpoint de
Drive no lee rutas del servidor enviadas por el cliente y responde 501."""
import asyncio
import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from services.google_service import GoogleService, google_service

pytestmark = pytest.mark.usefixtures("no_external_messaging")
API = settings.API_V1_STR


def _configured_service():
    svc = GoogleService()
    svc.configured_services = ["calendar", "gmail", "drive", "sheets"]
    return svc


def _all_calls(svc):
    now = datetime.utcnow()
    return [
        svc.create_calendar_event("x", now, now),
        svc.list_calendar_events(now, now),
        svc.send_gmail("a@example.com", "s", "b"),
        svc.read_gmail_inbox(),
        svc.upload_to_drive("/etc/passwd"),
        svc.list_drive_files(),
        svc.create_spreadsheet("t"),
        svc.write_to_sheet("id", "A1", [[1]]),
        svc.read_from_sheet("id", "A1"),
    ]


def test_service_never_returns_fake_success_even_if_configured():
    svc = _configured_service()

    async def run():
        return [await c for c in _all_calls(svc)]

    for r in asyncio.run(run()):
        assert r["success"] is False
        assert r["not_implemented"] is True
        assert r["status_code"] == 501
        assert "simulated" not in str(r).lower()


def test_service_unconfigured_returns_501_error():
    svc = GoogleService()
    svc.configured_services = []

    async def run():
        return [await c for c in _all_calls(svc)]

    for r in asyncio.run(run()):
        assert r["success"] is False and r["status_code"] == 501


def test_drive_upload_endpoint_501_and_ignores_client_file_path(monkeypatch):
    captured = {}
    real = google_service.upload_to_drive

    async def spy(file_path, folder_id=None, file_name=None):
        captured["file_path"] = file_path
        return await real(file_path, folder_id, file_name)

    monkeypatch.setattr(google_service, "upload_to_drive", spy)
    monkeypatch.setattr(google_service, "configured_services", ["drive"])
    with TestClient(app) as client:
        suf = uuid.uuid4().hex[:10]
        p = {"email": f"gdrv_{suf}@example.com", "password": "TestPass1", "full_name": "G D",
             "phone": "612345678", "company_name": f"Emp G {suf}", "business_type": "restaurant"}
        if client.post(f"{API}/auth/register", json=p).status_code != 201:
            pytest.skip("registro no disponible")
        tok = client.post(f"{API}/auth/login", data={"username": p["email"], "password": p["password"]}).json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        r = client.post(f"{API}/google/drive/upload", headers=h,
                        json={"file_path": "/etc/passwd", "file_name": "x.txt"})
        # 501 (no implementado) o 403 si THALOS/rol lo restringe; nunca 200 simulado
        assert r.status_code in (501, 403), r.text
        assert "simulated" not in r.text.lower()
        if r.status_code == 501:
            assert captured["file_path"] == ""
        # sin credenciales -> 401
        assert client.post(f"{API}/google/drive/upload", json={}).status_code in (401, 403)
