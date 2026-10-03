"""
Regresion N1: los ficheros fiscales de RAFAEL (PDF de facturas / Excel modelo 303) ya NO se
sirven sin autenticacion desde /static/fiscal/...

  * el motor escribe en settings.PRIVATE_FILES_DIR (fuera de STATIC_DIR);
  * la API devuelve URLs del endpoint autenticado /api/v1/rafael-fiscal/fiscal-files/...;
  * el endpoint exige usuario autenticado vinculado a la empresa del path (o superusuario);
  * kind en lista blanca, filename con regex estricta y comprobacion anti path traversal;
  * /static/fiscal/... da 404 aunque el fichero exista en disco bajo STATIC_DIR.

El contenido de los ficheros lo genera el motor real (generate_invoice_pdf_flow); no hay mocks
del contenido. Los directorios privado y estatico son tmp_path (no se escribe en el repo).
"""

from __future__ import annotations

import importlib.util
import uuid
import zipfile
from pathlib import Path

import pytest  # pyright: ignore[reportMissingImports]
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.core.config import settings
from app.core.security import get_password_hash
from app.core.static_files import PublicStaticFiles
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.company import Company, UserCompany
from app.models.customer import Customer
from app.models.erp import Invoice, InvoiceItem
from app.models.user import User
from services import rafael_fiscal_engine_v2 as fiscal_engine

API = settings.API_V1_STR
FISCAL_FILES = f"{API}/rafael-fiscal/fiscal-files"


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def dirs(tmp_path, monkeypatch):
    private = tmp_path / "private_files"
    static = tmp_path / "static"
    static.mkdir()
    monkeypatch.setattr(settings, "PRIVATE_FILES_DIR", str(private))
    monkeypatch.setattr(settings, "STATIC_DIR", str(static))
    _ensure_generators(monkeypatch)
    return private, static


def _has(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def _ensure_generators(monkeypatch) -> None:
    """Usa los generadores reales (reportlab/openpyxl, ver requirements.txt).

    Solo si la libreria no esta instalada en el entorno local se sustituye el *generador de
    bytes* por un escritor minimo (PDF/zip validos). El resto del flujo del motor (rutas, saneado
    de nombres, URL, BD) y el endpoint se ejercitan siempre de verdad.
    """
    if not _has("reportlab"):

        def _fake_pdf(*, output_path: Path, **_kw) -> str:
            pdf = output_path.with_suffix(".pdf")
            pdf.parent.mkdir(parents=True, exist_ok=True)
            pdf.write_bytes(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")
            return str(pdf)

        monkeypatch.setattr(fiscal_engine, "generate_invoice_pdf_v1", _fake_pdf)
    if not _has("openpyxl"):

        def _fake_xlsx(*, output_path: Path, **_kw) -> str:
            xlsx = output_path.with_suffix(".xlsx")
            xlsx.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(xlsx, "w") as z:
                z.writestr("[Content_Types].xml", "<Types/>")
            return str(xlsx)

        monkeypatch.setattr(fiscal_engine, "generate_model_303_xlsx_v1", _fake_xlsx)


@pytest.fixture()
def client():
    # Sin context manager: NO se ejecuta el lifespan (workers, BD de arranque, etc.).
    c = TestClient(app, raise_server_exceptions=False)
    try:
        yield c
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)


def _seed_company_user(db: Session, tag: str, *, superuser: bool = False):
    suf = uuid.uuid4().hex[:8]
    company = Company(company_name=f"Fiscal Co {tag} {suf}", slug=f"fiscal-{tag}-{suf}")
    db.add(company)
    db.flush()
    user = User(
        email=f"fiscal_{tag}_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name=f"Fiscal {tag}",
        is_active=True,
        is_superuser=superuser,
    )
    db.add(user)
    db.flush()
    db.add(UserCompany(user_id=user.id, company_id=company.id, role="owner"))
    db.commit()
    db.refresh(user)
    db.refresh(company)
    return user, company


def _seed_invoice(db: Session, company: Company) -> Invoice:
    suf = uuid.uuid4().hex[:6]
    customer = Customer(name=f"Cliente {suf}", email=f"cli_{suf}@example.test", company_id=company.id)
    db.add(customer)
    db.flush()
    invoice = Invoice(
        invoice_number=f"F/{suf}.01",  # caracteres peligrosos a proposito: el motor debe sanearlos
        company_id=company.id,
        customer_id=customer.id,
        subtotal=100.0,
        tax_amount=21.0,
        total=121.0,
    )
    db.add(invoice)
    db.flush()
    db.add(
        InvoiceItem(
            invoice_id=invoice.id,
            description="Servicio de prueba",
            quantity=1.0,
            unit_price=100.0,
            subtotal=100.0,
            tax_amount=21.0,
            total=121.0,
        )
    )
    db.commit()
    db.refresh(invoice)
    return invoice


def _generate_invoice_pdf(db: Session, user: User, company: Company) -> dict:
    """Factura real de la empresa -> PDF real generado por el motor RAFAEL."""
    invoice = _seed_invoice(db, company)
    return fiscal_engine.generate_invoice_pdf_flow(
        db, user=user, invoice_id=invoice.id, company_id=company.id
    )


def _as(user: User):
    app.dependency_overrides[get_current_active_user] = lambda: user


# ---------------------------------------------------------------- (f) ubicacion


def test_f_private_dir_default_is_outside_static_dir():
    """El valor por defecto de PRIVATE_FILES_DIR nunca cuelga de STATIC_DIR."""
    private = Path(settings.PRIVATE_FILES_DIR).resolve()
    static = Path(settings.STATIC_DIR).resolve()
    assert not private.is_relative_to(static)
    assert not static.is_relative_to(private)


def test_f_engine_writes_outside_static_and_returns_authenticated_url(db, dirs):
    private, static = dirs
    user, company = _seed_company_user(db, "f")
    out = _generate_invoice_pdf(db, user, company)

    generated = Path(out["file_path"]).resolve()
    assert generated.is_file() and generated.stat().st_size > 0
    assert generated.read_bytes()[:5] == b"%PDF-"
    assert generated.is_relative_to(private.resolve())
    assert not generated.is_relative_to(static.resolve())
    assert list(static.rglob("*")) == []  # nada fiscal bajo STATIC_DIR

    url = out["file_url"]
    assert url.startswith(f"{FISCAL_FILES}/{company.id}/invoices/")
    assert url.endswith(".pdf")
    assert "/static/" not in url


# ---------------------------------------------------------------- (a) sin token


def test_a_download_without_token_is_401(db, dirs, client):
    user, company = _seed_company_user(db, "a")
    out = _generate_invoice_pdf(db, user, company)
    app.dependency_overrides.pop(get_current_active_user, None)

    r = client.get(out["file_url"])
    assert r.status_code == 401

    r = client.get(out["file_url"], headers={"Authorization": "Bearer token-invalido"})
    assert r.status_code in (401, 403)


# ---------------------------------------------------------------- (c) empresa A -> 200


def test_c_company_member_downloads_real_bytes(db, dirs, client):
    user, company = _seed_company_user(db, "c")
    out = _generate_invoice_pdf(db, user, company)
    on_disk = Path(out["file_path"]).read_bytes()

    _as(user)
    r = client.get(out["file_url"])
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content == on_disk
    assert r.content[:5] == b"%PDF-"
    assert "no-store" in r.headers.get("cache-control", "")


def test_c_superuser_can_download_any_company_file(db, dirs, client):
    user, company = _seed_company_user(db, "cs")
    admin, _ = _seed_company_user(db, "root", superuser=True)
    out = _generate_invoice_pdf(db, user, company)

    _as(admin)
    r = client.get(out["file_url"])
    assert r.status_code == 200
    assert r.content == Path(out["file_path"]).read_bytes()


def test_c_model_303_xlsx_served_with_xlsx_content_type(db, dirs, client):
    user, company = _seed_company_user(db, "x")
    # Fichero del tipo model_303 generado por el generador de Excel que usa el motor.
    out_dir = fiscal_engine._fiscal_root() / str(company.id) / "model_303"
    xlsx = fiscal_engine.generate_model_303_xlsx_v1(
        output_path=out_dir / "modelo_303_2026-Q1_20260101000000",
        company_name="Fiscal Co x",
        period="2026-Q1",
        model_data={
            "base_imponible": 100.0,
            "iva_devengado": 21.0,
            "iva_soportado": 5.0,
            "resultado": 16.0,
            "vat_breakdown": {},
        },
    )
    url = fiscal_engine._private_file_url(xlsx)
    assert url == f"{FISCAL_FILES}/{company.id}/model_303/{Path(xlsx).name}"

    _as(user)
    r = client.get(url)
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers["content-type"]
    assert r.content[:2] == b"PK"  # xlsx = zip
    assert r.content == Path(xlsx).read_bytes()


# ---------------------------------------------------------------- (b) empresa B -> A


def test_b_other_company_cannot_download(db, dirs, client):
    user_a, company_a = _seed_company_user(db, "A")
    user_b, company_b = _seed_company_user(db, "B")
    out = _generate_invoice_pdf(db, user_a, company_a)
    filename = Path(out["file_path"]).name

    _as(user_b)
    # Pide el fichero de A usando la ruta de A
    r = client.get(f"{FISCAL_FILES}/{company_a.id}/invoices/{filename}")
    assert r.status_code in (403, 404)
    assert b"%PDF" not in r.content
    # Pide el mismo nombre bajo su propia empresa B: no existe
    r = client.get(f"{FISCAL_FILES}/{company_b.id}/invoices/{filename}")
    assert r.status_code == 404
    # Empresa inexistente
    r = client.get(f"{FISCAL_FILES}/99999999/invoices/{filename}")
    assert r.status_code in (403, 404)


# ---------------------------------------------------------------- (d) traversal / validacion


@pytest.mark.parametrize(
    "tail",
    [
        "invoices/..%2F..%2Fmodel_303%2Fsecreto.xlsx",
        "invoices/%2e%2e%2f%2e%2e%2fsecreto.xlsx",
        "invoices/..%5C..%5Csecreto.xlsx",
        "invoices/secreto.txt",
        "invoices/.pdf",
        "invoices/a.b.pdf",
        "otro_kind/secreto.xlsx",
        "../invoices/secreto.xlsx",
    ],
)
def test_d_path_traversal_and_invalid_names_rejected(db, dirs, client, tail):
    private, _ = dirs
    user, company = _seed_company_user(db, "d")
    base = private / "fiscal" / str(company.id)
    (base / "model_303").mkdir(parents=True)
    (base / "model_303" / "secreto.xlsx").write_bytes(b"PK-secreto")
    (base / "invoices").mkdir(parents=True)
    (base / "invoices" / "secreto.txt").write_bytes(b"txt-secreto")
    (private / "fiscal" / "secreto.xlsx").write_bytes(b"PK-fuera-de-empresa")

    _as(user)
    r = client.get(f"{FISCAL_FILES}/{company.id}/{tail}")
    assert 400 <= r.status_code < 500
    assert b"PK-secreto" not in r.content
    assert b"txt-secreto" not in r.content
    assert b"PK-fuera" not in r.content


def test_d_symlink_escaping_company_dir_is_rejected(db, dirs, client, tmp_path):
    private, _ = dirs
    user, company = _seed_company_user(db, "sym")
    outside = tmp_path / "fuera.pdf"
    outside.write_bytes(b"%PDF-1.4 secreto")
    inv_dir = private / "fiscal" / str(company.id) / "invoices"
    inv_dir.mkdir(parents=True)
    try:
        (inv_dir / "enlace.pdf").symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks no disponibles en este entorno")

    _as(user)
    r = client.get(f"{FISCAL_FILES}/{company.id}/invoices/enlace.pdf")
    assert r.status_code == 404
    assert b"secreto" not in r.content


# ---------------------------------------------------------------- (e) /static/fiscal -> 404


def _public_static_mount():
    for route in app.routes:
        if getattr(route, "path", None) == "/static":
            return route.app
    raise AssertionError("/static no esta montado en la app")


def test_e_static_mount_uses_public_static_files():
    assert isinstance(_public_static_mount(), PublicStaticFiles)


def test_e_static_fiscal_is_404_even_if_file_exists_on_disk(tmp_path, monkeypatch, client):
    """Fichero real presente en disco bajo el directorio servido por /static -> 404."""
    mount = _public_static_mount()
    static = tmp_path / "served_static"
    (static / "fiscal" / "7" / "invoices").mkdir(parents=True)
    (static / "fiscal" / "7" / "invoices" / "invoice_1.pdf").write_bytes(b"%PDF-1.4 legado")
    (static / "uploads").mkdir()
    (static / "uploads" / "publico.txt").write_bytes(b"ok-publico")
    monkeypatch.setattr(mount, "directory", str(static))
    monkeypatch.setattr(mount, "all_directories", [str(static)])

    # Control: lo publico sigue sirviendose, asi el 404 de fiscal es por el bloqueo y no por el montaje.
    assert client.get("/static/uploads/publico.txt").content == b"ok-publico"

    for path in (
        "/static/fiscal/7/invoices/invoice_1.pdf",
        "/static/Fiscal/7/invoices/invoice_1.pdf",
        "/static/./fiscal/7/invoices/invoice_1.pdf",
        "/static/uploads/../fiscal/7/invoices/invoice_1.pdf",
        "/static/fiscal/7/invoices/",
    ):
        r = client.get(path)
        assert r.status_code == 404, path
        assert b"legado" not in r.content, path


def test_e_spa_fallback_does_not_serve_fiscal_files(tmp_path, monkeypatch, client):
    """/fiscal/... (sin /static) tampoco sirve el fichero aunque SPA_STATIC_DIR == STATIC_DIR."""
    import app.main as main_module

    root = tmp_path / "spa"
    (root / "fiscal" / "7").mkdir(parents=True)
    (root / "fiscal" / "7" / "x.pdf").write_bytes(b"%PDF-1.4 legado-spa")
    monkeypatch.setattr(main_module, "spa_root", str(root))
    r = client.get("/fiscal/7/x.pdf")
    assert b"legado-spa" not in r.content
