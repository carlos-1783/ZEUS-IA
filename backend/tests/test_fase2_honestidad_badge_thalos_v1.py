"""Fase 2 / honestidad final #11 — el ui_badge de THALOS se calcula, no es "REAL" fijo."""

from __future__ import annotations

from services.thalos_control_layer_v1 import build_metadata, compute_ui_badge, wrap_response


def test_badge_calculado():
    assert compute_ui_badge(data_origin="backend", real_execution=True) == "REAL"
    assert compute_ui_badge(data_origin="mixed", real_execution=True) == "REAL"
    assert compute_ui_badge(data_origin="mock", real_execution=False) == "SIMULADO"
    assert compute_ui_badge(data_origin="mock", real_execution=True) == "SIMULADO"
    assert compute_ui_badge(data_origin="user_input", real_execution=False) == "PARCIAL"


def test_wrap_no_dice_real_con_mock_o_sin_ejecucion():
    out = wrap_response({}, "text_analysis", data_origin="mock", real_execution=False)
    assert out["thalos_control"]["ui_badge"] == "SIMULADO"
    out = wrap_response({}, "log_monitor", data_origin="user_input", real_execution=False)
    assert out["thalos_control"]["ui_badge"] == "PARCIAL"
    out = wrap_response({}, "log_monitor", data_origin="mixed", real_execution=True)
    assert out["thalos_control"]["ui_badge"] == "REAL"
    assert build_metadata("auditoria_real", data_origin="backend", real_execution=True).ui_badge == "REAL"
