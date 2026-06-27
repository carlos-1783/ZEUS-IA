"""Tests JUSTICIA force real mode."""

from __future__ import annotations

from services.justicia_control_layer_v1 import MODULE_UI_BADGE


def test_all_modules_real_badge():
    for mod, badge in MODULE_UI_BADGE.items():
        assert badge == "REAL", f"{mod} should be REAL, got {badge}"


def test_contract_template_exists():
    from services.contract_generator import CONTRACT_TEMPLATES

    assert "servicios" in CONTRACT_TEMPLATES
