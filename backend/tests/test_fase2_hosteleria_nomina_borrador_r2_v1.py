"""Fase 2 / vertical hosteleria — borrador de nómina sin disco local (R2 o BD).

Antes el PDF se escribía en storage/outputs (disco efímero de Railway) y la descarga
daba 404 "Archivo no encontrado" tras cada deploy. Ahora:
- Con R2: el documento va a empresa/{companies.id}/documents/... y la descarga lo lee de ahí.
- Sin R2: no se escribe nada a disco; la descarga lo regenera desde la fila de BD.
- Otra empresa no puede descargar el borrador (403) ni lo ve en su listado.
- No se envía nada al empleado ni a organismos (sin gestor configurado: ningún email).
"""

from __future__ import annotations

import io
import uuid
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.company import Company, UserCompany
from app.models.payroll_draft import PayrollDraft
from app.models.stored_file import StoredFile
from app.models.user import User
from services import object_storage
from services.payroll_assistant_service import generate_and_persist


class FakeR2:
    def __init__(self) -> None:
        self.objects: Dict[str, Dict[str, Any]] = {}

    def put_object(self, *, Bucket, Key, Body, ContentType, Metadata):
        self.objects[Key] = {"body": Body, "ct": ContentType}

    def get_object(self, *, Bucket, Key):
        return {"Body": io.BytesIO(self.objects[Key]["body"])}

    def delete_object(self, *, Bucket, Key):
        self.objects.pop(Key, None)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def r2(monkeypatch):
    fake = FakeR2()
    for name, value in (("R2_ACCOUNT_ID", "acc"), ("R2_ACCESS_KEY_ID", "k"),
                        ("R2_SECRET_ACCESS_KEY", "s"), ("R2_BUCKET", "zeus-test")):
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


def _owner(db, tag):
    suf = uuid.uuid4().hex[:8]
    c = Company(company_name=f"Nom {tag} {suf}", slug=f"nom-{tag}-{suf}")
    u = User(email=f"nom_{tag}_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
             full_name=f"Owner {tag}", is_active=True, company_name=f"Bar {tag}")
    e = User(email=f"emp_{tag}_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
             full_name=f"Camarero {tag}", is_active=True)
    db.add_all([c, u, e])
    db.flush()
    db.add_all([UserCompany(user_id=u.id, company_id=c.id, role="owner"),
                UserCompany(user_id=e.id, company_id=c.id, role="member")])
    db.commit()
    db.refresh(u)
    db.refresh(e)
    return u, e, c.id


def _h(u):
    return {"Authorization": f"Bearer {create_access_token({'sub': u.email, 'email': u.email})}"}


def test_borrador_en_r2_bajo_su_empresa_y_descarga_desde_r2(db, r2, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # cualquier escritura relativa a disco apareceria aqui
    a, emp, cid = _owner(db, "a")
    b, _, _ = _owner(db, "b")
    record, ref = generate_and_persist(db, company_id=a.id, employee_id=emp.id, gross_salary=1800.0,
                                       month="octubre", year=2026, company_name="Bar a", employee_name="Camarero a")
    assert ref and ref.startswith("r2:")
    row = db.query(StoredFile).filter(StoredFile.id == ref[3:]).one()
    assert row.company_id == cid and row.object_key.startswith(f"empresa/{cid}/documents/")
    assert list(tmp_path.rglob("*")) == []  # nada en disco local

    client = TestClient(app)
    r = client.get(f"/api/v1/payroll/drafts/{record.id}/download", headers=_h(a))
    assert r.status_code == 200, r.text
    assert r.content == r2.objects[row.object_key]["body"]
    assert r.content[:4] in (b"%PDF", b"=== ")

    assert client.get(f"/api/v1/payroll/drafts/{record.id}/download", headers=_h(b)).status_code == 403
    ids_b = [d["id"] for d in client.get("/api/v1/payroll/drafts", headers=_h(b)).json()["drafts"]]
    assert record.id not in ids_b
    ids_a = [d["id"] for d in client.get("/api/v1/payroll/drafts", headers=_h(a)).json()["drafts"]]
    assert record.id in ids_a


def test_sin_r2_no_escribe_disco_y_regenera_desde_bd(db, no_r2, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    a, emp, _ = _owner(db, "a")
    record, ref = generate_and_persist(db, company_id=a.id, employee_id=emp.id, gross_salary=1500.0,
                                       month="octubre", year=2026)
    assert ref is None and record.pdf_path is None
    assert list(tmp_path.rglob("*")) == []

    r = TestClient(app).get(f"/api/v1/payroll/drafts/{record.id}/download", headers=_h(a))
    assert r.status_code == 200, r.text
    assert len(r.content) > 100
    assert "attachment" in r.headers.get("content-disposition", "")


def test_borrador_legado_con_ruta_perdida_se_regenera(db, no_r2):
    a, emp, _ = _owner(db, "a")
    d = PayrollDraft(owner_user_id=a.id, employee_id=emp.id, gross_salary=1200.0, irpf_estimated=228.0,
                     social_security_estimated=76.2, net_salary_estimated=895.8, month="enero", year=2026,
                     pdf_path="storage/outputs/payroll_drafts/ya_no_existe.pdf")
    db.add(d)
    db.commit()
    r = TestClient(app).get(f"/api/v1/payroll/drafts/{d.id}/download", headers=_h(a))
    assert r.status_code == 200, r.text  # antes: 404 "Archivo no encontrado"
