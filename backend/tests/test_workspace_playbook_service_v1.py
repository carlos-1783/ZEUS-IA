"""Tests workspace_playbook_service_v1 auto-persist loop."""

from __future__ import annotations

import os
import uuid
from unittest.mock import patch

import pytest

from app.db.base import Base, SessionLocal, engine
from app.models.user import User
from services.workspace_playbook_service_v1 import (
    create_playbook,
    list_playbooks,
    persist_execution_playbook,
)
from services.workspace_playbook_writer_v1 import write_ops_playbook, write_rrhh_playbook


@pytest.fixture()
def db():
    from app.models.workspace_playbook import WorkspacePlaybook

    WorkspacePlaybook.__table__.drop(bind=engine, checkfirst=True)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def user(db):
    u = User(
        email=f"ws-pb-{uuid.uuid4().hex}@test.local",
        hashed_password="x",
        is_active=True,
        is_superuser=False,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_create_and_list_playbook(db, user):
    with patch.dict(os.environ, {"AFRODITA_WORKSPACE_ENABLED": "true"}, clear=False):
        row = create_playbook(
            db,
            user,
            title="Test OPS",
            content={"summary": "ok"},
            agent_source="ops",
        )
        db.commit()
        out = list_playbooks(db, user)
    assert row.id is not None
    assert out["count"] == 1
    assert out["playbooks"][0]["agent_source"] == "ops"


def test_auto_persist_rrhh_and_ops(db, user):
    with patch.dict(os.environ, {"AFRODITA_WORKSPACE_ENABLED": "true"}, clear=False):
        write_rrhh_playbook(
            db,
            user,
            action="qr_check_in",
            title="Fichaje",
            payload={"checkin_id": 1},
        )
        write_ops_playbook(
            db,
            user,
            action="create_movement",
            title="Movimiento",
            payload={"movement_id": 2},
        )
        db.commit()
        out = list_playbooks(db, user)
    assert out["count"] == 2
    sources = {p["agent_source"] for p in out["playbooks"]}
    assert sources == {"rrhh", "ops"}


def test_persist_execution_playbook_disabled():
    with patch("services.workspace_playbook_service_v1.workspace_enabled", return_value=False):
        assert persist_execution_playbook(
            None,
            None,  # type: ignore[arg-type]
            agent_source="rrhh",
            action="x",
            title="t",
            payload={},
        ) is None
