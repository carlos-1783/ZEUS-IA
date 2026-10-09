"""J2: confirmacion humana real. Sin bypass force_execute; el servidor ejecuta tras
la aprobacion del MISMO usuario, una sola vez, con resultado real y auditoria."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi import HTTPException
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
from services.zeus_human_approval_v1 import execute_approval, request_approval

BASE = "/api/v1/zeus-core"


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    from app.db.base import _migrate_zeus_approvals_execution_columns

    _migrate_zeus_approvals_execution_columns()  # BD local pre-J2 sin las columnas nuevas
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


@pytest.fixture()
def invoice_flow(monkeypatch):
    """Solo se sustituye la generacion del PDF (E/S pesada); registra cada llamada."""
    calls = []

    def _flow(db, *, user, invoice_id, company_id=None):
        calls.append({"invoice_id": invoice_id, "user_id": user.id})
        return {"pdf": f"inv_{invoice_id}.pdf"}

    monkeypatch.setattr("services.rafael_fiscal_engine_v2.generate_invoice_pdf_flow", _flow)
    return calls


def _seed(db: Session, tag: str, role: str = "owner", superuser: bool = False, company=None):
    suf = uuid.uuid4().hex[:8]
    if company is None:
        company = Company(company_name=f"J2 {tag} {suf}", slug=f"j2-{tag}-{suf}")
        db.add(company)
        db.flush()
    user = User(
        email=f"j2_{tag}_{suf}@example.test",
        hashed_password=get_password_hash("TestPass1"),
        full_name=f"J2 {tag}",
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


def _as(user):
    app.dependency_overrides[get_current_active_user] = lambda: user


def _execute(client, **extra):
    body = {"agent": "RAFAEL", "action": "generate_invoice", "payload": {"invoice_id": 77}, **extra}
    return client.post(f"{BASE}/agent/execute", json=body)


def _pending(db, cid):
    return db.query(ZeusPendingApproval).filter(ZeusPendingApproval.company_id == cid).all()


def test_force_execute_from_client_does_not_execute(db, client, invoice_flow):
    owner, co = _seed(db, "fe")
    _as(owner)
    r = _execute(client, force_execute=True)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["executed"] is False and body["needs_approval"] is True
    assert invoice_flow == []  # _dispatch/flow no llamado
    rows = _pending(db, co.id)
    assert len(rows) == 1 and rows[0].status == "pending" and rows[0].user_id == owner.id


def test_same_user_approve_executes_stored_payload_once(db, client, invoice_flow):
    owner, co = _seed(db, "ok")
    _as(owner)
    aid = _execute(client).json()["approval_id"]
    assert invoice_flow == []
    r = client.post(f"{BASE}/approvals/{aid}/resolve", json={"approve": True})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "executed" and r.json()["result"]["executed"] is True
    assert invoice_flow == [{"invoice_id": 77, "user_id": owner.id}]
    db.expire_all()
    row = db.get(ZeusPendingApproval, aid)
    assert row.status == "executed" and row.executed_at is not None and "inv_77.pdf" in row.result_json
    # segundo approve -> 409 y sin segunda ejecucion
    r2 = client.post(f"{BASE}/approvals/{aid}/resolve", json={"approve": True})
    assert r2.status_code == 409
    assert len(invoice_flow) == 1
    # auditoria con company_id
    types = {a.action_type: a for a in db.query(AgentActivity).filter(AgentActivity.company_id == co.id)}
    assert "approval_executed" in types and types["approval_executed"].status == "completed"
    assert "agent_action_generate_invoice" in types
    assert types["agent_action_generate_invoice"].details["approval_id"] == aid


def test_execute_approval_claim_is_atomic(db, invoice_flow):
    owner, co = _seed(db, "atom")
    row = request_approval(
        db, user=owner, company_id=co.id, agent_name="RAFAEL",
        action_type="generate_invoice", payload={"invoice_id": 5},
    )
    # una segunda reclamacion con la fila ya consumida no ejecuta
    from services.zeus_human_approval_v1 import resolve_approval

    resolve_approval(db, approval_id=row.id, user=owner, approve=True)
    asyncio.run(execute_approval(db, row=row, user=owner))
    with pytest.raises(HTTPException) as e:
        asyncio.run(execute_approval(db, row=row, user=owner))
    assert e.value.status_code == 409
    assert len(invoice_flow) == 1


def test_other_user_same_company_cannot_approve(db, client, invoice_flow):
    owner, co = _seed(db, "req")
    admin, _ = _seed(db, "adm", role="company_admin", company=co)
    _as(owner)
    aid = _execute(client).json()["approval_id"]
    _as(admin)
    r = client.post(f"{BASE}/approvals/{aid}/resolve", json={"approve": True})
    assert r.status_code == 403
    assert invoice_flow == []
    db.expire_all()
    assert db.get(ZeusPendingApproval, aid).status == "pending"


def test_superuser_cannot_execute_on_behalf(db, client, invoice_flow):
    owner, co = _seed(db, "req")
    root, _ = _seed(db, "root", role="owner", superuser=True, company=co)
    _as(owner)
    aid = _execute(client).json()["approval_id"]
    _as(root)
    r = client.post(f"{BASE}/approvals/{aid}/resolve", json={"approve": True})
    assert r.status_code == 403 and invoice_flow == []


def test_member_cannot_even_request_critical_action(db, client, invoice_flow):
    _, co = _seed(db, "own")
    member, _ = _seed(db, "mem", role="member", company=co)
    _as(member)
    r = _execute(client)
    assert r.status_code == 403
    assert _pending(db, co.id) == []
    assert invoice_flow == []


def test_failed_execution_marks_failed_with_real_error(db, client, invoice_flow):
    owner, co = _seed(db, "fail")
    _as(owner)
    r = client.post(f"{BASE}/agent/execute", json={"agent": "RAFAEL", "action": "generate_invoice", "payload": {}})
    aid = r.json()["approval_id"]  # sin invoice_id: el executor devolvera error real
    r = client.post(f"{BASE}/approvals/{aid}/resolve", json={"approve": True})
    assert r.status_code == 422
    body = r.json()
    assert body["success"] is False and body["status"] == "failed" and "invoice_id" in body["error"]
    db.expire_all()
    row = db.get(ZeusPendingApproval, aid)
    assert row.status == "failed" and "invoice_id" in row.result_json
    # el fallo no se puede reintentar (ya consumida)
    assert client.post(f"{BASE}/approvals/{aid}/resolve", json={"approve": True}).status_code == 409


def test_exception_in_action_marks_failed(db, client, monkeypatch):
    def _boom(db, *, user, invoice_id, company_id=None):
        raise HTTPException(status_code=404, detail="Factura no encontrada.")

    monkeypatch.setattr("services.rafael_fiscal_engine_v2.generate_invoice_pdf_flow", _boom)
    owner, co = _seed(db, "exc")
    _as(owner)
    aid = _execute(client).json()["approval_id"]
    r = client.post(f"{BASE}/approvals/{aid}/resolve", json={"approve": True})
    assert r.status_code == 422 and r.json()["status"] == "failed"
    assert "Factura no encontrada" in r.json()["error"]
    db.expire_all()
    assert db.get(ZeusPendingApproval, aid).status == "failed"


def test_reject_does_not_execute(db, client, invoice_flow):
    owner, co = _seed(db, "rej")
    _as(owner)
    aid = _execute(client).json()["approval_id"]
    r = client.post(f"{BASE}/approvals/{aid}/resolve", json={"approve": False})
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    assert invoice_flow == []
    db.expire_all()
    assert db.get(ZeusPendingApproval, aid).status == "rejected"


def test_admin_can_reject_others_request_member_cannot(db, client, invoice_flow):
    owner, co = _seed(db, "req")
    admin, _ = _seed(db, "adm", role="company_admin", company=co)
    member, _ = _seed(db, "mem", role="member", company=co)
    _as(owner)
    a1 = _execute(client).json()["approval_id"]
    a2 = _execute(client).json()["approval_id"]
    _as(member)
    assert client.post(f"{BASE}/approvals/{a1}/resolve", json={"approve": False}).status_code == 403
    _as(admin)
    assert client.post(f"{BASE}/approvals/{a2}/resolve", json={"approve": False}).status_code == 200
    assert invoice_flow == []


def test_cross_tenant_still_404(db, client, invoice_flow):
    ua, _ = _seed(db, "a")
    ub, cb = _seed(db, "b")
    _as(ub)
    aid = _execute(client).json()["approval_id"]
    _as(ua)
    assert client.post(f"{BASE}/approvals/{aid}/resolve", json={"approve": True}).status_code == 404
    assert client.post(f"{BASE}/approvals/{aid}/resolve", json={"approve": False}).status_code == 404
    assert invoice_flow == []
    db.expire_all()
    assert db.get(ZeusPendingApproval, aid).status == "pending"


def test_noncritical_direct_execution_is_logged(db, client):
    owner, co = _seed(db, "nc")
    _as(owner)
    r = client.post(f"{BASE}/agent/execute", json={"agent": "ZEUS", "action": "get_metrics", "payload": {}})
    assert r.status_code == 200, r.text
    acts = db.query(AgentActivity).filter(
        AgentActivity.company_id == co.id, AgentActivity.action_type == "agent_action_get_metrics"
    ).all()
    assert len(acts) == 1 and acts[0].status == "completed"
