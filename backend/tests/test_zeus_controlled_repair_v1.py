"""Tests zeus_controlled_repair_v1."""

from __future__ import annotations

import os
from unittest.mock import patch

from services.automation.handlers import scan_handler_coverage
from services.zeus_controlled_repair_v1 import REPAIR_ID, _teamflow_handler_replacement, _validate_env


def test_repair_id():
    assert REPAIR_ID == "zeus_controlled_repair_v1"


def test_controlled_repair_handlers_phase_passes():
    with patch.dict(
        os.environ,
        {
            "AFRODITA_EXECUTION_ENABLED": "true",
            "AFRODITA_READ_ONLY_MODE": "false",
            "ZEUS_AGENT_ENABLED": "true",
            "TEAMFLOW_ENABLED": "true",
            "AFRODITA_OPS_ENABLED": "true",
            "AFRODITA_OPS_READ_ONLY": "false",
        },
        clear=False,
    ):
        env_phase = _validate_env()
        handler_phase = _teamflow_handler_replacement()
        coverage = scan_handler_coverage()

    assert env_phase["passed"] is True
    assert handler_phase["passed"] is True
    assert coverage["generic_handlers_count"] == 0
    assert coverage["teamflow_real_percentage"] == 100.0
