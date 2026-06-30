"""Tests teamflow_real_handlers_v1 and handler coverage."""

from __future__ import annotations

from unittest.mock import MagicMock

from services.automation.handlers import resolve_handler, scan_handler_coverage
from services.automation.handlers.generic_internal import handle_generic_internal
from services.teamflow_real_handlers_v1 import (
    TEAMFLOW_REAL_ACTION_TYPES,
    handle_unmapped_no_fake,
)


def test_critical_actions_have_real_handlers():
    coverage = scan_handler_coverage()
    assert coverage["generic_handlers_count"] == 0
    assert coverage["critical_actions_all_real"] is True
    assert coverage["teamflow_real_percentage"] == 100.0


def test_resolve_perseo_ads_campaign_builder():
    handler = resolve_handler("PERSEO", "ads_campaign_builder")
    assert handler is not handle_generic_internal
    assert handler.__name__ == "handle_ads_campaign_builder"


def test_resolve_justicia_document_signed():
    handler = resolve_handler("JUSTICIA", "document_signed")
    assert handler.__name__ == "handle_document_signed"


def test_unknown_action_fail_closed():
    handler = resolve_handler("UNKNOWN", "totally_unknown_xyz")
    assert handler is handle_unmapped_no_fake


def test_unmapped_critical_returns_fail_handler():
    activity = MagicMock()
    activity.agent_name = "UNKNOWN"
    activity.action_type = "invoice_sent"
    result = handle_unmapped_no_fake(activity)
    assert result["status"] == "failed"
    assert result["details_update"]["real_execution"] is False


def test_all_critical_action_types_covered():
    for action in TEAMFLOW_REAL_ACTION_TYPES:
        found = False
        for agent in ("PERSEO", "RAFAEL", "JUSTICIA", "AFRODITA"):
            h = resolve_handler(agent, action)
            if h is not handle_generic_internal and h is not handle_unmapped_no_fake:
                found = True
                break
        assert found, f"no real handler for {action}"
