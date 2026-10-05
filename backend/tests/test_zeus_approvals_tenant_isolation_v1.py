"""J1: aprobaciones humanas ZEUS aisladas por empresa, con rol y auditoria."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.core.security import get_password_hash
from app.db.base import Base, SessionLocal, engine
from app.main import app
from app.models.agent_activity import AgentActivity
from app.models.company import Company, UserCompany
from app.models.user import User
from app.models.zeus_pending_approval import ZeusPendingApproval
from services.zeus_human_approval_v1 import list_pending, request_approval


@pytest.fixture()
def db():
    Base.metadata.create_all(
        bind=engine,
        tables=[
            User.__table__,
            Company.__table__,
            UserCompany.__table__,
            ZeusPendingApproval.__table__,
            AgentActivity.__table__,
        ],
    )
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client():
    c = TestClient(app)
    try:
        yield c
    finally:
        app.dependency_overrides.clear()


def _seed(db: Session, tag: str, role: str = "owner", superuser: bool = False, company: Company | None = None):
    suf = uuid.uuid4().hex[:8]
    if company is None:
        company = Company(company_name=f"Appr {tag} {suf}", slug=f"appr-{tag}-{suf}")
        db.add(company)
        db.flush()
    user = User(
        email=f"appr_{tag}_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name=f"Appr {tag}",
        is_active=True,
        is_superuser=superuser,
    )
    db.add(user)
    db.flush()
    db.add(UserCompany(user_id=user.id, company_id=company.id, role=role))
    db.commit()
    db.refresh(user)
    db.refresh(company)
    return user, company


def _req(db, user, company):
    return request_approval(
        db, user=user, company_id=company.id, agent_name="RAFAEL",
        action_type="generate_invoice", payload={"amount": 900},
    )


def _as(user):
    app.dependency_overrides[get_current_active_user] = lambda: user


def test_request_without_company_rejected(db):
    user, _ = _seed(db, "a")
    before = db.query(ZeusPendingApproval).count()
    with pytest.raises(Exception) as e:
        request_approval(db, user=user, company_id=None, agent_name="ZEUS", action_type="send_campaign", payload={})
    assert e.value.status_code == 400
    assert db.query(ZeusPendingApproval).count() == before


def test_list_other_company_forbidden(db, client):
    ua, ca = _seed(db, "a")
    ub, cb = _seed(db, "b")
    _req(db, ub, cb)
    _as(ua)
    r = client.get(f"/api/v1/zeus-core/approvals/pending?company_id={cb.id}")
    assert r.status_code == 403
    r = client.get(f"/api/v1/zeus-core/approvals/pending?company_id={ca.id}")
    assert r.status_code == 200 and r.json()["pending"] == []
    with pytest.raises(Exception) as e:
        list_pending(db, user=ua, company_id=cb.id)
    assert e.value.status_code == 403


def test_list_own_company_ok(db, client):
    ub, cb = _seed(db, "b")
    row = _req(db, ub, cb)
    _as(ub)
    r = client.get("/api/v1/zeus-core/approvals/pending")
    assert r.status_code == 200
    assert [p["id"] for p in r.json()["pending"]] == [row.id]


def test_resolve_other_company_404_and_unchanged(db, client):
    ua, _ = _seed(db, "a")
    ub, cb = _seed(db, "b")
    row = _req(db, ub, cb)
    _as(ua)
    r = client.post(f"/api/v1/zeus-core/approvals/{row.id}/resolve", json={"approve": True})
    assert r.status_code == 404
    db.expire_all()
    assert db.get(ZeusPendingApproval, row.id).status == "pending"


def test_resolve_nonexistent_404_not_500(db, client):
    ua, _ = _seed(db, "a")
    _as(ua)
    r = client.post("/api/v1/zeus-core/approvals/99999999/resolve", json={"approve": True})
    assert r.status_code == 404


def test_resolve_insufficient_role_403(db, client):
    owner, cb = _seed(db, "b")
    member, _ = _seed(db, "bm", role="member", company=cb)
    row = _req(db, owner, cb)
    _as(member)
    r = client.post(f"/api/v1/zeus-core/approvals/{row.id}/resolve", json={"approve": True})
    assert r.status_code == 403
    db.expire_all()
    assert db.get(ZeusPendingApproval, row.id).status == "pending"


def test_resolve_happy_path_and_double_resolve_409(db, client):
    owner, cb = _seed(db, "b")
    row = _req(db, owner, cb)
    _as(owner)
    r = client.post(f"/api/v1/zeus-core/approvals/{row.id}/resolve", json={"approve": True})
    assert r.status_code == 200 and r.json()["status"] == "approved"
    db.expire_all()
    got = db.get(ZeusPendingApproval, row.id)
    assert got.status == "approved" and got.resolved_by_user_id == owner.id
    r = client.post(f"/api/v1/zeus-core/approvals/{row.id}/resolve", json={"approve": False})
    assert r.status_code == 409
    db.expire_all()
    assert db.get(ZeusPendingApproval, row.id).status == "approved"


def test_company_admin_can_reject(db, client):
    _, cb = _seed(db, "b")
    admin, _ = _seed(db, "badm", role="company_admin", company=cb)
    row = _req(db, admin, cb)
    _as(admin)
    r = client.post(f"/api/v1/zeus-core/approvals/{row.id}/resolve", json={"approve": False})
    assert r.status_code == 200 and r.json()["status"] == "rejected"


def test_activity_log_recorded_with_company(db, client):
    owner, cb = _seed(db, "b")
    row = _req(db, owner, cb)
    _as(owner)
    client.post(f"/api/v1/zeus-core/approvals/{row.id}/resolve", json={"approve": True})
    db.expire_all()
    acts = db.query(AgentActivity).filter(AgentActivity.company_id == cb.id).all()
    by_type = {a.action_type: a for a in acts}
    assert "approval_requested" in by_type and "approval_approved" in by_type
    a = by_type["approval_approved"]
    assert a.user_email == owner.email and a.agent_name == "RAFAEL"
    assert a.details["approval_id"] == row.id and a.status == "completed"
