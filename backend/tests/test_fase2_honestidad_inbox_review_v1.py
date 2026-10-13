"""Fase 2 / honestidad final — POST /api/v1/zeus/inbox/{id}/review.

Cierra la revision humana de las entradas de la bandeja de ZEUS (incluidas las asignadas a
AFRODITA/ZEUS, que no tenian flujo de cierre). Solo marca la revision y deja log: no
contabiliza, no envia nada. Aislamiento por empresa. THALOS real.
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
from app.models.document_approval import DocumentApproval
from app.models.user import User
from app.models.zeus_inbox_item import STATUS_CLASSIFIED, STATUS_PENDING_CLASSIFICATION, ZeusInboxItem


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def as_user():
    def _as(user):
        app.dependency_overrides[get_current_active_user] = lambda: user
        return TestClient(app)

    yield _as
    app.dependency_overrides.pop(get_current_active_user, None)


def _seed(db, tag, company=None, role="owner"):
    suf = uuid.uuid4().hex[:8]
    if company is None:
        company = Company(company_name=f"Rev {tag} {suf}", slug=f"rev-{tag}-{suf}")
        db.add(company)
        db.flush()
    u = User(email=f"rev_{tag}_{suf}@example.test", hashed_password=get_password_hash("TestPass1"), is_active=True)
    db.add(u)
    db.flush()
    db.add(UserCompany(user_id=u.id, company_id=company.id, role=role))
    db.commit()
    db.refresh(u)
    db.refresh(company)
    return u, company


def _item(db, user, company, agent="AFRODITA", classified=True):
    approval = None
    if classified:
        approval = DocumentApproval(
            user_id=user.id, company_id=company.id, agent_name=agent,
            document_type="zeus_inbox_nomina", status="pending_review",
        )
        approval.document_payload = {"source": "zeus_inbox"}
        approval.audit_log = [{"action": "assigned_by_zeus_inbox"}]
        db.add(approval)
        db.flush()
    item = ZeusInboxItem(
        company_id=company.id, user_id=user.id, original_filename="n.jpg", content_type="image/jpeg",
        size_bytes=10, sha256="0" * 64,
        status=STATUS_CLASSIFIED if classified else STATUS_PENDING_CLASSIFICATION,
        assigned_agent=agent if classified else None,
        document_approval_id=approval.id if approval else None,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item, approval


def P(i):
    return f"/api/v1/zeus/inbox/{i}/review"


def test_revisado_por_otro_miembro_de_la_empresa(db, as_user):
    owner, company = _seed(db, "own")
    member, _ = _seed(db, "mem", company=company, role="member")
    item, approval = _item(db, owner, company, agent="AFRODITA")
    r = as_user(member).post(P(item.id), json={"decision": "revisado", "note": "nomina correcta"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["item"]["review"]["status"] == "reviewed"
    assert "no lo ha enviado" in body["item"]["notice"]
    db.expire_all()
    a = db.query(DocumentApproval).filter(DocumentApproval.id == approval.id).one()
    assert a.status == "reviewed"
    assert a.sent_at is None and a.exported_at is None and a.filed_external_at is None and a.approved_at is None
    last = a.audit_log[-1]
    assert last["decision"] == "revisado" and last["user_id"] == member.id and last["note"] == "nomina correcta"
    log = (db.query(AgentActivity)
           .filter(AgentActivity.company_id == company.id, AgentActivity.action_type == "inbox_review_reviewed")
           .one())
    assert log.agent_name == "AFRODITA" and log.status == "completed"
    # ya cerrada -> 409
    r2 = as_user(owner).post(P(item.id), json={"decision": "descartado"})
    assert r2.status_code == 409


def test_descartado_zeus(db, as_user):
    u, c = _seed(db, "zeus")
    item, approval = _item(db, u, c, agent="ZEUS")
    r = as_user(u).post(P(item.id), json={"decision": "descartado"})
    assert r.status_code == 200, r.text
    db.expire_all()
    assert db.query(DocumentApproval).filter(DocumentApproval.id == approval.id).one().status == "discarded"


def test_otra_empresa_no_puede(db, as_user):
    u, c = _seed(db, "a")
    intruso, _ = _seed(db, "b")
    item, approval = _item(db, u, c)
    r = as_user(intruso).post(P(item.id), json={"decision": "descartado"})
    assert r.status_code == 404
    db.expire_all()
    assert db.query(DocumentApproval).filter(DocumentApproval.id == approval.id).one().status == "pending_review"


def test_validaciones(db, as_user):
    u, c = _seed(db, "val")
    item, _ = _item(db, u, c)
    assert as_user(u).post(P(item.id), json={"decision": "aprobado"}).status_code == 422
    pend, _ = _item(db, u, c, classified=False)
    assert as_user(u).post(P(pend.id), json={"decision": "revisado"}).status_code == 409


def test_sin_auth_401():
    app.dependency_overrides.pop(get_current_active_user, None)
    r = TestClient(app).post(P(1), json={"decision": "revisado"})
    assert r.status_code == 401
