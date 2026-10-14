"""GET /api/v1/files/{id}/url — la firma que usa el frontend para <video>/<img>/enlaces.

El vídeo de PERSEO se entrega pidiendo esta URL firmada con Authorization en cabecera.
Se comprueba que: pasa por THALOS, exige sesión real, y un usuario de otra empresa NO obtiene
la firma (404 sin revelar que existe, evento THALOS critico). El cliente S3 es un doble en
memoria SOLO en el test; los endpoints, la BD y THALOS son los reales.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.core.config import settings
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.company import Company, UserCompany
from app.models.stored_file import StoredFile
from app.models.thalos_security_event import ThalosSecurityEvent
from app.models.user import User
from services import object_storage
from services.thalos_request_guard_v1 import route_is_thalos_covered

MP4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2" + b"\x00" * 64


class _FakeR2:
    def __init__(self) -> None:
        self.objects: Dict[str, Dict[str, Any]] = {}

    def put_object(self, *, Bucket, Key, Body, ContentType, Metadata):
        self.objects[Key] = {"body": Body, "ct": ContentType}

    def generate_presigned_url(self, op, *, Params, ExpiresIn):
        return f"https://r2.test/{Params['Key']}?exp={ExpiresIn}&sig=x"


@pytest.fixture()
def r2(monkeypatch):
    fake = _FakeR2()
    for name, value in (
        ("R2_ACCOUNT_ID", "acc"),
        ("R2_ACCESS_KEY_ID", "key"),
        ("R2_SECRET_ACCESS_KEY", "secret"),
        ("R2_BUCKET", "zeus-test"),
    ):
        monkeypatch.setattr(settings, name, value, raising=False)
    monkeypatch.setattr(object_storage, "_build_client", lambda: fake)
    object_storage.reset_client_cache()
    yield fake
    object_storage.reset_client_cache()


@pytest.fixture()
def db():
    Base.metadata.create_all(
        bind=engine,
        tables=[
            User.__table__,
            Company.__table__,
            UserCompany.__table__,
            StoredFile.__table__,
            ThalosSecurityEvent.__table__,
        ],
    )
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed(db: Session, tag: str):
    suf = uuid.uuid4().hex[:8]
    company = Company(company_name=f"Sig {tag} {suf}", slug=f"sig-{tag}-{suf}")
    db.add(company)
    db.flush()
    user = User(
        email=f"sig_{tag}_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name=f"Sig {tag}",
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(UserCompany(user_id=user.id, company_id=company.id, role="owner"))
    db.commit()
    db.refresh(user)
    db.refresh(company)
    return user, company


@pytest.fixture()
def as_user():
    def _as(user: User) -> TestClient:
        app.dependency_overrides[get_current_active_user] = lambda: user
        return TestClient(app)

    yield _as
    app.dependency_overrides.pop(get_current_active_user, None)


def _route(path: str, method: str) -> APIRoute:
    for r in app.routes:
        if isinstance(r, APIRoute) and r.path_format == path and method in (r.methods or ()):
            return r
    raise AssertionError(f"ruta no encontrada: {method} {path}")


def test_signed_url_routes_pass_through_thalos():
    assert route_is_thalos_covered(_route("/api/v1/files/{file_id}/url", "GET"))
    assert route_is_thalos_covered(_route("/api/v1/files/{file_id}", "GET"))


def test_signed_url_requires_real_session(db, r2):
    owner, company = _seed(db, "anon")
    row = object_storage.store_file(
        db, company_id=company.id, user_id=owner.id, category="videos",
        filename="perseo.mp4", content_type="video/mp4", data=MP4, agent_name="PERSEO",
    )
    app.dependency_overrides.pop(get_current_active_user, None)
    resp = TestClient(app).get(f"/api/v1/files/{row.id}/url")
    assert resp.status_code == 401
    assert "r2.test" not in resp.text


def test_other_company_never_gets_the_signed_url(db, r2, as_user):
    owner, company = _seed(db, "own")
    intruder, _ = _seed(db, "intr")
    row = object_storage.store_file(
        db, company_id=company.id, user_id=owner.id, category="videos",
        filename="perseo.mp4", content_type="video/mp4", data=MP4, agent_name="PERSEO",
    )

    ok = as_user(owner).get(f"/api/v1/files/{row.id}/url")
    assert ok.status_code == 200
    body = ok.json()
    assert body["url"].startswith(f"https://r2.test/empresa/{company.id}/videos/{row.id}/")
    assert body["content_type"] == "video/mp4"
    assert body["expires_in"] == int(settings.R2_SIGNED_URL_TTL_SEC)

    denied = as_user(intruder).get(f"/api/v1/files/{row.id}/url")
    assert denied.status_code == 404
    assert "r2.test" not in denied.text and row.object_key not in denied.text

    ev = (
        db.query(ThalosSecurityEvent)
        .filter(ThalosSecurityEvent.event_type == "file_access_denied")
        .order_by(ThalosSecurityEvent.id.desc())
        .first()
    )
    assert ev is not None and ev.severity == "critical"
    details = json.loads(ev.details_json or "{}")
    assert details.get("reason") == "other_company"
    assert details.get("path") == f"/api/v1/files/{row.id}/url"
