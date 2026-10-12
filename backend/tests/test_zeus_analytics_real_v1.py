"""Tests for zeus_analytics_real_v1."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from services.zeus_analytics_real_v1 import (
    OLYMPUS_AGENTS,
    build_executive_analytics,
    record_zeus_event,
)


def test_build_executive_analytics_structure():
    db = MagicMock()
    user = MagicMock()
    user.id = 1
    user.is_superuser = True

    with patch("services.zeus_analytics_real_v1._count_events_24h", return_value=(10, 8)),             patch("services.zeus_analytics_real_v1._count_active_agents_24h", return_value=3):
        with patch("services.zeus_analytics_real_v1._count_alerts", return_value=2):
            with patch("services.zeus_analytics_real_v1._count_automations", return_value=6):
                with patch("services.zeus_analytics_real_v1._system_status", return_value="healthy"):
                    out = build_executive_analytics(db, user)

    assert out["agents"] == 3
    assert out["agents_total"] == OLYMPUS_AGENTS
    assert out["tasks24h"] == 10
    assert out["alerts"] == 2
    assert out["automations"] == 6
    assert out["efficiency"] == 80
    assert out["system"] == "healthy"
    assert out["real_data"] is True


def test_record_zeus_event_adds_row():
    db = MagicMock()
    record_zeus_event(
        db,
        event_type="contract_created",
        agent="AFRODITA",
        status="success",
        user_id=1,
    )
    db.add.assert_called()
    db.flush.assert_called()


def test_efficiency_zero_tasks():
    db = MagicMock()
    user = MagicMock()
    user.is_superuser = True

    with patch("services.zeus_analytics_real_v1._count_events_24h", return_value=(0, 0)),             patch("services.zeus_analytics_real_v1._count_active_agents_24h", return_value=0):
        with patch("services.zeus_analytics_real_v1._count_alerts", return_value=0):
            with patch("services.zeus_analytics_real_v1._count_automations", return_value=6):
                with patch("services.zeus_analytics_real_v1._system_status", return_value="healthy"):
                    out = build_executive_analytics(db, user)

    # Sin tareas no hay eficiencia que medir: "sin datos", no 0 %.
    assert out["efficiency"] is None
