"""Tests for zeus_integrations_e2e_v1."""

import asyncio
from unittest.mock import MagicMock, patch

from services.zeus_integrations_e2e_v1 import (
    _probe_openai_sync,
    _probe_sendgrid_sync,
    _probe_stripe_sync,
    _probe_twilio_sync,
    run_integrations_e2e,
)


def test_probe_stripe_not_configured():
    with patch("services.zeus_integrations_e2e_v1.stripe_service") as mock_svc:
        mock_svc.get_status.return_value = {"configured": False}
        result = _probe_stripe_sync()
    assert result["ok"] is False
    assert result["error"] == "not_configured"


def test_probe_stripe_ok():
    with patch("services.zeus_integrations_e2e_v1.stripe_service") as mock_svc:
        mock_svc.get_status.return_value = {
            "configured": True,
            "detected_mode": "test",
            "webhooks_enabled": True,
        }
        mock_account = MagicMock()
        mock_account.id = "acct_test"
        with patch("stripe.Account.retrieve", return_value=mock_account):
            result = _probe_stripe_sync()
    assert result["ok"] is True
    assert "acct_test" in result["detail"]


def test_probe_sendgrid_ok():
    with patch("services.zeus_integrations_e2e_v1.email_service") as mock_email:
        mock_email.api_key = "SG.test"
        mock_email.from_email = "noreply@test.com"
        mock_email.is_resend_configured.return_value = False
        mock_email.is_smtp_configured.return_value = False
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"scopes": ["mail.send"]}
        with patch("services.zeus_integrations_e2e_v1.requests.get", return_value=mock_resp):
            result = _probe_sendgrid_sync()
    assert result["ok"] is True


def test_probe_twilio_not_configured():
    with patch("services.zeus_integrations_e2e_v1.whatsapp_service") as mock_wa:
        mock_wa.get_status.return_value = {"configured": False, "enabled": True}
        result = _probe_twilio_sync()
    assert result["ok"] is False


def test_probe_openai_not_configured():
    with patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False):
        result = _probe_openai_sync()
    assert result["ok"] is False


def test_run_integrations_e2e_structure():
    db = MagicMock()
    with patch(
        "services.zeus_integrations_e2e_v1._probe_stripe_sync",
        return_value={"id": "stripe", "ok": True},
    ), patch(
        "services.zeus_integrations_e2e_v1._probe_twilio_sync",
        return_value={"id": "whatsapp", "ok": True},
    ), patch(
        "services.zeus_integrations_e2e_v1._probe_sendgrid_sync",
        return_value={"id": "email", "ok": False, "error": "not_configured"},
    ), patch(
        "services.zeus_integrations_e2e_v1._probe_openai_sync",
        return_value={"id": "openai", "ok": True},
    ), patch(
        "services.zeus_integrations_e2e_v1._probe_database_sync",
        return_value={"id": "database", "ok": True},
    ), patch(
        "services.zeus_integrations_e2e_v1._probe_internal_flags",
        return_value=[{"id": "event_bus", "ok": True}],
    ):
        result = asyncio.run(run_integrations_e2e(db))
    assert "summary" in result
    assert result["external_ready"] is False
    assert len(result["checks"]) >= 4
