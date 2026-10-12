"""Fase 2 / Step 2 — puntos 9 y 11.

- autonomo_paperwork_prepare/pricing_review ya no salen "executed_internal" sin hacer nada.
- stripe_readiness_check comprueba la configuracion real.
- el modo del guard legacy sale del handler real, no de una lista fija desfasada.
- el ejecutor de chat ya no responde success=True "Accion simulada".
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from services.automation.handlers import GENERIC_INTERNAL_ACTION_TYPES, HANDLER_MAP, resolve_handler
from services.automation.handlers.generic_internal import handle_generic_internal
from services.automation.handlers.no_real_logic import handle_no_real_logic
from services.automation.handlers.stripe_readiness import handle_stripe_readiness_check
from services.legacy_handler_guard_v1 import handler_execution_mode


def _act(agent, action):
    return SimpleNamespace(id=1, agent_name=agent, action_type=action, action_description="t",
                           details={}, user_email="x@example.com", company_id=None)


@pytest.mark.parametrize("action", ["autonomo_paperwork_prepare", "pricing_review"])
def test_no_logic_actions_are_explicit(action):
    for agent in ("ZEUS", "PERSEO"):
        h = resolve_handler(agent, action)
        assert h is handle_no_real_logic
        out = h(_act(agent, action))
        assert out["status"] == "blocked_missing_handler" and out["details_update"]["executed"] is False


def test_generic_handler_only_for_record_only_actions():
    assert GENERIC_INTERNAL_ACTION_TYPES == {"daily_internal_log", "system_friction_detected"}
    misuse = [f"{a}:{x}" for a, acts in HANDLER_MAP.items() for x, h in acts.items()
              if h is handle_generic_internal and x not in GENERIC_INTERNAL_ACTION_TYPES]
    assert misuse == []


def test_stripe_readiness_reads_real_config():
    from services.stripe_service import stripe_service

    assert resolve_handler("ZEUS", "stripe_readiness_check") is handle_stripe_readiness_check
    with patch.object(stripe_service, "get_status", return_value={"configured": False, "webhooks_enabled": False}):
        out = handle_stripe_readiness_check(_act("ZEUS", "stripe_readiness_check"))
    assert out["status"] == "failed" and out["details_update"]["missing"] == ["STRIPE_API_KEY", "STRIPE_WEBHOOK_SECRET"]
    with patch.object(stripe_service, "get_status",
                      return_value={"configured": True, "webhooks_enabled": True, "detected_mode": "test"}):
        out = handle_stripe_readiness_check(_act("ZEUS", "stripe_readiness_check"))
    assert out["status"] == "completed" and out["details_update"]["ready"] is True


def test_legacy_guard_mode_follows_real_handler():
    assert handler_execution_mode(_act("RAFAEL", "invoice_sent")) == "real"  # antes: "simulated"
    assert handler_execution_mode(_act("PERSEO", "task_assigned")) == "no_real_logic"
    assert handler_execution_mode(_act("ZEUS", "accion_inexistente")) == "no_handler"


def test_chat_executor_never_reports_simulated_success():
    import asyncio

    from services import zeus_agent_executor_v1 as ex

    user = SimpleNamespace(id=1, email="x@example.com", is_superuser=False)
    with patch.object(ex.crm_svc, "primary_company_id", return_value=1), \
         patch.object(ex, "_log_execution") as log:
        out = asyncio.run(ex.execute_agent_action(None, user=user, agent="RAFAEL", action="invoice_sent", payload={}))
    assert out["success"] is False and out["executed"] is False
    assert out["status"] == "workflow_only_action" and "simulada" not in out["message"].lower()
    log.assert_called_once()
