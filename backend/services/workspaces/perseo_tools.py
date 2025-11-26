"""
Herramientas de workspace para PERSEO.
"""

from __future__ import annotations

from io import BytesIO
from statistics import mean
from typing import Any, Dict, List, Optional

import requests
from PIL import Image

from .base import log_tool_execution


def _hex_color(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _extract_palette(image: Image.Image, top: int = 5) -> List[str]:
    palette_img = image.resize((50, 50))
    colors = palette_img.getcolors(50 * 50) or []
    colors.sort(reverse=True, key=lambda item: item[0])
    return [_hex_color(color[1]) for color in colors[:top]]


def analyze_perseo_image(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Analizar una imagen para extraer insights rápidos."""
    image_url = payload.get("image_url")
    goals = payload.get("goals", [])
    tags = payload.get("tags", [])

    width = height = 0
    palette: List[str] = []
    average_color = None
    aspect_ratio = None

    if image_url:
        try:
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content)).convert("RGB")
            width, height = image.size
            palette = _extract_palette(image)
            aspect_ratio = round(width / height, 2) if height else None
            avg_pixel = tuple(int(mean(channel)) for channel in zip(*image.getdata()))
            average_color = _hex_color(avg_pixel)
        except Exception as exc:  # pylint: disable=broad-except
            palette = []
            average_color = None
            print(f"[PERSEO][image_analyzer] No se pudo analizar la imagen: {exc}")

    insights = []
    if "conversion" in goals:
        insights.append("Añadir CTA visible en los primeros 3 segundos.")
    if aspect_ratio and aspect_ratio < 1:
        insights.append("Formato vertical detectado: prioriza Reels/TikTok.")
    if tags:
        insights.append(f"Paleta debe reforzar {', '.join(tags[:3])}.")

    result = {
        "dimensions": {"width": width, "height": height, "aspect_ratio": aspect_ratio},
        "palette": palette,
        "average_color": average_color,
        "insights": insights or ["Proporciona más contexto para recomendaciones específicas."],
    }

    log_tool_execution(
        agent="PERSEO",
        tool_name="image_analyzer",
        description=f"Analizada imagen {image_url or 'sin URL'}",
        details={"goals": goals, "tags": tags, "result": result},
    )
    return result


def enhance_perseo_video(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Recomendar mejoras para un vídeo."""
    duration = payload.get("duration_seconds", 45)
    tone = payload.get("tone", "energético")
    platform = payload.get("platform", "meta")

    beats = max(3, duration // 10)
    timeline = [
        {
            "timestamp": round(i * (duration / beats), 1),
            "action": action,
        }
        for i, action in enumerate(
            [
                "Hook visual con claim directo",
                "Prueba social o métrica clave",
                "CTA sincronizado con beat final",
            ][:beats]
        )
    ]

    result = {
        "recommended_duration": min(duration, 45 if platform.lower() in ("meta", "tiktok") else duration),
        "tone": tone,
        "timeline": timeline,
        "audio_suggestions": [
            "Añadir whoosh de transición" if tone == "energético" else "Utilizar cama musical suave",
            "Subir volumen del CTA final 3 dB",
        ],
    }

    log_tool_execution(
        agent="PERSEO",
        tool_name="video_enhancer",
        description="Generado plan de mejora de vídeo",
        details={"payload": payload, "result": result},
    )
    return result


def run_seo_audit(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Auditoría técnica rápida."""
    keywords = payload.get("keywords", [])
    html_snapshot = (payload.get("html_snapshot") or "").lower()

    title_ok = "<title" in html_snapshot
    h1_count = html_snapshot.count("<h1")
    meta_desc = "meta name=\"description\"" in html_snapshot

    keyword_coverage = sum(1 for kw in keywords if kw.lower() in html_snapshot)
    total_keywords = len(keywords) or 1
    keyword_score = round(keyword_coverage / total_keywords * 100, 1)

    issues = []
    if not title_ok:
        issues.append("Falta etiqueta <title> optimizada.")
    if h1_count != 1:
        issues.append("Debe existir un único H1 por página.")
    if not meta_desc:
        issues.append("Añadir meta description con CTA.")

    result = {
        "score": max(30, 100 - len(issues) * 15),
        "keyword_score": keyword_score,
        "issues": issues or ["Checklist técnico aprobado."],
        "technical_checks": {
            "title": title_ok,
            "h1_count": h1_count,
            "meta_description": meta_desc,
        },
    }

    log_tool_execution(
        agent="PERSEO",
        tool_name="seo_audit_engine",
        description="Auditado sitio SEO",
        details={"payload": payload, "result": result},
        metrics={"score": result["score"]},
    )
    return result


def build_ads_blueprint(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Crear blueprint multicanal para campañas."""
    budget = payload.get("budget", 1000)
    audience = payload.get("audience", "general")
    objective = payload.get("objective", "leads")

    channel_mix = [
        {"channel": "Meta Ads", "allocation": round(budget * 0.45, 2), "why": "Optimiza awareness + conversión rápida."},
        {"channel": "Google Search", "allocation": round(budget * 0.35, 2), "why": "Captura demanda intensional."},
        {"channel": "YouTube Shorts", "allocation": round(budget * 0.20, 2), "why": "Construye autoridad visual."},
    ]

    kpis = {
        "cpl_target": 15 if objective == "leads" else None,
        "roas_target": 3.5 if objective == "ventas" else None,
        "ctr_target": 1.8,
    }

    result = {
        "audience": audience,
        "budget": budget,
        "channels": channel_mix,
        "kpis": {k: v for k, v in kpis.items() if v is not None},
        "next_steps": [
            "Configurar UTMs coherentes por canal",
            "Cargar creatividades validadas por JUSTICIA",
            "Activar alertas automáticas de gasto >20%",
        ],
    }

    log_tool_execution(
        agent="PERSEO",
        tool_name="ads_campaign_builder",
        description="Blueprint de anuncios generado",
        details={"payload": payload, "result": result},
    )
    return result

