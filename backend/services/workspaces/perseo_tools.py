"""
Herramientas de workspace para PERSEO — AI real cuando OpenAI está configurado.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .base import log_tool_execution


def _ai_or_heuristic(ai_fn, heuristic_fn, payload, tool_name, description_fn):
    try:
        from services.perseo_ai_service_v2 import openai_configured

        if openai_configured():
            return ai_fn(payload)
    except Exception as exc:
        print(f"[PERSEO][{tool_name}] AI fallback: {exc}")
    return heuristic_fn(payload)


def analyze_perseo_image(payload: Dict[str, Any], user_email: Optional[str] = None) -> Dict[str, Any]:
    from services.perseo_ai_service_v2 import analyze_image_ai
    from services.workspaces.perseo_tools_heuristic import analyze_perseo_image_heuristic

    result = _ai_or_heuristic(
        analyze_image_ai,
        analyze_perseo_image_heuristic,
        payload,
        "image_analyzer",
        None,
    )
    log_tool_execution(
        agent="PERSEO",
        tool_name="image_analyzer",
        description=f"Imagen analizada ({'AI' if result.get('ai_powered') else 'heurístico'})",
        details={"payload": payload, "result": result},
        user_email=user_email,
    )
    return result


def enhance_perseo_video(payload: Dict[str, Any], user_email: Optional[str] = None) -> Dict[str, Any]:
    from services.perseo_ai_service_v2 import recommend_video_ai
    from services.workspaces.perseo_tools_heuristic import enhance_perseo_video_heuristic

    result = _ai_or_heuristic(
        recommend_video_ai,
        enhance_perseo_video_heuristic,
        payload,
        "video_enhancer",
        None,
    )
    log_tool_execution(
        agent="PERSEO",
        tool_name="video_enhancer",
        description=f"Recomendación vídeo ({'AI' if result.get('ai_powered') else 'heurístico'})",
        details={"payload": payload, "result": result},
        user_email=user_email,
    )
    return result


def run_seo_audit(payload: Dict[str, Any], user_email: Optional[str] = None) -> Dict[str, Any]:
    from services.perseo_ai_service_v2 import seo_audit_ai

    # seo_audit_ai ya hace la auditoría determinista sobre la página real (422 si no hay
    # página analizable) y solo añade texto IA si está configurada: no hay "fallback".
    result = seo_audit_ai(payload)
    logged_payload = {k: v for k, v in payload.items() if k != "html_snapshot"}
    if payload.get("html_snapshot"):
        logged_payload["html_snapshot_chars"] = len(str(payload["html_snapshot"]))
    log_tool_execution(
        agent="PERSEO",
        tool_name="seo_audit_engine",
        description=(
            f"Auditoría SEO determinista ({result.get('checks_passed')}/{result.get('checks_total')} "
            f"comprobaciones){' + recomendaciones IA' if result.get('ai_powered') else ''}"
        ),
        details={"payload": logged_payload, "result": result},
        metrics={"score": result.get("score")},
        user_email=user_email,
    )
    return result


def build_ads_blueprint(payload: Dict[str, Any], user_email: Optional[str] = None) -> Dict[str, Any]:
    from services.perseo_ai_service_v2 import generate_ads_ai
    from services.workspaces.perseo_tools_heuristic import build_ads_blueprint_heuristic

    result = _ai_or_heuristic(
        generate_ads_ai,
        build_ads_blueprint_heuristic,
        payload,
        "ads_campaign_builder",
        None,
    )
    log_tool_execution(
        agent="PERSEO",
        tool_name="ads_campaign_builder",
        description=f"Blueprint ads ({'AI' if result.get('ai_powered') else 'heurístico'})",
        details={"payload": payload, "result": result},
        user_email=user_email,
    )
    return result
