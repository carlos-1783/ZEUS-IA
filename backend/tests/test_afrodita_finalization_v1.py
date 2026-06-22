"""Tests afrodita_finalization_v1 — domain separation."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from services.afrodita_control_layer_v1 import MODULE_UI_BADGE
from services.afrodita_finalization_v1 import (
    assert_workspace_isolated,
    finalization_payload,
)
from services.afrodita_workspace_service_v1 import execute_face_checkin


def test_finalization_payload_structure():
    payload = finalization_payload()
    assert payload["system_id"] == "afrodita_finalization_v1"
    assert payload["mode"] == "safe_execution"
    assert "workspace_no_executes_business" in payload["domain_separation"]["rules"]
    assert len(payload["ui_tabs"]) == 3
    assert payload["final_state"]["workspace"] == "ISOLATED"


def test_facial_checkin_disabled():
    assert MODULE_UI_BADGE["facial_checkin"] == "NONE"
    out = execute_face_checkin(None, None, {"employee_id": "X"})
    assert out["disabled"] is True
    assert out["executed"] is False


def test_workspace_isolated_raises():
    with pytest.raises(HTTPException) as exc:
        assert_workspace_isolated("qr_checkin")
    assert exc.value.status_code == 403
    detail = exc.value.detail
    assert detail["error"] == "workspace_isolated"
    assert "/api/v1/afrodita/rrhh/v1" in detail["redirect_rrhh"]
