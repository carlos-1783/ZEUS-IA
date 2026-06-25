"""Tests afrodita truth status endpoint."""

from __future__ import annotations

import pytest
from app.db.base import Base, SessionLocal, engine
from services.afrodita_unified_control import get_global_status


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_truth_status_payload_shape(db):
    payload = get_global_status(db)
    assert payload["execution_mode"] in ("REAL", "SIMULATED", "ERROR")
    assert isinstance(payload["db_connected"], bool)
    assert isinstance(payload["writes_enabled"], bool)
    assert isinstance(payload["flags_loaded"], bool)
    assert "execution_enabled" in payload
    assert "read_only_mode" in payload
    assert "AFRODITA_EXECUTION_ENABLED" in payload
    assert "AFRODITA_READ_ONLY_MODE" in payload
    assert payload["writes_enabled"] == (payload["execution_enabled"] and not payload["read_only_mode"])
    if payload["writes_enabled"] and payload["db_connected"]:
        assert payload["execution_mode"] == "REAL"
