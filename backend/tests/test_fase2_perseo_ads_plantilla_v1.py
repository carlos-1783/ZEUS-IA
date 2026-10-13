"""Fase 2 #19 — el plan de Ads de PERSEO es una plantilla orientativa etiquetada,
sin KPIs numéricos inventados (CPL 15, ROAS 3.5, CTR 1.8) ni "listo para ejecutar"."""

from __future__ import annotations

from unittest.mock import patch

import services.perseo_ai_service_v2 as ai
import services.workspaces.perseo_tools_heuristic as heur


def test_plan_ads_heuristico_es_plantilla_sin_kpis_inventados():
    out = heur.build_ads_blueprint_heuristic({"budget": 1000, "audience": "jóvenes", "objective": "leads"})
    assert out["label"] == "Plantilla orientativa (sin datos de tu cuenta)"
    assert out["is_template"] is True and out["based_on_account_data"] is False
    assert out["kpi_targets"] is None
    assert "kpis" not in out
    assert sum(c["allocation"] for c in out["channels"]) == 1000


def test_plan_ads_ia_descarta_kpis_numericos():
    llm = {"success": True, "ai_powered": True, "model": "gpt-x", "kpis": {"cpl": 12, "roas": 4},
           "budget_strategy": {"channel_mix": [{"channel": "Meta"}]}, "kpis_to_track": ["CPL"]}
    with patch.object(ai, "openai_configured", return_value=True), \
         patch.object(ai, "_text_completion", return_value=llm):
        out = ai.generate_ads_ai({"product": "café", "budget": 300})
    assert "kpis" not in out
    assert out["kpi_targets"] is None
    assert "sin datos de tu cuenta" in out["label"]


def test_texto_workspace_ads_no_dice_listo_para_ejecutar():
    from app.api.v1.endpoints import workspaces as ws

    txt = ws._text_for_ads(heur.build_ads_blueprint_heuristic({"budget": 500}))
    assert txt.startswith("Plantilla orientativa (sin datos de tu cuenta)")
    assert "listo para ejecutar" not in txt
    assert "15" not in txt and "3.5" not in txt and "1.8" not in txt
