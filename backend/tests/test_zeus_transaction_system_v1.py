"""Tests zeus_transaction_system_v1 orchestrator."""

from __future__ import annotations

import os
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.db.base import Base, SessionLocal, engine
from app.models.user import User
from app.models.zeus_transaction import ZeusTransaction
from services.zeus_transaction_system_v1 import create_transaction, execute_transaction, get_health


@pytest.fixture()
def db():
    ZeusTransaction.__table__.drop(bind=engine, checkfirst=True)
    Base.metadata.create_all(bind=engine, tables=[ZeusTransaction.__table__, User.__table__])
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def user(db):
    u = User(
        email=f"zeus-tx-{uuid.uuid4().hex}@test.local",
        hashed_password="x",
        is_active=True,
        is_superuser=False,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_create_transaction_pending(db, user):
    with patch.dict(os.environ, {"AFRODITA_EXECUTION_ENABLED": "true", "AFRODITA_READ_ONLY_MODE": "false"}, clear=False):
        tx = create_transaction(
            db,
            user,
            initiator={"type": "USER", "id": str(user.id), "source": "API"},
            context={"correlation_id": "c1"},
            steps=[
                {"module": "RRHH", "action": "create_employee", "input": {"full_name": "A", "employee_code": "E1"}},
            ],
        )
    assert tx["status"] == "PENDING"
    assert tx["transaction_id"]
    assert len(tx["steps"]) == 1


def test_idempotency_key(db, user):
    key = f"idemp-{uuid.uuid4().hex}"
    kwargs = dict(
        initiator={"type": "USER", "id": str(user.id), "source": "API"},
        context={},
        steps=[{"module": "WORKSPACE", "action": "persist_summary", "input": {"note": "x"}}],
        idempotency_key=key,
    )
    first = create_transaction(db, user, **kwargs)
    second = create_transaction(db, user, **kwargs)
    assert first["transaction_id"] == second["transaction_id"]


def test_execute_fails_validation_without_writes(db, user):
    with patch.dict(os.environ, {"AFRODITA_EXECUTION_ENABLED": "false"}, clear=False):
        tx = create_transaction(
            db,
            user,
            initiator={"type": "USER", "id": str(user.id), "source": "API"},
            context={},
            steps=[{"module": "OPS", "action": "create_movement", "input": {"product_id": 1, "quantity": 1}}],
        )
        out = execute_transaction(db, user, tx["transaction_id"])
    assert out["status"] == "FAILED"
    assert out["validation"]["passed"] is False


def test_health_endpoint_shape(db):
    health = get_health(db)
    assert health["system_status"] in ("OK", "DEGRADED", "ERROR")
    assert "active_transactions" in health
    assert "failed_transactions" in health
    assert "inconsistencies" in health
