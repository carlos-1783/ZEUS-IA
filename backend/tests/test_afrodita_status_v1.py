"""Tests afrodita truth status endpoint."""

from __future__ import annotations

import pytest
from app.db.base import Base, SessionLocal, engine
from services.afrodita_control_layer_v1 import afrodita_truth_status_payload


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_truth_status_payload_shape(db):
    payload = afrodita_truth_status_payload(db)
    assert payload["execution_mode"] in ("REAL", "SIMULATED")
    assert isinstance(payload["db_connected"], bool)
    assert isinstance(payload["writes_enabled"], bool)
    assert isinstance(payload["flags_loaded"], bool)
    assert "execution_enabled" in payload
    assert "read_only_mode" in payload
    assert "AFRODITA_EXECUTION_ENABLED" in payload
    assert "AFRODITA_READ_ONLY_MODE" in payload
    assert "module_badges" in payload
    if not payload["flags_loaded"]:
        assert payload["writes_enabled"] is False
