"""Tests for zeus_crm_hooks_v1 (CRM → agent connection)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from services.zeus_crm_hooks_v1 import (
    PAYMENT_RISK_DAYS,
    _customer_payload,
    _parse_iso_date,
    check_payment_expiry_risk,
)


def test_parse_iso_date_z_suffix():
    dt = _parse_iso_date("2026-06-25T12:00:00Z")
    assert dt is not None
    assert dt.tzinfo is not None


def test_customer_payload_includes_metadata():
    customer = MagicMock()
    customer.id = 42
    customer.name = "Acme"
    customer.email = "a@acme.com"
    customer.phone = None
    customer.company_id = 1
    customer.metadata_ = {"next_payment_date": "2026-06-25"}
    payload = _customer_payload(customer)
    assert payload["customer_id"] == 42
    assert payload["next_payment_date"] == "2026-06-25"


def test_check_payment_expiry_risk_within_window():
    customer = MagicMock()
    customer.id = 1
    customer.name = "Risk Co"
    customer.email = "r@risk.com"
    customer.phone = None
    customer.company_id = 1
    due = datetime.now(timezone.utc) + timedelta(days=3)
    customer.metadata_ = {"next_payment_date": due.isoformat()}
    db = MagicMock()
    risk = check_payment_expiry_risk(db, customer)
    assert risk is not None
    assert risk["risk_level"] in ("high", "medium")
    assert risk["days_until_due"] <= PAYMENT_RISK_DAYS


def test_check_payment_expiry_risk_outside_window():
    customer = MagicMock()
    customer.id = 1
    customer.name = "Safe Co"
    customer.email = "s@safe.com"
    customer.phone = None
    customer.company_id = 1
    due = datetime.now(timezone.utc) + timedelta(days=30)
    customer.metadata_ = {"next_payment_date": due.isoformat()}
    db = MagicMock()
    assert check_payment_expiry_risk(db, customer) is None


@patch("services.zeus_event_bus_v1.emit_event")
def test_on_client_updated_emits_payment_risk(mock_emit):
    from services.zeus_crm_hooks_v1 import on_client_updated

    customer = MagicMock()
    customer.id = 7
    customer.name = "Due Soon"
    customer.email = "d@due.com"
    customer.phone = None
    customer.company_id = 1
    due = datetime.now(timezone.utc) + timedelta(days=2)
    customer.metadata_ = {"next_payment_date": due.isoformat()}
    user = MagicMock()
    user.id = 1
    db = MagicMock()
    mock_emit.side_effect = [{"event_id": "a"}, {"event_id": "b"}]

    out = on_client_updated(db, user, customer)

    assert mock_emit.call_count == 2
    assert mock_emit.call_args_list[0].kwargs["event_name"] == "client_updated"
    assert mock_emit.call_args_list[1].kwargs["event_name"] == "payment_risk"
    assert "payment_risk" in out
