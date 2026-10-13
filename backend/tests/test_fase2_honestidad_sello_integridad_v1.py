"""Fase 2 / honestidad final #2 — JUSTICIA: sello de integridad (hash), no "firma digital".

- Sellar NO aprueba: un borrador sigue en draft.
- Cada respuesta avisa de que no equivale a firma electronica eIDAS.
- Un workflow (handler de automatizacion) ya no sella/aprueba documentos solo.
- Sin BD/usuario no se devuelve un hash "de firma" inventado.
Endpoints HTTP reales con THALOS real; BD desechable de tests.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_active_user
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.agent_activity import AgentActivity
from app.models.company import Company, UserCompany
from app.models.legal_document import LegalDocument
from app.models.user import User
from services.automation.handlers.justicia import handle_justicia_task
from services.workspaces.justicia_tools import sign_pdf_document


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _seed(db):
    suf = uuid.uuid4().hex[:8]
    c = Company(company_name=f"Sello {suf}", slug=f"sello-{suf}")
    u = User(email=f"sello_{suf}@example.test", hashed_password=get_password_hash("TestPass1"), is_active=True)
    db.add_all([c, u])
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=c.id, role="owner"))
    db.commit()
    db.refresh(u)
    return u, c


@pytest.fixture()
def as_user():
    def _as(user):
        app.dependency_overrides[get_current_active_user] = lambda: user
        return TestClient(app)

    yield _as
    app.dependency_overrides.pop(get_current_active_user, None)


def _draft(db, u, c):
    d = LegalDocument(user_id=u.id, company_id=c.id, doc_type="contract", content="x", status="draft")
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def test_sello_no_aprueba_el_borrador(db, as_user):
    u, c = _seed(db)
    d = _draft(db, u, c)
    r = as_user(u).post("/api/v1/justice/sign", json={"document_id": d.public_id, "document_name": "c.pdf"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_electronic_signature"] is False and body["approved"] is False
    assert "eIDAS" in body["legal_notice"]
    assert body["document_status"] == "draft" and len(body["integrity_hash"]) == 64
    db.expire_all()
    row = db.query(LegalDocument).filter(LegalDocument.id == d.id).one()
    assert row.status == "draft"
    assert row.signature_hash == body["integrity_hash"] and row.signed_at is not None


def test_sello_sin_documento_crea_integrity_sealed_de_la_empresa(db, as_user):
    u, c = _seed(db)
    r = as_user(u).post("/api/v1/justice/sign", json={"document_name": "acta.pdf", "file_hash": "ab" * 32})
    assert r.status_code == 200, r.text
    db.expire_all()
    row = db.query(LegalDocument).filter(LegalDocument.public_id == r.json()["document_id"]).one()
    assert row.status == "integrity_sealed" and row.doc_type == "integrity_seal"
    assert row.company_id == c.id


def test_workspace_texto_honesto(db, as_user):
    u, c = _seed(db)
    d = _draft(db, u, c)
    r = as_user(u).post(
        "/api/v1/workspaces/justicia/pdf-signer",
        json={"document_id": d.public_id, "document_name": "c.pdf", "file_hash": "cd" * 32},
    )
    assert r.status_code == 200, r.text
    text = r.json()["text"]
    assert text.startswith("Sello de integridad (hash)") and "eIDAS" in text
    assert "Firma digital" not in text and "completado correctamente" not in text
    db.expire_all()
    assert db.query(LegalDocument).filter(LegalDocument.id == d.id).one().status == "draft"


def test_sin_bd_no_inventa_hash():
    out = sign_pdf_document({"document_name": "x.pdf"})
    assert out["real_execution"] is False and out["stored_in_db"] is False
    assert "integrity_hash" not in out and "signature" not in out


def test_workflow_no_firma_ni_aprueba(db):
    u, c = _seed(db)
    d = _draft(db, u, c)
    act = AgentActivity(
        agent_name="JUSTICIA",
        action_type="task_assigned",
        action_description="revision",
        details={"document_id": d.public_id},
        user_email=u.email,
        status="pending",
    )
    db.add(act)
    db.commit()
    db.refresh(act)
    out = handle_justicia_task(act)
    assert out["status"] == "completed"
    sig = out["details_update"]["automation"]["signature"]
    assert sig["status"] == "no_real_logic" and sig["document_id"] == d.public_id
    assert out["metrics_update"]["documents_signed"] == 0
    assert "NO aplicado" in out["notes"]
    db.expire_all()
    row = db.query(LegalDocument).filter(LegalDocument.id == d.id).one()
    assert row.status == "draft" and row.signature_hash is None and row.signed_at is None
