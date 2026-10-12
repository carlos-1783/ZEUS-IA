"""HOTFIX — /agents/status daba 500 en produccion: PostgreSQL devuelve created_at con zona
(timestamptz) y se comparaba con un datetime naive (TypeError)."""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.api.v1.endpoints import agents


def _status(rows):
    db = MagicMock()
    db.query.return_value.filter.return_value.filter.return_value.all.return_value = rows
    user = SimpleNamespace(is_superuser=False, email="x@example.com")
    with patch.object(agents, "business_activities", side_effect=lambda r: r):
        return asyncio.run(agents.get_agents_status(current_user=user, db=db))


def test_aware_timestamps_like_postgres_do_not_crash():
    now = datetime.now(timezone.utc)
    rows = [
        SimpleNamespace(agent_name="PERSEO", status="completed", created_at=now - timedelta(minutes=1)),
        SimpleNamespace(agent_name="PERSEO", status="failed", created_at=now - timedelta(days=2)),
    ]
    out = _status(rows)
    perseo = next(v for k, v in out["agents"].items() if k.upper() == "PERSEO") if isinstance(out.get("agents"), dict) else None
    assert out  # antes: TypeError
    if perseo is not None:
        assert perseo["status"] == "online"


def test_naive_timestamps_like_sqlite_still_work():
    now = datetime.utcnow()
    out = _status([SimpleNamespace(agent_name="RAFAEL", status="completed", created_at=now - timedelta(minutes=1))])
    assert out
