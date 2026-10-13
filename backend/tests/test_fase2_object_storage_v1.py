"""Fase 2 / Step 1 — almacenamiento de objetos (R2) y fin de las subidas publicas en /static.

El cliente S3 se sustituye por un doble en memoria SOLO en el test (el codigo de producto
habla con R2 via boto3). Se ejercitan los endpoints HTTP reales con dos empresas reales.
"""

from __future__ import annotations

import io
import json
import uuid
from pathlib import Path
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.core.config import settings
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.company import Company, UserCompany
from app.models.customer import Customer
from app.models.stored_file import StoredFile
from app.models.thalos_security_event import ThalosSecurityEvent
from app.models.user import User
from services import object_storage

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PDF = b"%PDF-1.4\n%fake but valid header\n"


class FakeR2:
    def __init__(self) -> None:
        self.objects: Dict[str, Dict[str, Any]] = {}

    def put_object(self, *, Bucket, Key, Body, ContentType, Metadata):
        self.objects[Key] = {"bucket": Bucket, "body": Body, "ct": ContentType, "meta": Metadata}

    def get_object(self, *, Bucket, Key):
        return {"Body": io.BytesIO(self.objects[Key]["body"])}

    def delete_object(self, *, Bucket, Key):
        self.objects.pop(Key, None)

    def generate_presigned_url(self, op, *, Params, ExpiresIn):
        return f"https://r2.test/{Params['Key']}?exp={ExpiresIn}&rct={Params['ResponseContentType']}"


@pytest.fixture()
def r2(monkeypatch):
    fake = FakeR2()
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
def no_r2(monkeypatch):
    for name in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET", "R2_ENDPOINT_URL"):
        monkeypatch.setattr(settings, name, "", raising=False)
    object_storage.reset_client_cache()
    yield
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
            Customer.__table__,
        ],
    )
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed(db: Session, tag: str) -> tuple[User, Company]:
    suf = uuid.uuid4().hex[:8]
    company = Company(company_name=f"R2 {tag} {suf}", slug=f"r2-{tag}-{suf}")
    db.add(company)
    db.flush()
    user = User(
        email=f"r2_{tag}_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name=f"R2 {tag}",
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


def _static_uploads_snapshot() -> set:
    root = Path(settings.STATIC_DIR)
    return {str(p) for p in root.rglob("*") if p.is_file()} if root.exists() else set()


def test_upload_without_r2_is_explicit_503_and_writes_nothing(db, no_r2, as_user):
    user, _ = _seed(db, "nocfg")
    before = _static_uploads_snapshot()
    resp = as_user(user).post("/api/v1/upload", files={"file": ("a.png", PNG, "image/png")})
    assert resp.status_code == 503
    assert "no está configurado" in resp.json()["detail"]
    assert db.query(StoredFile).filter(StoredFile.user_id == user.id).count() == 0
    assert _static_uploads_snapshot() == before


def test_upload_goes_to_r2_under_company_prefix(db, r2, as_user):
    user, company = _seed(db, "up")
    before = _static_uploads_snapshot()
    resp = as_user(user).post("/api/v1/upload", files={"file": ("foto.png", PNG, "image/png")})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["url"] == f"/api/v1/files/{body['file_id']}"
    assert body["company_id"] == company.id
    row = db.get(StoredFile, body["file_id"])
    assert row.object_key.startswith(f"empresa/{company.id}/images/{row.id}/")
    assert r2.objects[row.object_key]["body"] == PNG
    assert r2.objects[row.object_key]["meta"]["company-id"] == str(company.id)
    assert _static_uploads_snapshot() == before, "no debe escribirse nada en STATIC_DIR"


def test_content_type_spoofing_is_rejected(db, r2, as_user):
    user, _ = _seed(db, "spoof")
    html = b"<html><script>alert(1)</script></html>"
    resp = as_user(user).post("/api/v1/upload", files={"file": ("x.png", html, "image/png")})
    assert resp.status_code == 415
    assert r2.objects == {}


def test_other_company_cannot_open_file_and_thalos_records_it(db, r2, as_user):
    owner, company = _seed(db, "own")
    intruder, _ = _seed(db, "intr")
    fid = as_user(owner).post(
        "/api/v1/upload", files={"file": ("doc.pdf", PDF, "application/pdf")}
    ).json()["file_id"]

    ok = as_user(owner).get(f"/api/v1/files/{fid}", follow_redirects=False)
    assert ok.status_code == 302
    assert ok.headers["location"].startswith(f"https://r2.test/empresa/{company.id}/documents/")
    assert ok.headers["cache-control"] == "no-store"

    url_json = as_user(owner).get(f"/api/v1/files/{fid}/url").json()
    assert url_json["url"].startswith("https://r2.test/") and url_json["content_type"] == "application/pdf"

    denied = as_user(intruder).get(f"/api/v1/files/{fid}", follow_redirects=False)
    assert denied.status_code == 404
    assert as_user(intruder).get(f"/api/v1/files/{fid}/url").status_code == 404
    assert as_user(intruder).delete(f"/api/v1/files/{fid}").status_code == 404

    ev = (
        db.query(ThalosSecurityEvent)
        .filter(ThalosSecurityEvent.event_type == "file_access_denied")
        .order_by(ThalosSecurityEvent.id.desc())
        .first()
    )
    assert ev is not None and ev.severity == "critical"
    details = json.loads(ev.details_json or "{}")
    assert details.get("reason") == "other_company"


def test_delete_removes_object_and_marks_row(db, r2, as_user):
    user, _ = _seed(db, "del")
    fid = as_user(user).post("/api/v1/upload", files={"file": ("f.png", PNG, "image/png")}).json()["file_id"]
    key = db.get(StoredFile, fid).object_key
    assert as_user(user).delete(f"/api/v1/files/{fid}").status_code == 200
    db.expire_all()
    assert key not in r2.objects
    assert db.get(StoredFile, fid).deleted_at is not None
    assert as_user(user).get(f"/api/v1/files/{fid}", follow_redirects=False).status_code == 404


def test_legacy_url_resolves_only_within_company(db, r2, as_user):
    owner, company = _seed(db, "leg")
    other, _ = _seed(db, "leg2")
    legacy = f"uploads/images/u{owner.id}_20260101T000000_foto.png"
    row = object_storage.store_file(
        db, company_id=company.id, user_id=owner.id, category="images",
        filename="foto.png", content_type="image/png", data=PNG, legacy_path=legacy,
    )
    path = f"/api/v1/upload/file/images/u{owner.id}_20260101T000000_foto.png"
    r = as_user(owner).get(path, follow_redirects=False)
    assert r.status_code == 302 and row.object_key in r.headers["location"]
    assert as_user(other).get(path, follow_redirects=False).status_code == 404


def test_tpv_and_workspace_uploads_use_r2(db, r2, as_user):
    user, company = _seed(db, "tpvws")
    c = as_user(user)
    tpv = c.post("/api/v1/tpv/products/upload-image", files={"image": ("p.png", PNG, "image/png")})
    assert tpv.status_code == 200, tpv.text
    assert db.get(StoredFile, tpv.json()["file_id"]).object_key.startswith(f"empresa/{company.id}/products/")
    ws = c.post("/api/v1/workspaces/uploads/documentos", files={"file": ("n.pdf", PDF, "application/pdf")})
    assert ws.status_code == 200, ws.text
    assert db.get(StoredFile, ws.json()["file_id"]).object_key.startswith(f"empresa/{company.id}/workspace/")
    too_big = c.post(
        "/api/v1/tpv/products/upload-image",
        files={"image": ("big.png", PNG + b"\x00" * (2 * 1024 * 1024), "image/png")},
    )
    assert too_big.status_code == 413


def test_crm_import_file_lives_in_r2_and_is_private(db, r2, as_user):
    owner, company = _seed(db, "crm")
    other, _ = _seed(db, "crm2")
    csv = "nombre,email\nAna,ana@example.test\nLuis,luis@example.test\n".encode()
    resp = as_user(owner).post(
        "/api/v1/crm/import/clients/preview", files={"file": ("clientes.csv", csv, "text/csv")}
    )
    assert resp.status_code == 200, resp.text
    fid = resp.json()["file_id"]
    assert resp.json()["total_rows"] == 2
    row = db.get(StoredFile, fid)
    assert row.category == "crm_import" and row.object_key.startswith(f"empresa/{company.id}/crm_import/")

    import services.crm_import_service as svc
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        svc.build_preview(db, fid, other)
    assert exc.value.status_code == 404


def test_crm_import_confirm_reads_from_r2_and_cleans_up(db, r2, as_user):
    owner, company = _seed(db, "crmok")
    csv = "nombre,email,telefono\nAna Ruiz,ana@example.test,600111222\n".encode()
    c = as_user(owner)
    fid = c.post(
        "/api/v1/crm/import/clients/preview", files={"file": ("clientes.csv", csv, "text/csv")}
    ).json()["file_id"]
    key = db.get(StoredFile, fid).object_key
    resp = c.post(
        "/api/v1/crm/import/clients/confirm",
        json={"file_id": fid, "mapping": {"name": "nombre", "email": "email", "phone": "telefono"}},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["imported"] == 1
    db.expire_all()
    created = db.query(Customer).filter(Customer.company_id == company.id).all()
    assert [x.name for x in created] == ["Ana Ruiz"]
    assert key not in r2.objects, "el fichero temporal debe borrarse de R2 tras importar"
    assert db.get(StoredFile, fid).deleted_at is not None


# ---------------------------------------------------------------- /static, entregables, PERSEO


def test_static_uploads_no_longer_public(tmp_path):
    from app.core.static_files import is_blocked_public_path

    for path in (
        "uploads/images/u1_20260101T000000_a.png",
        "UPLOADS/videos/x.mp4",
        "tmp_uploads/abc.csv",
        "./uploads/../uploads/documents/f.pdf",
        "fiscal/x.pdf",
    ):
        assert is_blocked_public_path(path), path
    assert not is_blocked_public_path("assets/app.js")

    root = Path(settings.STATIC_DIR) / "uploads" / "images"
    root.mkdir(parents=True, exist_ok=True)
    probe = root / f"probe_{uuid.uuid4().hex[:6]}.png"
    probe.write_bytes(PNG)
    try:
        r = TestClient(app).get(f"/static/uploads/images/{probe.name}")
        assert r.status_code == 404
    finally:
        probe.unlink(missing_ok=True)


def test_automation_outputs_are_company_scoped(db, r2, as_user):
    from services.automation import utils

    owner, company = _seed(db, "outA")
    other, _ = _seed(db, "outB")
    path = utils.write_json("PERSEO", "42_campaign", {"secreto": "empresa A"}, company_id=company.id)
    assert path.startswith("/api/v1/automation/outputs/perseo/42_campaign_") and path.endswith(".json")
    filename = path.rsplit("/", 1)[1]

    mine = as_user(owner).get("/api/v1/automation/outputs?agent=PERSEO").json()
    assert [o["filename"] for o in mine["outputs"]] == [filename]
    assert as_user(other).get("/api/v1/automation/outputs").json()["outputs"] == []

    got = as_user(owner).get(f"/api/v1/automation/outputs/perseo/{filename}")
    assert got.status_code == 200 and got.json() == {"secreto": "empresa A"}
    assert as_user(other).get(f"/api/v1/automation/outputs/perseo/{filename}").status_code == 404


def test_automation_output_without_company_or_r2_is_not_written(db, no_r2):
    from services.automation import utils

    _, company = _seed(db, "outNo")
    assert utils.write_json("ZEUS", "1_x", {"a": 1}, company_id=company.id) is None
    assert utils.write_markdown("ZEUS", "1_x", "# a", company_id=None) is None


def test_transaction_storage_step_cannot_read_server_files(db):
    from services.zeus_transaction_validation_v1 import validate_transaction

    user, _ = _seed(db, "txst")
    result = validate_transaction(
        db, user, steps=[{"module": "STORAGE", "action": "store_object", "input": {"local_path": "/proc/self/environ"}}]
    )
    assert result["passed"] is False
    assert any("STORAGE" in e for e in result["errors"])


def test_backup_without_r2_fails_honestly(no_r2):
    from services import thalos_backup_service

    res = thalos_backup_service.create_backup(activity_id=7)
    assert res["backup_created"] is False
    assert "R2" in res["notes"]


def test_backup_goes_to_platform_prefix_not_company(r2, monkeypatch, tmp_path):
    from services import thalos_backup_service

    dbfile = tmp_path / "copia.db"
    dbfile.write_bytes(b"SQLite format 3\x00" + b"\x00" * 100)
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{dbfile}", raising=False)
    res = thalos_backup_service.create_backup(activity_id=8)
    assert res["backup_created"] is True, res
    assert res["storage_key"].startswith("plataforma/backups/zeus_backup_")
    assert r2.objects[res["storage_key"]]["body"] == dbfile.read_bytes()
    assert not any(k.startswith("empresa/") and "backup" in k for k in r2.objects)


def test_perseo_inputs_only_from_own_company(db, r2):
    from fastapi import HTTPException

    from services.perseo_media_io import find_input

    owner, company = _seed(db, "pin")
    other, _ = _seed(db, "pin2")
    row = object_storage.store_file(
        db, company_id=company.id, user_id=owner.id, category="videos",
        filename="clip.mp4", content_type="video/mp4", data=b"\x00\x00\x00\x18ftypisom" + b"\x00" * 32,
    )
    assert find_input(db, f"/api/v1/files/{row.id}", owner.id).id == row.id
    assert find_input(db, f"https://zeus.example/api/v1/files/{row.id}?token=x", owner.id).id == row.id
    with pytest.raises(HTTPException) as e1:
        find_input(db, f"/api/v1/files/{row.id}", other.id)
    assert e1.value.status_code == 404
    for bad in ("http://100.64.0.4:8080/secret", "/etc/passwd", "file:///etc/passwd"):
        with pytest.raises(HTTPException) as e2:
            find_input(db, bad, owner.id)
        assert e2.value.status_code == 422, bad


def test_perseo_storage_adapter_uploads_under_company(db, r2, tmp_path):
    from services import perseo_storage_v2

    user, company = _seed(db, "pst")
    f = tmp_path / "out.mp4"
    f.write_bytes(b"\x00\x00\x00\x18ftypisom" + b"\x00" * 64)
    out = perseo_storage_v2.upload_file(f, user_id=user.id, category="videos", content_type="video/mp4")
    assert out["storage"] == "r2" and out["url"] == f"/api/v1/files/{out['file_id']}"
    assert out["key"].startswith(f"empresa/{company.id}/videos/")
    gif = tmp_path / "p.gif"
    gif.write_bytes(b"GIF89a" + b"\x00" * 16)
    g = perseo_storage_v2.upload_tenant_video(gif, tenant_id=company.id, user_id=0, filename="x_preview.gif")
    assert g["key"].startswith(f"empresa/{company.id}/images/")


def test_perseo_storage_adapter_without_r2_is_503(no_r2, tmp_path):
    from fastapi import HTTPException

    from services import perseo_storage_v2

    f = tmp_path / "a.mp4"
    f.write_bytes(b"x")
    with pytest.raises(HTTPException) as exc:
        perseo_storage_v2.upload_file(f, user_id=1, category="videos")
    assert exc.value.status_code == 503


def test_legacy_migration_script_dry_run_apply_and_idempotent(tmp_path, monkeypatch):
    import importlib.util

    from sqlalchemy import create_engine, text as sql

    from app.models.erp import TPVProduct

    spec = importlib.util.spec_from_file_location(
        "migrate_static_uploads_to_r2", Path(__file__).resolve().parents[1] / "scripts" / "migrate_static_uploads_to_r2.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    dbfile = tmp_path / "legacy.db"
    eng = create_engine(f"sqlite:///{dbfile}")
    Base.metadata.create_all(
        bind=eng,
        tables=[User.__table__, Company.__table__, UserCompany.__table__, StoredFile.__table__, TPVProduct.__table__],
    )
    from sqlalchemy.orm import Session as OrmSession

    with OrmSession(eng) as s:
        s.add_all([Company(id=11, company_name="A", slug="a"), Company(id=22, company_name="B", slug="b")])
        s.add(User(id=5, email="u5@x.test", hashed_password="h", is_active=True))
        s.flush()
        s.add(UserCompany(id=1, user_id=5, company_id=11, role="owner"))
        s.add(TPVProduct(id=1, user_id=5, company_id=22, product_id="P1", name="Cafe", category="bebidas",
                         price=1, price_with_iva=1.21, image="/static/uploads/products/product_x.png"))
        s.commit()
    static = tmp_path / "static" / "uploads"
    for rel, data in {
        "images/u5_20260101T000000_foto.png": PNG,
        "products/product_x.png": PNG,
        "videos/22/clip.mp4": b"\x00\x00\x00\x18ftypisom",
        "documents/huerfano.pdf": PDF,
    }.items():
        p = static / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    fake = FakeR2()
    monkeypatch.setattr(mod, "_r2_client", lambda: fake)
    monkeypatch.setenv("R2_BUCKET", "zeus-test")
    base_args = ["prog", "--static-dir", str(tmp_path / "static"), "--database-url", f"sqlite:///{dbfile}"]

    monkeypatch.setattr("sys.argv", base_args + ["--report", str(tmp_path / "dry.json")])
    assert mod.main() == 0
    dry = json.loads((tmp_path / "dry.json").read_text(encoding="utf-8"))
    assert len(dry["migrado"]) == 3 and fake.objects == {}
    assert [e["legacy_path"] for e in dry["sin_resolver"]] == ["uploads/documents/huerfano.pdf"]

    monkeypatch.setattr("sys.argv", base_args + ["--apply", "--report", str(tmp_path / "apply.json")])
    assert mod.main() == 0
    with eng.connect() as c:
        rows = {r[0]: r[1] for r in c.execute(sql("SELECT legacy_path, company_id FROM stored_files"))}
    assert rows == {
        "uploads/images/u5_20260101T000000_foto.png": 11,
        "uploads/products/product_x.png": 22,
        "uploads/videos/22/clip.mp4": 22,
    }
    assert all(k.startswith(("empresa/11/", "empresa/22/")) for k in fake.objects)
    assert len(fake.objects) == 3

    monkeypatch.setattr("sys.argv", base_args + ["--apply", "--report", str(tmp_path / "again.json")])
    assert mod.main() == 0
    again = json.loads((tmp_path / "again.json").read_text(encoding="utf-8"))
    assert len(again["ya_migrado"]) == 3 and again["migrado"] == []
    assert len(fake.objects) == 3
