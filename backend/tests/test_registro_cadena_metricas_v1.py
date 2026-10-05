"""J7 (correcciones): las trazas de cadena no alteran metricas/uptime; el chat correcto cuenta como
completado; el turno de ZEUS conserva su fila visible; el lanzamiento de ZEUS lleva empresa real."""

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
from app.models.user import User
from services import zeus_orchestrator_service as orch
from services.activity_logger import ActivityLogger
from tests.test_registro_cadena_v1 import CAMPAIGN, RAFAEL, ZEUS, _by_step, _chat, _rows, _seed  # noqa: F401
from tests.test_registro_cadena_v1 import client, db, sent  # noqa: F401


@pytest.fixture()
def model_ok(monkeypatch):
    monkeypatch.setattr("agents.base_agent.chat_completion", lambda messages=None, **k: {
        "success": True, "content": "ok", "model": "stub", "usage": {"total_tokens": 1},
        "cost": 0.0, "elapsed_time": 0.0, "timestamp": "2026-01-01T00:00:00"})


def test_correct_chat_counts_completed_and_chain_rows_do_not_dilute(db, client, model_ok):
    user, _ = _seed(db)
    body = _chat(client, user, "hola", url=RAFAEL)
    assert body["success"] is True
    steps = _by_step(_rows(db, user, body["request_id"]))
    assert len(steps) >= 4  # hay varias filas chain_* ocultas para esta peticion
    visible = [r for r in _rows(db, user, body["request_id"]) if r.action_type == "chat_request_processed"]
    assert visible and visible[0].status == "completed"

    st = client.get("/api/v1/agents/status").json()
    assert st["agents"]["RAFAEL"]["uptime"] == "100.00%"
    assert st["agents"]["RAFAEL"]["decisions_last_30d"] == 1  # solo la actividad de negocio

    perf = client.get("/api/v1/metrics/performance", params={"agent": "RAFAEL"}).json()
    assert perf["total_activities"] == 1 and perf["success_rate"] == "100.0%"

    summ = client.get("/api/v1/metrics/summary").json()["metrics"]
    assert summ["total_interactions"] == 1 and summ["success_rate"] == "100.0%"

    m = ActivityLogger.get_agent_metrics("RAFAEL", user_email=user.email)
    assert m["total_actions"] == 1 and m["completed"] == 1 and m["success_rate"] == 100


def test_failed_chat_still_counts_failed(db, client, monkeypatch):
    user, _ = _seed(db)

    def _boom(messages, **kw):
        raise RuntimeError("caido")

    monkeypatch.setattr("agents.base_agent.chat_completion", _boom)
    _chat(client, user, "hola", url=RAFAEL)
    st = client.get("/api/v1/agents/status").json()
    assert st["agents"]["RAFAEL"]["uptime"] == "0.00%"


def test_zeus_bridge_turn_keeps_visible_row(db, client, sent):
    user, co = _seed(db)
    thread = "v-" + uuid.uuid4().hex[:6]
    first = _chat(client, user, CAMPAIGN, thread=thread)
    vis = [r for r in _rows(db, user, first["request_id"])
           if r.action_type == "chat_request_processed" and r.visible_to_client]
    assert len(vis) == 1 and vis[0].status == "completed" and vis[0].company_id == co.id
    second = _chat(client, user, "confirmar", thread=thread)
    rows2 = _rows(db, user, second["request_id"])
    # ejecutado via aprobacion: ya hay approval_executed visible; no se duplica con chat_request_processed
    assert any(r.action_type == "approval_executed" and r.visible_to_client for r in rows2)
    assert not [r for r in rows2 if r.action_type == "chat_request_processed"]
    # turno fallido (sin pending): fila visible failed
    third = _chat(client, user, "confirmar", thread=thread)
    v3 = [r for r in _rows(db, user, third["request_id"]) if r.action_type == "chat_request_processed"]
    assert len(v3) == 1 and v3[0].status == "failed" and v3[0].visible_to_client


def test_zeus_launch_started_uses_explicit_company(db, monkeypatch):
    """Superusuario sin UserCompany: se usa la empresa interna; sin ninguna, no se lanza."""
    from app import main as m
    from services.internal_company_bootstrap import INTERNAL_COMPANY_SLUG

    for u in db.query(User).filter(User.is_superuser == True).all():  # noqa: E712
        u.is_superuser = False
    su = User(email=f"su_{uuid.uuid4().hex[:6]}@example.test", hashed_password=get_password_hash("TestPass1"),
              full_name="su", is_active=True, is_superuser=True)
    db.add(su)
    db.commit()
    internal = db.query(Company).filter(Company.slug == INTERNAL_COMPANY_SLUG).first()
    if internal is None:
        internal = Company(company_name="Interna", slug=INTERNAL_COMPANY_SLUG)
        db.add(internal)
        db.commit()
    from services import unified_agent_runtime as rt

    seen = []
    handler = lambda a, t: (lambda act: seen.append(act.company_id) or {"status": "completed"})  # noqa: E731
    monkeypatch.setattr(m, "resolve_handler", handler)
    monkeypatch.setattr(rt, "resolve_handler", handler)
    monkeypatch.setattr(rt, "persist_operational_state", lambda *a, **k: None)
    monkeypatch.setattr(rt, "append_decision_log", lambda *a, **k: None)
    monkeypatch.setattr(rt, "memory_load", lambda *a, **k: {})
    m._execute_zeus_launch_started()
    assert seen == [internal.id]
    row = (db.query(AgentActivity).filter(AgentActivity.user_email == su.email,
                                          AgentActivity.action_type == "zeus_launch_started").first())
    assert row.company_id == internal.id and row.status == "completed"
