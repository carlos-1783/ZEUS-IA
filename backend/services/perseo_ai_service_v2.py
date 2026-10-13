"""PERSEO AI service v2 — GPT-4o powered analysis, recommendations, SEO and ads."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from config.settings import settings
from services.openai_service import chat_completion, get_openai_client, parse_json_response

logger = logging.getLogger(__name__)

PERSEO_AI_MODEL = os.getenv("PERSEO_AI_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o"))


def openai_configured() -> bool:
    return bool(settings.OPENAI_API_KEY)


def _model() -> str:
    return PERSEO_AI_MODEL or "gpt-4o"


def _require_ai() -> None:
    if not openai_configured():
        raise RuntimeError("OPENAI_API_KEY not configured for PERSEO AI")


def _vision_completion(system: str, user_text: str, image_url: str) -> Dict[str, Any]:
    _require_ai()
    client = get_openai_client()
    response = client.chat.completions.create(
        model=_model(),
        messages=[
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            },
        ],
        temperature=0.4,
        max_tokens=1800,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content or "{}"
    parsed = parse_json_response(content) or json.loads(content)
    return {"success": True, "ai_powered": True, "model": _model(), **parsed}


def _text_completion(system: str, user_text: str) -> Dict[str, Any]:
    result = chat_completion(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ],
        model=_model(),
        temperature=0.5,
        max_tokens=2200,
        response_format={"type": "json_object"},
    )
    if not result.get("success"):
        raise RuntimeError(result.get("error") or "OpenAI request failed")
    parsed = parse_json_response(result["content"]) or {}
    return {"success": True, "ai_powered": True, "model": _model(), **parsed}


def analyze_image_ai(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Real AI image analysis — tags, hooks, marketing angles, visual insights."""
    image_url = (payload.get("image_url") or "").strip()
    goals: List[str] = payload.get("goals") or []
    tags: List[str] = payload.get("tags") or []

    if not openai_configured():
        from services.workspaces.perseo_tools_heuristic import analyze_perseo_image_heuristic

        out = analyze_perseo_image_heuristic(payload)
        return {**out, "ai_powered": False, "mode": "heuristic_fallback"}

    if not image_url:
        raise ValueError("image_url required for AI analysis")

    system = (
        "Eres PERSEO, director creativo de marketing. Analiza la imagen y responde SOLO JSON con: "
        "tags (array), marketing_angles (array), hooks (array), visual_insights (array), "
        "palette_suggestions (array), recommended_platforms (array), summary (string)."
    )
    user_text = f"Objetivos: {', '.join(goals) or 'conversión'}. Tags contexto: {', '.join(tags) or 'ninguno'}."
    return _vision_completion(system, user_text, image_url)


def recommend_video_ai(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Real AI video recommendations — script, structure, scenes, CTA."""
    if not openai_configured():
        from services.workspaces.perseo_tools_heuristic import enhance_perseo_video_heuristic

        out = enhance_perseo_video_heuristic(payload)
        return {**out, "ai_powered": False, "mode": "heuristic_fallback"}

    duration = payload.get("duration_seconds", 45)
    tone = payload.get("tone", "energético")
    platform = payload.get("platform", "meta")
    system = (
        "Eres PERSEO, estratega de vídeo corto. Responde SOLO JSON con: "
        "script (string), structure (array de fases), scene_breakdown (array de objetos con timestamp y action), "
        "cta (string), audio_suggestions (array), recommended_duration (number)."
    )
    user_text = f"Duración objetivo: {duration}s. Tono: {tone}. Plataforma: {platform}."
    return _text_completion(system, user_text)


def seo_audit_ai(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Auditoría SEO sobre la página REAL.

    El score y las incidencias salen SIEMPRE de las comprobaciones deterministas
    (``run_seo_audit_heuristic`` descarga el HTML con el fetch seguro; sin página → 422).
    Si OpenAI está configurado, el LLM solo añade recomendaciones de texto, etiquetadas
    como tales; cualquier puntuación que devuelva se descarta.
    """
    from services.workspaces.perseo_tools_heuristic import run_seo_audit_heuristic

    out = run_seo_audit_heuristic(payload)
    if not openai_configured():
        return {**out, "mode": "deterministic"}

    keywords: List[str] = payload.get("keywords") or []
    system = (
        "Eres PERSEO, consultor SEO. Te paso el resultado de comprobaciones técnicas YA "
        "medidas sobre una página real. NO puntúes la página. Responde SOLO JSON con: "
        "recommendations (array de strings accionables), suggested_title (string), "
        "suggested_meta_description (string)."
    )
    facts = {
        "url": out.get("url"),
        "checks": out.get("checks"),
        "keywords": out.get("keywords"),
    }
    user_text = (
        f"Keywords objetivo: {', '.join(keywords) or 'ninguna'}.\n"
        f"Resultados medidos: {json.dumps(facts, ensure_ascii=False)[:8000]}"
    )
    try:
        ai = _text_completion(system, user_text)
    except Exception as exc:
        logger.warning("PERSEO seo_audit: recomendaciones IA no disponibles: %s", exc)
        return {
            **out,
            "mode": "deterministic",
            "ai_recommendations": {"available": False, "error": str(exc)[:300]},
        }
    return {
        **out,
        "mode": "deterministic+ai_text",
        "ai_powered": True,
        "ai_recommendations": {
            "available": True,
            "label": "Recomendaciones de texto generadas por IA (no influyen en el score)",
            "model": ai.get("model"),
            "recommendations": ai.get("recommendations") or [],
            "suggested_title": ai.get("suggested_title"),
            "suggested_meta_description": ai.get("suggested_meta_description"),
        },
    }


def generate_ads_ai(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Real AI ads blueprint — copy, creatives, targeting, budget strategy."""
    if not openai_configured():
        from services.workspaces.perseo_tools_heuristic import build_ads_blueprint_heuristic

        out = build_ads_blueprint_heuristic(payload)
        return {**out, "ai_powered": False, "mode": "heuristic_fallback"}

    product = payload.get("product") or payload.get("audience") or "producto"
    budget = payload.get("budget", 1000)
    audience = payload.get("audience", "general")
    objective = payload.get("objective", "leads")
    system = (
        "Eres PERSEO, media buyer senior. Responde SOLO JSON con: "
        "ad_copy (array de variantes), creatives (array de ideas visuales), "
        "targeting (objeto demographics/interests/placements), "
        "budget_strategy (objeto con channel_mix array), kpis (objeto), next_steps (array)."
    )
    user_text = f"Producto: {product}. Presupuesto: {budget}€. Audiencia: {audience}. Objetivo: {objective}."
    return _text_completion(system, user_text)
