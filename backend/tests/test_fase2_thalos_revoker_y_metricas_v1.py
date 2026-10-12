"""Fase 2 / Step 2 — THALOS ya no "revoca" credenciales sin hacerlo; efficiency real."""

from types import SimpleNamespace

from services.activity_logger import calculate_zeus_metrics
from services.workspaces.thalos_tools import revoke_credentials


def test_revoker_does_not_claim_revocation():
    r = revoke_credentials({"credential_ids": ["stripe_key", "openai_key"]})
    assert r["real_execution"] is False and r["revoked"] == [] and r["count"] == 0
    assert r["error"] == "credential_revoker_not_implemented"


def test_revoker_endpoint_is_501_and_persists_nothing():
    from unittest.mock import patch

    import pytest
    from fastapi import HTTPException

    from app.api.v1.endpoints import workspaces as ws

    req = SimpleNamespace(model_dump=lambda: {"credential_ids": ["k1"]})
    with patch.object(ws, "_persist_agent_tool_response") as persist:
        import asyncio

        with pytest.raises(HTTPException) as exc:
            asyncio.run(ws.workspace_thalos_credentials(req, current_user=SimpleNamespace(id=1), db=None))
    assert exc.value.status_code == 501
    persist.assert_not_called()


def test_zeus_efficiency_is_computed():
    acts = [SimpleNamespace(action_type="coordination", status=s) for s in ("completed", "failed", "completed", "pending")]
    assert calculate_zeus_metrics(acts)["efficiency"] == 50
    assert calculate_zeus_metrics([])["efficiency"] is None
