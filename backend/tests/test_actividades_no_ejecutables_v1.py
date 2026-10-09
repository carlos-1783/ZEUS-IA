"""J3c: POST /activities/log (cliente) nunca produce actividades ejecutables por el
AgentAutomationExecutor. Solo se sustituyen efectos (resolve_handler / apply_signature) para
contar llamadas; el endpoint y el executor son los reales."""

from __future__ import annotations

import pytest

from app.main import app  # noqa: F401
from app.models.agent_activity import AgentActivity
from services import unified_agent_runtime as runtime
from services.activity_logger import ActivityLogger
from test_confirmacion_unica_v1 import _as, _run_executor_on
from test_chat_claves_servidor_v1 import _seed, client, db, sent  # noqa: F401

CASES = [
    ("JUSTICIA", "document_reviewed"),
    ("JUSTICIA", "compliance_check"),
    ("JUSTICIA", "task_assigned"),
    ("PERSEO", "ads_campaign_builder"),
    ("PERSEO", "image_analyzer"),
    ("RAFAEL", "invoice_sent"),
]


@pytest.fixture
def calls(monkeypatch):
    seen = {"handlers": [], "signatures": []}

    def fake_resolve(agent, action):
        def handler(activity):
            seen["handlers"].append((agent, action))
            return {"status": "completed", "notes": "stub"}
        return handler

    monkeypatch.setattr(runtime, "resolve_handler", fake_resolve)
    import services.signature_service as sig
    monkeypatch.setattr(sig, "apply_signature", lambda *a, **k: seen["signatures"].append(1))
    return seen


def _row(db, aid):
    db.expire_all()
    return db.query(AgentActivity).filter(AgentActivity.id == aid).one()


@pytest.mark.parametrize("agent,action", CASES)
def test_client_log_pending_is_not_executable(db, client, calls, agent, action):
    attacker, company = _seed(db, tag="att")
    victim, _ = _seed(db, tag="vic")
    _as(attacker)
    r = client.post("/api/v1/activities/log", json={
        "agent_name": agent, "action_type": action, "action_description": "forzado",
        "status": "pending",
        "details": {"user_id": victim.id, "_origin": "server", "document_id": 1, "payload": {"document_id": 1}},
    })
    assert r.status_code == 200, r.text
    aid = r.json()["activity_id"]
    act = _row(db, aid)
    assert act.status == "logged"  # no ejecutable
    assert act.details["_origin"] == "client_log"  # el cliente no puede sobreescribirlo
    assert act.details["_requested_status"] == "pending"
    assert act.user_email == attacker.email and act.company_id == company.id

    # Aunque algo lo dejara en pending (carrera/legado), el executor lo bloquea.
    act.status = "pending"
    db.commit()
    _run_executor_on(aid)
    act = _row(db, aid)
    assert act.status == "blocked_client_origin"
    assert act.details["blocked_reason"] == "client_origin_not_executable" and act.details["executed"] is False
    assert calls["handlers"] == [] and calls["signatures"] == []
    log = (db.query(AgentActivity)
           .filter(AgentActivity.action_type == "automation_blocked",
                   AgentActivity.status == "blocked_client_origin",
                   AgentActivity.company_id == company.id).all())
    assert any(l.details.get("original_activity_id") == aid for l in log)


def test_in_progress_also_downgraded(db, client, calls):
    user, _ = _seed(db)
    _as(user)
    r = client.post("/api/v1/activities/log", json={
        "agent_name": "PERSEO", "action_type": "ads_campaign_builder", "action_description": "x",
        "status": "in_progress"})
    assert _row(db, r.json()["activity_id"]).status == "logged"


def test_internal_activity_without_client_origin_still_executes(db, calls):
    """Uso legitimo: teamflow_engine.run_workflow / playbooks crean via ActivityLogger en proceso."""
    user, company = _seed(db)
    act = ActivityLogger.log_activity(
        agent_name="JUSTICIA", action_type="document_reviewed", action_description="[TeamFlow:x] paso",
        details={"workflow_id": "x", "step_id": "s1"}, status="in_progress", user_email=user.email)
    _run_executor_on(act.id)
    assert calls["handlers"] == [("JUSTICIA", "document_reviewed")]
    assert _row(db, act.id).status == "completed"


def test_superuser_keeps_documented_capability(db, client, calls):
    admin, _ = _seed(db, tag="adm")
    admin.is_superuser = True
    db.commit()
    _as(admin)
    r = client.post("/api/v1/activities/log", json={
        "agent_name": "JUSTICIA", "action_type": "document_reviewed", "action_description": "admin",
        "status": "pending", "details": {"_origin": "client_log"}})
    aid = r.json()["activity_id"]
    act = _row(db, aid)
    assert act.status == "pending" and act.details["_origin"] == "superuser_log"
    _run_executor_on(aid)
    assert calls["handlers"] == [("JUSTICIA", "document_reviewed")]


def test_completed_status_from_client_is_kept(db, client, calls):
    user, _ = _seed(db)
    _as(user)
    r = client.post("/api/v1/activities/log", json={
        "agent_name": "ZEUS", "action_type": "note", "action_description": "n", "status": "completed"})
    assert _row(db, r.json()["activity_id"]).status == "completed"


@pytest.mark.parametrize("modpath", [
    "services.automation.handlers.justicia", "services.teamflow_real_handlers_v1"])
def test_user_from_activity_ignores_foreign_user_id(db, modpath):
    import importlib
    mod = importlib.import_module(modpath)
    a, _ = _seed(db, tag="a")
    b, _ = _seed(db, tag="b")
    act = AgentActivity(agent_name="JUSTICIA", action_type="x", action_description="x",
                        user_email=a.email, details={"user_id": b.id}, status="pending")
    assert mod._user_from_activity(db, act).id == a.id
    own = AgentActivity(agent_name="JUSTICIA", action_type="x", action_description="x",
                        user_email=a.email, details={"user_id": a.id}, status="pending")
    assert mod._user_from_activity(db, own).id == a.id
    internal = AgentActivity(agent_name="JUSTICIA", action_type="x", action_description="x",
                             user_email=None, details={"user_id": b.id}, status="pending")
    assert mod._user_from_activity(db, internal).id == b.id
