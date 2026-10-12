"""Fase 2 / Step 2 — export format=pdf devolvia JSON. Ahora PDF real (y solo del dueno)."""

from __future__ import annotations

import base64
import uuid

from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.company import Company, UserCompany
from app.models.document_approval import DocumentApproval
from app.models.user import User

P = "/api/v1/documents"


def _seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    suf = uuid.uuid4().hex[:8]
    c = Company(company_name=f"Pdf {suf}", slug=f"pdf-{suf}")
    u = User(email=f"pdf_{suf}@example.com", hashed_password=get_password_hash("TestPass1"), is_active=True)
    other = User(email=f"pdf2_{suf}@example.com", hashed_password=get_password_hash("TestPass1"), is_active=True)
    db.add_all([c, u, other])
    db.flush()
    db.add_all([UserCompany(user_id=u.id, company_id=c.id, role="owner"),
                UserCompany(user_id=other.id, company_id=c.id, role="member")])
    doc = DocumentApproval(user_id=u.id, company_id=c.id, agent_name="RAFAEL", document_type="fiscal_document",
                           document_payload={"title": "F-9", "total": 121.0, "lineas": [{"concepto": "Menu", "importe": 100}]},
                           status="approved", fiscal_document_type="factura")
    db.add(doc)
    db.commit()
    out = (u.email, other.email, doc.id)
    db.close()
    return out


def _h(client, email):
    tok = client.post("/api/v1/auth/login", data={"username": email, "password": "TestPass1"}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def test_pdf_export_is_a_real_pdf():
    email, _, doc_id = _seed()
    client = TestClient(app)
    r = client.post(f"{P}/{doc_id}/export?format=pdf", headers=_h(client, email))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["content_type"] == "application/pdf" and body["filename"].endswith(".pdf")
    assert body["export_encoding"] == "base64"
    pdf = base64.b64decode(body["export_data"])
    assert pdf.startswith(b"%PDF-") and len(pdf) > 500


def test_export_of_someone_elses_document_is_404():
    _, other_email, doc_id = _seed()
    client = TestClient(app)
    r = client.post(f"{P}/{doc_id}/export?format=pdf", headers=_h(client, other_email))
    assert r.status_code == 404
