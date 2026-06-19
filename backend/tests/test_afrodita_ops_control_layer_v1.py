"""Tests afrodita_ops_control_layer_v1."""

from __future__ import annotations

from unittest.mock import patch

from app.core.config import settings
from services.afrodita_ops_control_layer_v1 import (
    MODULE_UI_BADGE,
    can_write_stock,
    global_status_payload,
    wrap_response,
)


def test_default_ops_read_only():
    payload = global_status_payload()
    assert payload["system_default_mode"] == "READ_ONLY"
    assert payload["AFRODITA_OPS_READ_ONLY"] is True
    assert payload["erp_api_path"] == "/api/v1/products"


def test_can_write_stock_requires_flags():
    with patch.object(settings, "AFRODITA_OPS_ENABLED", False):
        assert can_write_stock() is False
    with patch.object(settings, "AFRODITA_OPS_ENABLED", True):
        with patch.object(settings, "AFRODITA_OPS_READ_ONLY", True):
            assert can_write_stock() is False
        with patch.object(settings, "AFRODITA_OPS_READ_ONLY", False):
            with patch.object(settings, "AFRODITA_ENABLE_STOCK_SYNC", True):
                assert can_write_stock() is True


def test_wrap_response_inventory():
    out = wrap_response({"ok": True}, "inventory_core", data_origin="backend", real_execution=True)
    assert out["afrodita_ops_control"]["ui_badge"] == MODULE_UI_BADGE["inventory_core"]
    assert out["real_execution"] is True


def test_warehouse_stub_badge():
    out = wrap_response({"stub": True}, "warehouse_management", data_origin="mock", real_execution=False)
    assert out["afrodita_ops_control"]["ui_badge"] == "NONE"
