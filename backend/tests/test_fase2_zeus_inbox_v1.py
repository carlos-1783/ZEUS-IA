"""Fase 2 / Jarvis — ZEUS recepcionista: POST/GET /api/v1/zeus/inbox.

Dobles SOLO en el test: el cliente S3 (R2 en memoria) y la llamada al modelo de vision
(`zeus_inbox_service._vision_call`). En produccion ambos son reales (boto3 -> R2, OpenAI).
Se ejercitan los endpoints HTTP reales, con THALOS real y dos empresas reales.
"""

from __future__ import annotations

import io
import uuid
from pathlib import Path
from typing import Any, Dict, List

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.core.config import settings
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.agent_activity import AgentActivity
from app.models.company import Company, UserCompany
from app.models.document_approval import DocumentApproval
from app.models.stored_file import StoredFile
from app.models.thalos_security_event import ThalosSecurityEvent
from app.models.user import User
from app.models.zeus_inbox_item import ZeusInboxItem
from services import object_storage
from services import thalos_request_guard_v1 as guard
from services import zeus_inbox_service as inbox

P = "/api/v1/zeus/inbox"
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 128
PDF = b"%PDF-1.4\n%cabecera real de PDF\n"


class FakeR2:
    def __init__(self) -> None:
        self.objects: Dict[str, Dict[str, Any]] = {}

    def put_object(self, *, Bucket, Key, Body, ContentType, Metadata):
        self.objects[Key] = {"body": Body, "ct": ContentType, "meta": Metadata}

    def get_object(self, *, Bucket, Key):
        return {"Body": io.BytesIO(self.objects[Key]["body"])}

    def delete_object(self, *, Bucket, Key):
        self.objects.pop(Key, None)

    def generate_presigned_url(self, op, *, Params, ExpiresIn):
        return f"https://r2.test/{Params['Key']}"


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


class Vision:
    """Doble del modelo de vision: registra llamadas y devuelve la respuesta configurada."""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []
        self.response: Any = None

    def __call__(self, data, content_type, filename, note):
        self.calls.append({"bytes": len(data), "content_type": content_type, "note": note})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


@pytest.fixture()
def vision(monkeypatch):
    v = Vision()
    monkeypatch.setattr(inbox.settings, "OPENAI_API_KEY", "sk-test-solo-en-tests", raising=False)
    monkeypatch.setattr(inbox, "_vision_call", v)
    return v


@pytest.fixture()
def no_openai(monkeypatch):
    monkeypatch.setattr(inbox.settings, "OPENAI_API_KEY", "", raising=False)

    def _never(*a, **k):
        raise AssertionError("no se debe llamar al modelo sin OPENAI_API_KEY")

    monkeypatch.setattr(inbox, "_vision_call", _never)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _seed(db: Session, tag: str) -> tuple[User, Company]:
    suf = uuid.uuid4().hex[:8]
    company = Company(company_name=f"Inbox {tag} {suf}", slug=f"inbox-{tag}-{suf}")
    db.add(company)
    db.flush()
    user = User(
        email=f"inbox_{tag}_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name=f"Inbox {tag}",
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


def _factura(**over) -> Dict[str, Any]:
    campos = {
        "proveedor": "Suministros Lopez SL",
        "nif": "12345678Z",
        "fecha": "2026-09-30",
        "numero": "F-2026-0042",
        "base": 100.0,
        "iva": 21.0,
        "total": 121.0,
    }
    campos.update(over)
    return {"tipo": "factura_proveedor", "confianza": 0.93, "campos": campos, "observaciones": None}


def _activities(db: Session, company_id: int) -> List[AgentActivity]:
    db.expire_all()
    return db.query(AgentActivity).filter(AgentActivity.company_id == company_id).all()


def _static_snapshot() -> set:
    root = Path(settings.STATIC_DIR)
    return {str(p) for p in root.rglob("*") if p.is_file()} if root.exists() else set()


# ------------------------------------------------------------------ flujo completo


def test_factura_se_guarda_clasifica_y_asigna_a_rafael(db, r2, vision, as_user):
    user, company = _seed(db, "ok")
    vision.response = _factura()
    resp = as_user(user).post(
        P, files={"file": ("factura.jpg", JPG, "image/jpeg")}, data={"note": "factura del gas"}
    )
    assert resp.status_code == 201, resp.text
    item = resp.json()["item"]
    assert item["status"] == "clasificado"
    assert item["doc_type"] == "factura_proveedor"
    assert item["assigned_agent"] == "RAFAEL"
    assert item["confidence"] == "alta"
    assert item["fields"]["total"] == "121.00" and item["fields"]["nif"] == "12345678Z"
    assert item["validation"]["checks"]["importes"]["estado"] == "coherente"
    assert item["validation"]["issues"] == []
    assert item["file"]["url"] == f"/api/v1/files/{item['file']['file_id']}"
    assert item["review"]["status"] == "pending_review"
    assert vision.calls == [{"bytes": len(JPG), "content_type": "image/jpeg", "note": "factura del gas"}]

    db.expire_all()
    stored = db.query(StoredFile).filter(StoredFile.id == item["file"]["file_id"]).one()
    assert stored.company_id == company.id and stored.category == "inbox"
    assert stored.object_key.startswith(f"empresa/{company.id}/inbox/")
    assert stored.object_key in r2.objects

    approval = db.query(DocumentApproval).filter(DocumentApproval.id == item["review"]["document_approval_id"]).one()
    assert approval.company_id == company.id
    assert approval.agent_name == "RAFAEL"
    assert approval.status == "pending_review"
    assert approval.document_type == "zeus_inbox_factura_proveedor"
    assert approval.document_payload["inbox_item_id"] == item["id"]
    assert approval.sent_at is None and approval.exported_at is None and approval.filed_external_at is None

    acts = {(a.agent_name, a.action_type, a.status) for a in _activities(db, company.id)}
    assert ("ZEUS", "inbox_received", "completed") in acts
    assert ("ZEUS", "inbox_classified", "completed") in acts
    assert ("RAFAEL", "inbox_document_assigned", "pending") in acts


def test_pdf_se_envia_al_modelo_como_pdf(db, r2, vision, as_user):
    user, _ = _seed(db, "pdf")
    vision.response = {"tipo": "contrato", "confianza": 0.9, "campos": {}}
    resp = as_user(user).post(P, files={"file": ("c.pdf", PDF, "application/pdf")})
    assert resp.status_code == 201, resp.text
    assert vision.calls[0]["content_type"] == "application/pdf"
    assert resp.json()["item"]["assigned_agent"] == "JUSTICIA"


@pytest.mark.parametrize(
    "tipo,agente,tipo_final",
    [
        ("ticket", "RAFAEL", "ticket"),
        ("nomina", "AFRODITA", "nomina"),
        ("albaran", "AFRODITA", "albaran"),
        ("pedido", "AFRODITA", "pedido"),
        ("contrato", "JUSTICIA", "contrato"),
        ("otro", "ZEUS", "otro"),
        ("carta_de_amor", "ZEUS", "otro"),  # tipo fuera de la lista cerrada -> otro
    ],
)
def test_enrutado_por_tipo(db, r2, vision, as_user, tipo, agente, tipo_final):
    user, company = _seed(db, "route")
    vision.response = {"tipo": tipo, "confianza": 0.85, "campos": {}}
    resp = as_user(user).post(P, files={"file": ("d.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 32, "image/png")})
    assert resp.status_code == 201, resp.text
    item = resp.json()["item"]
    assert item["doc_type"] == tipo_final and item["assigned_agent"] == agente
    db.expire_all()
    approval = db.query(DocumentApproval).filter(DocumentApproval.id == item["review"]["document_approval_id"]).one()
    assert approval.agent_name == agente and approval.company_id == company.id
    assert any(
        a.agent_name == agente and a.action_type == "inbox_document_assigned" for a in _activities(db, company.id)
    )


def test_importes_incoherentes_bajan_confianza_y_no_se_corrigen(db, r2, vision, as_user):
    user, _ = _seed(db, "incoh")
    vision.response = _factura(base="100,00", iva="21,00", total="150,00")
    resp = as_user(user).post(P, files={"file": ("f.jpg", JPG, "image/jpeg")})
    assert resp.status_code == 201
    item = resp.json()["item"]
    assert item["confidence"] == "baja"
    assert item["validation"]["checks"]["importes"]["estado"] == "incoherente"
    assert item["fields"]["total"] == "150.00"  # lo que se leyo, sin "arreglar"


def test_campos_no_leidos_quedan_null_no_se_inventan(db, r2, vision, as_user):
    user, _ = _seed(db, "nulls")
    vision.response = {"tipo": "factura_proveedor", "confianza": 0.9, "campos": {"total": "60.50", "nif": None}}
    resp = as_user(user).post(P, files={"file": ("f.jpg", JPG, "image/jpeg")})
    assert resp.status_code == 201
    item = resp.json()["item"]
    assert item["fields"] == {
        "proveedor": None, "nif": None, "fecha": None, "numero": None,
        "base": None, "iva": None, "total": "60.50",
    }
    assert item["confidence"] == "media"
    assert item["validation"]["checks"]["importes"]["estado"] == "incompleto"
    assert any("NIF" in i for i in item["validation"]["issues"])


# ------------------------------------------------------------------ sin claves externas


def test_sin_openai_503_documento_guardado_pendiente_sin_campos(db, r2, no_openai, as_user):
    user, company = _seed(db, "nokey")
    resp = as_user(user).post(P, files={"file": ("f.jpg", JPG, "image/jpeg")})
    assert resp.status_code == 503
    body = resp.json()
    assert body["detail"] == "clasificación no disponible: falta OPENAI_API_KEY"
    item = body["item"]
    assert item["status"] == "pendiente_clasificacion"
    assert item["doc_type"] is None and item["fields"] is None and item["assigned_agent"] is None
    assert item["review"] is None
    db.expire_all()
    assert db.query(StoredFile).filter(StoredFile.id == item["file"]["file_id"]).count() == 1
    assert db.query(DocumentApproval).filter(DocumentApproval.company_id == company.id).count() == 0
    acts = {(a.agent_name, a.action_type, a.status) for a in _activities(db, company.id)}
    assert ("ZEUS", "inbox_classification_unavailable", "failed") in acts


def test_reintento_de_clasificacion_cuando_ya_hay_clave(db, r2, no_openai, as_user, monkeypatch):
    user, _ = _seed(db, "retry")
    client = as_user(user)
    item_id = client.post(P, files={"file": ("f.jpg", JPG, "image/jpeg")}).json()["item"]["id"]
    assert client.post(f"{P}/{item_id}/classify").status_code == 503  # sigue sin clave

    v = Vision()
    v.response = _factura()
    monkeypatch.setattr(inbox.settings, "OPENAI_API_KEY", "sk-test-solo-en-tests", raising=False)
    monkeypatch.setattr(inbox, "_vision_call", v)
    resp = client.post(f"{P}/{item_id}/classify")
    assert resp.status_code == 201, resp.text
    assert resp.json()["item"]["assigned_agent"] == "RAFAEL"
    assert v.calls[0]["bytes"] == len(JPG)  # bytes leidos de R2
    assert client.post(f"{P}/{item_id}/classify").status_code == 409


def test_fallo_del_modelo_502_y_queda_pendiente(db, r2, vision, as_user):
    user, company = _seed(db, "fail")
    vision.response = inbox.ClassificationFailed("El modelo de vision no devolvio un JSON valido.")
    resp = as_user(user).post(P, files={"file": ("f.jpg", JPG, "image/jpeg")})
    assert resp.status_code == 502
    assert resp.json()["item"]["status"] == "pendiente_clasificacion"
    db.expire_all()
    assert db.query(DocumentApproval).filter(DocumentApproval.company_id == company.id).count() == 0


def test_sin_r2_503_no_guarda_ni_clasifica_nada(db, no_r2, vision, as_user):
    user, company = _seed(db, "nor2")
    before = _static_snapshot()
    vision.response = _factura()
    resp = as_user(user).post(P, files={"file": ("f.jpg", JPG, "image/jpeg")})
    assert resp.status_code == 503
    assert "no esta configurado" in resp.json()["detail"]
    assert vision.calls == []
    db.expire_all()
    assert db.query(ZeusInboxItem).filter(ZeusInboxItem.company_id == company.id).count() == 0
    assert db.query(StoredFile).filter(StoredFile.company_id == company.id).count() == 0
    assert _static_snapshot() == before
    acts = {(a.agent_name, a.action_type, a.status) for a in _activities(db, company.id)}
    assert ("ZEUS", "inbox_storage_unavailable", "failed") in acts


# ------------------------------------------------------------------ validacion de fichero


def test_mime_falso_rechazado(db, r2, vision, as_user):
    user, company = _seed(db, "mime")
    client = as_user(user)
    html = b"<html><script>alert(1)</script></html>"
    assert client.post(P, files={"file": ("x.jpg", html, "image/jpeg")}).status_code == 415
    assert client.post(P, files={"file": ("x.txt", b"hola", "text/plain")}).status_code == 415
    assert client.post(P, files={"file": ("x.pdf", JPG, "application/pdf")}).status_code == 415
    assert vision.calls == []
    db.expire_all()
    assert db.query(ZeusInboxItem).filter(ZeusInboxItem.company_id == company.id).count() == 0


def test_fichero_demasiado_grande_413(db, r2, vision, as_user, monkeypatch):
    from app.api.v1.endpoints import zeus_inbox_v1

    monkeypatch.setattr(zeus_inbox_v1, "MAX_BYTES", 64)
    user, _ = _seed(db, "big")
    resp = as_user(user).post(P, files={"file": ("f.jpg", JPG, "image/jpeg")})
    assert resp.status_code == 413
    assert vision.calls == []


# ------------------------------------------------------------------ multi-tenant y THALOS


def test_otra_empresa_no_ve_la_bandeja_ni_el_documento(db, r2, vision, as_user):
    user_a, company_a = _seed(db, "a")
    user_b, _ = _seed(db, "b")
    vision.response = _factura()
    item = as_user(user_a).post(P, files={"file": ("f.jpg", JPG, "image/jpeg")}).json()["item"]

    own = as_user(user_a).get(P)
    assert own.status_code == 200 and [i["id"] for i in own.json()["items"]] == [item["id"]]

    client_b = as_user(user_b)
    lst = client_b.get(P)
    assert lst.status_code == 200 and lst.json() == {"success": True, "total": 0, "items": []}
    assert client_b.get(f"{P}/{item['id']}").status_code == 404
    assert client_b.post(f"{P}/{item['id']}/classify").status_code == 404
    assert client_b.get(f"/api/v1/files/{item['file']['file_id']}").status_code == 404
    db.expire_all()
    assert all(
        a.company_id == company_a.id
        for a in db.query(AgentActivity).filter(AgentActivity.action_type.like("inbox_%"),
                                                AgentActivity.user_email == user_a.email)
    )


def test_usuario_sin_empresa_rechazado_por_thalos(db, r2, vision, as_user):
    suf = uuid.uuid4().hex[:8]
    lone = User(email=f"inbox_lone_{suf}@example.test", hashed_password=get_password_hash("TestPass1"),
                full_name="Sin empresa", is_active=True)
    db.add(lone)
    db.commit()
    db.refresh(lone)
    resp = as_user(lone).post(P, files={"file": ("f.jpg", JPG, "image/jpeg")})
    assert resp.status_code == 403
    assert vision.calls == []


def test_rutas_cubiertas_por_thalos_y_evento_registrado(db, r2, vision, as_user):
    routes = [r for r in app.routes if isinstance(r, APIRoute) and r.path_format.startswith(P)]
    assert {r.path_format for r in routes} == {
        P, f"{P}/{{item_id}}", f"{P}/{{item_id}}/classify", f"{P}/{{item_id}}/review"
    }
    assert all(guard.route_is_thalos_covered(r) for r in routes)

    user, _ = _seed(db, "thalos")
    vision.response = _factura()
    assert as_user(user).post(P, files={"file": ("f.jpg", JPG, "image/jpeg")}).status_code == 201
    db.expire_all()
    events = [
        e for e in db.query(ThalosSecurityEvent).filter(ThalosSecurityEvent.event_type == "request_guard").all()
        if P in str(e.details_json) and e.user_id == user.id
    ]
    assert events, "THALOS no registro la peticion a la bandeja"


# ------------------------------------------------------------------ unidades


def test_validaciones_nif_e_importes():
    assert inbox.nif_is_valid("12345678Z")
    assert not inbox.nif_is_valid("12345678A")
    assert inbox.nif_is_valid("X1234567L")
    assert inbox.nif_is_valid("B12345674")
    assert not inbox.nif_is_valid("B12345670")
    assert str(inbox._to_decimal("1.234,56 €")) == "1234.56"
    assert inbox._to_decimal("ilegible") is None


def test_llamada_real_al_modelo_construye_imagen_y_pdf(monkeypatch):
    """Ejercita `_vision_call` real con un cliente OpenAI doble: forma exacta de la peticion."""
    import services.openai_service as oai

    sent: List[Dict[str, Any]] = []

    class _Msg:
        content = '{"tipo": "ticket", "confianza": 0.7, "campos": {"total": "3,50"}}'

    class _Completions:
        def create(self, **kw):
            sent.append(kw)
            return type("R", (), {"choices": [type("C", (), {"message": _Msg()})()]})()

    fake = type("Client", (), {"chat": type("Chat", (), {"completions": _Completions()})()})()
    monkeypatch.setattr(oai, "get_openai_client", lambda: fake)

    out = inbox._vision_call(JPG, "image/jpeg", "t.jpg", None)
    assert out["tipo"] == "ticket"
    part = sent[0]["messages"][1]["content"][1]
    assert part["type"] == "image_url" and part["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert sent[0]["temperature"] == 0 and sent[0]["response_format"] == {"type": "json_object"}

    inbox._vision_call(PDF, "application/pdf", "c.pdf", "nota")
    part = sent[1]["messages"][1]["content"][1]
    assert part["type"] == "file" and part["file"]["file_data"].startswith("data:application/pdf;base64,")
    assert "nota" in sent[1]["messages"][1]["content"][0]["text"]

    _Msg.content = "esto no es json"
    with pytest.raises(inbox.ClassificationFailed):
        inbox._vision_call(JPG, "image/jpeg", "t.jpg", None)
