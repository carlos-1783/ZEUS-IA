"""Tests afrodita workspace DB service."""

from __future__ import annotations

import json
import os
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.db.base import Base, SessionLocal, engine
from app.models.user import User
from app.models.workspace_playbook import WorkspacePlaybook
from services.afrodita_workspace_db_service_v1 import (
    list_workspace_files,
    list_workspace_playbooks,
    persist_workspace_playbook,
    workspace_connection_status,
)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def user(db):
    u = User(
        email=f"afrodita-ws-{uuid.uuid4().hex}@test.local",
        hashed_password="x",
        is_active=True,
        is_superuser=False,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_workspace_connection_status_enabled():
    with patch.dict(os.environ, {"AFRODITA_WORKSPACE_ENABLED": "true"}, clear=False):
        db = MagicMock()
        db.execute.return_value = None
        status = workspace_connection_status(db)
    assert status["enabled"] is True
    assert status["connected"] is True
    assert status["status"] == "REAL"


def test_list_files_and_playbooks_empty(db, user):
    with patch.dict(os.environ, {"AFRODITA_WORKSPACE_ENABLED": "true"}, clear=False):
        files = list_workspace_files(db, user)
        playbooks = list_workspace_playbooks(db, user)
    assert files["count"] == 0
    assert playbooks["count"] == 0
    assert files["connected"] is True


def test_persist_and_list_playbook(db, user):
    with patch.dict(os.environ, {"AFRODITA_WORKSPACE_ENABLED": "true"}, clear=False):
        row = persist_workspace_playbook(
            db,
            user,
            title="Test Playbook",
            content={"summary": "ok", "support_schedule": {}},
        )
        db.commit()
        out = list_workspace_playbooks(db, user)
    assert row.id is not None
    assert out["count"] == 1
    assert out["playbooks"][0]["title"] == "Test Playbook"
    assert out["playbooks"][0]["content"]["summary"] == "ok"

    stored = db.query(WorkspacePlaybook).filter(WorkspacePlaybook.id == row.id).first()
    assert stored is not None
    assert json.loads(stored.content)["summary"] == "ok"


def test_workspace_disabled_returns_503(db, user):
    with patch("services.afrodita_workspace_db_service_v1.workspace_enabled", return_value=False):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            list_workspace_files(db, user)
        assert exc.value.status_code == 503
