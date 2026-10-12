"""Fase 2 / Step 3 — RAFAEL desde el chat usa el trimestre en curso, no 2026-T1 fijo."""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from services import zeus_agent_executor_v1 as ex


def _run(payload):
    user = SimpleNamespace(id=1, email="x@example.com", is_superuser=False)
    with patch.object(ex.crm_svc, "primary_company_id", return_value=7), \
         patch.object(ex, "_blocked_module_result", return_value=None), \
         patch.object(ex, "_log_execution"), \
         patch("services.zeus_core_guard_v1.validate_critical_action",
               return_value=SimpleNamespace(allowed=True, human_message="", to_dict=lambda: {})), \
         patch("services.rafael_fiscal_engine_v2.fetch_period_financials", return_value={"ok": 1}) as f:
        out = asyncio.run(ex.execute_agent_action(None, user=user, agent="RAFAEL", action="get_tax_summary",
                                                  payload=payload))
    return out, f


def test_default_period_is_current_quarter():
    now = datetime.now(timezone.utc)
    out, f = _run({})
    assert out["success"] is True
    assert f.call_args.kwargs == {"company_id": 7, "year": now.year, "quarter": (now.month - 1) // 3 + 1}


def test_invalid_quarter_is_controlled_failure():
    out, f = _run({"quarter": 7})
    assert out["success"] is False and out["status"] == "invalid_payload"
    f.assert_not_called()
