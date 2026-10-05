"""J3b: UN unico estado de confirmacion (zeus_pending_approvals) compartido por el chat y la
barra de decision del workspace. Solo se sustituye el envio externo de email (contador)."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.auth import get_current_active_user
from app.main import app
from app.models.customer import Customer
from app.models.zeus_pending_approval import ZeusPendingApproval
from services import zeus_orchestrator_service as orch
from test_chat_claves_servidor_v1 import CAMPAIGN, _chat, _seed, client, db, sent  # noqa: F401

BASE = "/api/v1/zeus-core"


def _row(db, aid):
    db.expire_all()
    return db.query(ZeusPendingApproval).filter(ZeusPendingApproval.id == aid).one()


def _count_customers(db, company_id):
    db.expire_all()
    return db.query(Customer).filter(Customer.company_id == company_id).count()


def _preview(client, user, thread, msg=CAMPAIGN):
    r = _chat(client, user, msg, thread=thread).json()
    assert r["needs_confirmation"] is True and r["approval_id"]
    return r["approval_id"]


def _as(user):
    app.dependency_overrides[get_current_active_user] = lambda: user


def test_preview_creates_pending_row_visible_in_workspace_bar(db, client, sent):
    user, company = _seed(db)
    aid = _preview(client, user, "bar-" + uuid.uuid4().hex[:6])
    row = _row(db, aid)
    assert (row.status, row.company_id, row.user_id, row.action_type, row.agent_name) == (
        "pending", company.id, user.id, "send_campaign", "ZEUS")
    assert row.thread_id.endswith(f":u{user.id}") and row.expires_at is not None
    assert "_zeus_context" not in row.payload_json
    _as(user)
    pend = client.get(f"{BASE}/approvals/pending").json()["pending"]
    assert aid in [p["id"] for p in pend]
    assert sent == []


def test_confirm_executes_once_and_row_executed_with_result(db, client, sent):
    user, _ = _seed(db)
    thread = "ok-" + uuid.uuid4().hex[:6]
    aid = _preview(client, user, thread)
    c = _chat(client, user, "confirmar", thread=thread).json()
    assert c["executed_action"] is True and c["approval_id"] == aid
    assert len(sent) == 1
    row = _row(db, aid)
    assert row.status == "executed" and row.executed_at is not None
    assert json.loads(row.result_json)["result"]["executed"] is True
    assert _chat(client, user, "confirmar", thread=thread).json()["executed_action"] is False
    assert len(sent) == 1


def test_double_confirmation_executes_once(db, client, sent):
    user, _ = _seed(db)
    thread = "dbl-" + uuid.uuid4().hex[:6]
    aid = _preview(client, user, thread)
    _as(user)
    r1 = client.post(f"{BASE}/approvals/{aid}/resolve", json={"approve": True})
    r2 = client.post(f"{BASE}/approvals/{aid}/resolve", json={"approve": True})
    assert r1.status_code == 200 and r2.status_code == 409
    assert _chat(client, user, "confirmar", thread=thread).json()["executed_action"] is False
    assert len(sent) == 1


def test_other_user_same_company_cannot_confirm_row(db, client, sent):
    a, company = _seed(db, tag="a")
    b, _ = _seed(db, company=company, tag="b")
    thread = "ou-" + uuid.uuid4().hex[:6]
    aid = _preview(client, a, thread)
    assert _chat(client, b, "confirmar", thread=thread).json()["executed_action"] is False
    _as(b)
    assert client.post(f"{BASE}/approvals/{aid}/resolve", json={"approve": True}).status_code == 403
    assert sent == [] and _row(db, aid).status == "pending"


def test_other_company_same_thread_id_cannot_confirm(db, client, sent):
    a, _ca = _seed(db, tag="a")
    b, _cb = _seed(db, tag="b")
    thread = "same-thread"
    aid = _preview(client, a, thread)
    assert _chat(client, b, "confirmar", thread=thread).json()["executed_action"] is False
    _as(b)
    assert client.post(f"{BASE}/approvals/{aid}/resolve", json={"approve": True}).status_code == 404
    assert client.get(f"{BASE}/approvals/pending").json()["pending"] == []
    assert sent == [] and _row(db, aid).status == "pending"
    assert _chat(client, a, "confirmar", thread=thread).json()["executed_action"] is True
    assert len(sent) == 1


@pytest.mark.parametrize("phrase", [
    "confirmar que no", "ejecutar no", "adelante con otra cosa", "ejecuta el informe", "ok confirmar nada",
])
def test_ambiguous_phrases_do_not_confirm(db, client, sent, phrase, monkeypatch):
    import services.unified_agent_runtime as runtime

    # Sin LLM real: las frases ambiguas caen al camino conversacional.
    monkeypatch.setattr(
        runtime, "run_chat",
        lambda *a, **k: {"success": True, "message": "stub", "agent": "ZEUS CORE"},
    )
    from services.intent_parser import is_affirmative_message, is_confirmation_message

    assert not is_confirmation_message(phrase) and not is_affirmative_message(phrase)
    user, _ = _seed(db)
    aid = _preview(client, user, "amb-" + uuid.uuid4().hex[:6])
    thread_msg = _chat  # mismo hilo: se reutiliza el thread del preview via row.thread_id
    row = _row(db, aid)
    thread = row.thread_id.rsplit(":u", 1)[0]
    r = thread_msg(client, user, phrase, thread=thread).json()
    assert not r.get("executed_action")
    assert sent == []
    row = _row(db, aid)
    assert row.status == "rejected" and "cambio de tema" in row.result_json


def test_strict_confirmation_phrases_accepted():
    from services.intent_parser import is_affirmative_message, is_cancel_message, is_confirmation_message

    for ok in ("confirmar", "Confirmo.", "sí, confirmo", "ejecutar", "Adelante!", "ok confirmar"):
        assert is_confirmation_message(ok), ok
    for ok in ("sí", "Si.", "ok"):
        assert is_affirmative_message(ok), ok
    for ok in ("no", "cancelar", "No."):
        assert is_cancel_message(ok), ok
    assert not is_cancel_message("no me cambies el texto")


def test_cancel_rejects_row(db, client, sent):
    user, _ = _seed(db)
    thread = "can-" + uuid.uuid4().hex[:6]
    aid = _preview(client, user, thread)
    r = _chat(client, user, "cancelar", thread=thread).json()
    assert r["executed_action"] is False and r["success"] is True
    row = _row(db, aid)
    assert row.status == "rejected" and "cancelado" in row.result_json
    assert _chat(client, user, "confirmar", thread=thread).json()["executed_action"] is False
    assert sent == []


def test_workspace_resolve_of_chat_preview_executes_same_state(db, client, sent):
    user, _ = _seed(db)
    thread = "ws-" + uuid.uuid4().hex[:6]
    aid = _preview(client, user, thread)
    _as(user)
    r = client.post(f"{BASE}/approvals/{aid}/resolve", json={"approve": True})
    assert r.status_code == 200 and r.json()["status"] == "executed"
    assert len(sent) == 1
    assert _chat(client, user, "confirmar", thread=thread).json()["executed_action"] is False
    assert len(sent) == 1


def test_workspace_reject_blocks_chat_confirmation(db, client, sent):
    user, _ = _seed(db)
    thread = "wsr-" + uuid.uuid4().hex[:6]
    aid = _preview(client, user, thread)
    _as(user)
    assert client.post(f"{BASE}/approvals/{aid}/resolve", json={"approve": False}).json()["status"] == "rejected"
    assert _chat(client, user, "confirmar", thread=thread).json()["executed_action"] is False
    assert sent == []


def test_expired_row_cannot_be_approved_from_workspace(db, client, sent):
    user, _ = _seed(db)
    aid = _preview(client, user, "exp-" + uuid.uuid4().hex[:6])
    row = _row(db, aid)
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    _as(user)
    assert client.get(f"{BASE}/approvals/pending").json()["pending"] == []
    assert client.post(f"{BASE}/approvals/{aid}/resolve", json={"approve": True}).status_code == 409
    assert sent == [] and _row(db, aid).status == "rejected"


def test_legacy_operational_pending_is_ignored_and_discarded(db, client, sent):
    from services.agent_memory_service import persist_operational_state

    user, company = _seed(db)
    thread = "leg-" + uuid.uuid4().hex[:6]
    key = orch._pending_thread_key(user, {"thread_id": thread})
    persist_operational_state(
        str(company.id), orch.AGENT_ZEUS, key, status="awaiting_confirmation",
        artifacts={orch.PENDING_ACTION_KEY: {"action_type": "send_campaign", "payload": {}, "_pending_at": 9e12}},
    )
    assert _chat(client, user, "confirmar", thread=thread).json()["executed_action"] is False
    assert sent == []
    assert orch.memory_load(str(company.id), orch.AGENT_ZEUS, key)["operational"]["artifacts"] == {}


def test_create_customer_via_agent_execute_is_pending_not_created(db, client):
    user, company = _seed(db, with_customer=False)
    _as(user)
    r = client.post(f"{BASE}/agent/execute", json={
        "agent": "ZEUS", "action": "create_customer",
        "payload": {"name": "Ana", "email": f"ana_{uuid.uuid4().hex[:6]}@example.com"},
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["needs_approval"] is True and body["executed"] is False
    assert _count_customers(db, company.id) == 0
    assert _row(db, body["approval_id"]).status == "pending"
    ok = client.post(f"{BASE}/approvals/{body['approval_id']}/resolve", json={"approve": True})
    assert ok.status_code == 200, ok.text
    assert _count_customers(db, company.id) == 1


def test_invalid_email_fails_controlled_no_500(db, client):
    user, company = _seed(db, with_customer=False)
    _as(user)
    r = client.post(f"{BASE}/agent/execute", json={
        "agent": "ZEUS", "action": "create_customer", "payload": {"name": "Ana", "email": "no-es-un-email"},
    })
    aid = r.json()["approval_id"]
    res = client.post(f"{BASE}/approvals/{aid}/resolve", json={"approve": True})
    assert res.status_code == 422, res.text
    row = _row(db, aid)
    assert row.status == "failed" and "email" in json.loads(row.result_json)["error"].lower()
    assert _count_customers(db, company.id) == 0


def test_member_cannot_request_send_campaign_but_can_create_customer(db, client, sent):
    _owner, company = _seed(db, tag="own")
    member, _ = _seed(db, company=company, tag="mem", role="member")
    r = _chat(client, member, CAMPAIGN, thread="mem-" + uuid.uuid4().hex[:6]).json()
    assert r["success"] is False and r["executed_action"] is False
    assert "permiso" in r["message"].lower() and not r.get("approval_id")
    db.expire_all()
    assert db.query(ZeusPendingApproval).filter(ZeusPendingApproval.user_id == member.id).count() == 0
    thread = "memcc-" + uuid.uuid4().hex[:6]
    aid = _preview(client, member, thread, f"crear cliente Juan juan_{uuid.uuid4().hex[:6]}@example.com")
    assert _chat(client, member, "confirmar", thread=thread).json()["executed_action"] is True
    assert _row(db, aid).status == "executed"
    assert sent == []


def test_persistence_failure_is_fail_closed(db, client, sent, monkeypatch):
    user, _ = _seed(db)
    real_request = orch.request_approval
    real_resolve = orch.resolve_approval

    def boom(*a, **k):
        raise RuntimeError("db caida")

    monkeypatch.setattr(orch, "request_approval", boom)
    r = _chat(client, user, CAMPAIGN).json()
    assert r["success"] is False and r["executed_action"] is False
    assert not r.get("needs_confirmation") and sent == []

    monkeypatch.setattr(orch, "request_approval", real_request)
    thread = "fc-" + uuid.uuid4().hex[:6]
    aid = _preview(client, user, thread)
    monkeypatch.setattr(orch, "resolve_approval", boom)
    r2 = _chat(client, user, "confirmar", thread=thread).json()
    assert r2["success"] is False and r2["executed_action"] is False and sent == []
    monkeypatch.setattr(orch, "resolve_approval", real_resolve)
    assert _row(db, aid).status == "pending"
