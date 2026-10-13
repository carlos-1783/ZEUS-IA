"""Fase 2 #5/#7 — herramientas PERSEO sin resultados inventados.

#5  Auditoría SEO: score SOLO con comprobaciones deterministas sobre el HTML real;
    sin página analizable → 422; el score del LLM se descarta.
#7  La descarga de imagen/página pasa por el fetch seguro (sin SSRF).
"""

from __future__ import annotations

import io
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

import services.perseo_ai_service_v2 as ai
import services.safe_http_fetch as sf
import services.workspaces.perseo_tools_heuristic as heur

GOOD_HTML = """<!doctype html><html lang="es"><head>
<title>Restaurante Olivo — cocina mediterránea en Madrid</title>
<meta name="description" content="Restaurante mediterráneo en Madrid con menú del día, terraza y reservas online. Cocina de temporada con producto local.">
<meta name="viewport" content="width=device-width">
<link rel="canonical" href="https://olivo.example/">
</head><body><h1>Cocina mediterránea</h1><img src="a.jpg" alt="Sala"><p>Menú del día y paella.</p>
<script>var paella_fake = 1;</script></body></html>"""

BAD_HTML = "<html><body><h1>a</h1><h1>b</h1><img src='x.png'></body></html>"


def _fetched(url, html, ct="text/html; charset=utf-8"):
    return sf.FetchResult(url=url, final_url=url, status=200, content_type=ct, body=html.encode("utf-8"))


# ------------------------------------------------------------------ #5 SEO


def test_seo_score_determinista_sobre_html_descargado():
    with patch.object(heur, "safe_fetch", return_value=_fetched("https://olivo.example/", GOOD_HTML)) as f, \
         patch.object(ai, "openai_configured", return_value=False):
        out = ai.seo_audit_ai({"url": "https://olivo.example/", "keywords": ["paella", "sushi"]})
    f.assert_called_once()
    assert f.call_args.kwargs["allow_http"] is True
    assert out["score"] == 100 and out["seo_score"] == 100
    assert out["score_method"] == "comprobaciones_deterministas"
    assert out["checks_passed"] == out["checks_total"] == 11
    assert out["source"] == "url_descargada"
    assert out["keyword_score"] == 50.0  # paella si (texto visible), sushi no
    assert out["issues"] == []


def test_seo_texto_dentro_de_script_no_cuenta_como_keyword():
    with patch.object(heur, "safe_fetch", return_value=_fetched("https://olivo.example/", GOOD_HTML)), \
         patch.object(ai, "openai_configured", return_value=False):
        out = ai.seo_audit_ai({"url": "https://olivo.example/", "keywords": ["paella_fake"]})
    assert out["keyword_score"] == 0.0


def test_seo_pagina_mala_baja_score_y_lista_incidencias():
    with patch.object(heur, "safe_fetch", return_value=_fetched("http://mala.example/", BAD_HTML)), \
         patch.object(ai, "openai_configured", return_value=False):
        out = ai.seo_audit_ai({"url": "http://mala.example/"})
    checks = {c["key"]: c["passed"] for c in out["checks"]}
    assert checks["title_present"] is False
    assert checks["single_h1"] is False
    assert checks["img_alt"] is False
    assert checks["https"] is False
    assert checks["indexable"] is True
    assert out["score"] == 9  # solo "indexable": 10 de 110 puntos aplicables
    assert out["keyword_score"] is None
    assert len(out["issues"]) == 10


def test_seo_sin_pagina_es_422_y_no_55_inventado():
    with pytest.raises(HTTPException) as exc:
        ai.seo_audit_ai({"url": None, "keywords": ["x"], "html_snapshot": None})
    assert exc.value.status_code == 422
    assert exc.value.detail["error"] == "seo_page_not_analyzable"


def test_seo_url_no_descargable_es_422_sin_caer_al_snapshot():
    with patch.object(heur, "safe_fetch", side_effect=sf.FetchFailedError("La URL respondió HTTP 500.")):
        with pytest.raises(HTTPException) as exc:
            ai.seo_audit_ai({"url": "https://caida.example/", "html_snapshot": GOOD_HTML})
    assert exc.value.status_code == 422
    assert "Sin página analizable" in exc.value.detail["message"]


def test_seo_ssrf_url_interna_es_422_sin_conexion(monkeypatch):
    opened = []
    monkeypatch.setattr(sf, "_opener", lambda *a, **k: opened.append(a))
    for url in ("http://127.0.0.1/admin", "http://169.254.169.254/latest/meta-data", "file:///etc/passwd"):
        with pytest.raises(HTTPException) as exc:
            ai.seo_audit_ai({"url": url})
        assert exc.value.status_code == 422
    assert opened == []


def test_seo_html_aportado_sin_url_no_puntua_https():
    with patch.object(ai, "openai_configured", return_value=False):
        out = ai.seo_audit_ai({"html_snapshot": GOOD_HTML})
    https = next(c for c in out["checks"] if c["key"] == "https")
    assert https["passed"] is None
    assert out["checks_total"] == 10
    assert out["source"] == "html_aportado_por_usuario"


def test_seo_con_ia_el_score_del_llm_se_descarta():
    llm = {"success": True, "ai_powered": True, "model": "gpt-x", "seo_score": 99,
           "recommendations": ["Añade la keyword al H1"], "suggested_title": "T"}
    with patch.object(heur, "safe_fetch", return_value=_fetched("http://mala.example/", BAD_HTML)), \
         patch.object(ai, "openai_configured", return_value=True), \
         patch.object(ai, "_text_completion", return_value=llm) as tc:
        out = ai.seo_audit_ai({"url": "http://mala.example/"})
    tc.assert_called_once()
    assert out["score"] == 9 and out["seo_score"] == 9
    rec = out["ai_recommendations"]
    assert rec["available"] is True
    assert "no influyen en el score" in rec["label"]
    assert rec["recommendations"] == ["Añade la keyword al H1"]


def test_seo_si_la_ia_falla_se_informa_y_se_mantiene_lo_medido():
    with patch.object(heur, "safe_fetch", return_value=_fetched("https://olivo.example/", GOOD_HTML)), \
         patch.object(ai, "openai_configured", return_value=True), \
         patch.object(ai, "_text_completion", side_effect=RuntimeError("quota")):
        out = ai.seo_audit_ai({"url": "https://olivo.example/"})
    assert out["score"] == 100
    assert out["ai_recommendations"] == {"available": False, "error": "quota"}
    assert out["ai_powered"] is False


def test_texto_workspace_seo_no_dice_completada_sin_datos():
    from app.api.v1.endpoints import workspaces as ws

    with patch.object(heur, "safe_fetch", return_value=_fetched("http://mala.example/", BAD_HTML)), \
         patch.object(ai, "openai_configured", return_value=False):
        out = ai.seo_audit_ai({"url": "http://mala.example/"})
    txt = ws._text_for_seo(out)
    assert "score 9/100" in txt and "1 de 11 comprobaciones" in txt
    assert "http://mala.example/" in txt


# ------------------------------------------------------------------ #7 imagen


def _png_bytes():
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (40, 80), (200, 10, 10)).save(buf, format="PNG")
    return buf.getvalue()


def test_imagen_se_descarga_con_fetch_seguro_y_mide_de_verdad():
    res = sf.FetchResult("https://cdn.example/a.png", "https://cdn.example/a.png", 200, "image/png", _png_bytes())
    with patch.object(heur, "safe_fetch", return_value=res) as f:
        out = heur.analyze_perseo_image_heuristic({"image_url": "https://cdn.example/a.png", "goals": ["conversion"]})
    assert f.call_args.kwargs["allowed_content_types"] == ["image/"]
    assert "allow_http" not in f.call_args.kwargs  # imagen: solo https
    assert out["dimensions"] == {"width": 40, "height": 80, "aspect_ratio": 0.5}
    assert out["average_color"] == "#c80a0a"


@pytest.mark.parametrize(
    "url",
    ["http://127.0.0.1:8000/api/v1/admin", "https://10.0.0.1/x.png", "https://[::1]/x.png", "http://cdn.example/a.png"],
)
def test_imagen_ssrf_bloqueada_422_sin_conexion(monkeypatch, url):
    opened = []
    monkeypatch.setattr(sf, "_opener", lambda *a, **k: opened.append(a))
    with pytest.raises(HTTPException) as exc:
        heur.analyze_perseo_image_heuristic({"image_url": url})
    assert exc.value.status_code == 422
    assert exc.value.detail["error"] == "image_not_fetchable"
    assert opened == []


def test_imagen_no_decodificable_o_sin_url_es_422():
    res = sf.FetchResult("https://cdn.example/a.png", "https://cdn.example/a.png", 200, "image/png", b"no-es-png")
    with patch.object(heur, "safe_fetch", return_value=res):
        with pytest.raises(HTTPException) as exc:
            heur.analyze_perseo_image_heuristic({"image_url": "https://cdn.example/a.png"})
    assert exc.value.detail["error"] == "image_not_decodable"
    with pytest.raises(HTTPException) as exc2:
        heur.analyze_perseo_image_heuristic({"image_url": None})
    assert exc2.value.status_code == 422


def test_tool_seo_audit_endpoint_persiste_solo_si_hay_pagina():
    import asyncio

    from app.api.v1.endpoints import workspaces as ws

    req = SimpleNamespace(model_dump=lambda: {"url": None, "keywords": [], "html_snapshot": None})
    with patch.object(ws, "_persist_tool_output") as persist, patch.object(ws, "_log_event_chain") as chain:
        with pytest.raises(HTTPException) as exc:
            asyncio.run(ws.tool_seo_audit(req, current_user=SimpleNamespace(id=1, email="a@b.c"), db=None))
    assert exc.value.status_code == 422
    persist.assert_not_called()
    chain.assert_not_called()
