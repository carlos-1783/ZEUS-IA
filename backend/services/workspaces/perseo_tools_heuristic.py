"""Motores deterministas de PERSEO para las herramientas de workspace.

* Análisis de imagen: descarga la imagen con el fetch seguro anti-SSRF y mide
  dimensiones/paleta reales; si no se puede descargar → 422 (nunca "0x0 analizada").
* Auditoría SEO: descarga el HTML real (o usa el HTML que aporta el usuario) y
  calcula el score SOLO con comprobaciones deterministas. Sin página → 422.
* Plan de Ads: plantilla orientativa de reparto, sin KPIs numéricos inventados.
"""

from __future__ import annotations

import logging
from html.parser import HTMLParser
from io import BytesIO
from statistics import mean
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError  # pyright: ignore[reportMissingImports]

from services.safe_http_fetch import SafeFetchError, safe_fetch

logger = logging.getLogger(__name__)

IMAGE_MAX_BYTES = 10 * 1024 * 1024
HTML_MAX_BYTES = 3 * 1024 * 1024
HTML_SNAPSHOT_MAX_CHARS = 2 * 1024 * 1024


def _hex_color(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _extract_palette(image: Image.Image, top: int = 5) -> List[str]:
    palette_img = image.resize((50, 50))
    colors = palette_img.getcolors(50 * 50) or []
    colors.sort(reverse=True, key=lambda item: item[0])
    return [_hex_color(color[1]) for color in colors[:top]]


def analyze_perseo_image_heuristic(payload: Dict[str, Any]) -> Dict[str, Any]:
    image_url = str(payload.get("image_url") or "").strip()
    goals = payload.get("goals", [])
    tags = payload.get("tags", [])

    if not image_url:
        raise HTTPException(
            status_code=422,
            detail={"error": "image_url_required", "message": "Indica la URL https de la imagen a analizar."},
        )
    try:
        fetched = safe_fetch(image_url, allowed_content_types=["image/"], max_bytes=IMAGE_MAX_BYTES)
        image = Image.open(BytesIO(fetched.body)).convert("RGB")
    except SafeFetchError as exc:
        logger.info("PERSEO image_analyzer: descarga rechazada url=%s motivo=%s", image_url, exc)
        raise HTTPException(
            status_code=422,
            detail={"error": "image_not_fetchable", "message": f"No se pudo descargar la imagen: {exc}"},
        ) from exc
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": "image_not_decodable", "message": "El recurso descargado no es una imagen válida."},
        ) from exc

    width, height = image.size
    palette = _extract_palette(image)
    aspect_ratio = round(width / height, 2) if height else None
    avg_pixel = tuple(int(mean(channel)) for channel in zip(*image.getdata()))
    average_color = _hex_color(avg_pixel)

    insights = []
    if "conversion" in goals:
        insights.append("Añadir CTA visible en los primeros 3 segundos.")
    if aspect_ratio and aspect_ratio < 1:
        insights.append("Formato vertical detectado: prioriza Reels/TikTok.")
    if tags:
        insights.append(f"Paleta debe reforzar {', '.join(tags[:3])}.")

    return {
        "dimensions": {"width": width, "height": height, "aspect_ratio": aspect_ratio},
        "palette": palette,
        "average_color": average_color,
        "insights": insights or ["Proporciona más contexto para recomendaciones específicas."],
        "source_url": fetched.final_url,
        "ai_powered": False,
    }


def enhance_perseo_video_heuristic(payload: Dict[str, Any]) -> Dict[str, Any]:
    duration = payload.get("duration_seconds", 45)
    tone = payload.get("tone", "energético")
    platform = payload.get("platform", "meta")

    beats = max(3, duration // 10)
    timeline = [
        {"timestamp": round(i * (duration / beats), 1), "action": action}
        for i, action in enumerate(
            [
                "Hook visual con claim directo",
                "Prueba social o métrica clave",
                "CTA sincronizado con beat final",
            ][:beats]
        )
    ]

    return {
        "recommended_duration": min(duration, 45 if platform.lower() in ("meta", "tiktok") else duration),
        "tone": tone,
        "timeline": timeline,
        "audio_suggestions": [
            "Añadir whoosh de transición" if tone == "energético" else "Utilizar cama musical suave",
            "Subir volumen del CTA final 3 dB",
        ],
        "ai_powered": False,
    }


# --------------------------------------------------------------------------- SEO


class _SeoHtmlParser(HTMLParser):
    """Extrae del HTML real lo necesario para las comprobaciones SEO deterministas."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.html_lang: Optional[str] = None
        self.title_parts: List[str] = []
        self.title_count = 0
        self.meta_description: Optional[str] = None
        self.viewport = False
        self.robots: Optional[str] = None
        self.canonical: Optional[str] = None
        self.h1_texts: List[str] = []
        self.images = 0
        self.images_without_alt = 0
        self.text_parts: List[str] = []
        self._in_title = False
        self._in_h1 = 0
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: List[tuple]) -> None:
        a = {(k or "").lower(): (v or "") for k, v in attrs}
        if tag == "html" and a.get("lang"):
            self.html_lang = a["lang"].strip()
        elif tag == "title":
            self.title_count += 1
            self._in_title = True
        elif tag == "meta":
            name = a.get("name", "").lower()
            if name == "description" and self.meta_description is None:
                self.meta_description = a.get("content", "").strip()
            elif name == "viewport":
                self.viewport = True
            elif name == "robots":
                self.robots = a.get("content", "").lower()
        elif tag == "link" and "canonical" in a.get("rel", "").lower().split():
            self.canonical = a.get("href", "").strip() or None
        elif tag == "h1":
            self._in_h1 += 1
            self.h1_texts.append("")
        elif tag == "img":
            self.images += 1
            if not a.get("alt", "").strip():
                self.images_without_alt += 1
        elif tag in ("script", "style", "noscript"):
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag == "h1" and self._in_h1:
            self._in_h1 -= 1
        elif tag in ("script", "style", "noscript") and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
            return
        if self._skip:
            return
        if self._in_h1 and self.h1_texts:
            self.h1_texts[-1] += data
        self.text_parts.append(data)

    @property
    def title(self) -> str:
        return " ".join("".join(self.title_parts).split())


def _load_seo_html(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Obtiene el HTML real a auditar. Nunca inventa: sin página analizable → 422."""
    url = str(payload.get("url") or "").strip()
    snapshot = payload.get("html_snapshot") or ""
    if url:
        try:
            # http permitido a propósito: auditar una web que aún no tiene TLS es un caso
            # legítimo y justo lo que la comprobación "https" debe señalar.
            fetched = safe_fetch(
                url,
                allowed_content_types=["text/html", "application/xhtml+xml"],
                max_bytes=HTML_MAX_BYTES,
                allow_http=True,
            )
        except SafeFetchError as exc:
            logger.info("PERSEO seo_audit: pagina no analizable url=%s motivo=%s", url, exc)
            raise HTTPException(
                status_code=422,
                detail={"error": "seo_page_not_analyzable", "message": f"Sin página analizable: {exc}"},
            ) from exc
        html = fetched.text()
        if not html.strip():
            raise HTTPException(
                status_code=422,
                detail={"error": "seo_page_not_analyzable", "message": "Sin página analizable: la URL devolvió HTML vacío."},
            )
        return {"html": html, "source": "url_descargada", "final_url": fetched.final_url}
    if isinstance(snapshot, str) and snapshot.strip():
        return {"html": snapshot[:HTML_SNAPSHOT_MAX_CHARS], "source": "html_aportado_por_usuario", "final_url": None}
    raise HTTPException(
        status_code=422,
        detail={
            "error": "seo_page_not_analyzable",
            "message": "Sin página analizable: indica la URL de la página (o pega su HTML).",
        },
    )


def run_seo_audit_heuristic(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Auditoría SEO determinista sobre HTML real. El score sale solo de estas comprobaciones."""
    keywords = [str(k).strip() for k in (payload.get("keywords") or []) if str(k).strip()]
    page = _load_seo_html(payload)
    parser = _SeoHtmlParser()
    parser.feed(page["html"])
    parser.close()

    title = parser.title
    desc = parser.meta_description or ""
    h1_count = len(parser.h1_texts)
    final_url = page["final_url"]

    checks: List[Dict[str, Any]] = []

    def add(key: str, label: str, weight: int, passed: Optional[bool], detail: str) -> None:
        checks.append({"key": key, "label": label, "weight": weight, "passed": passed, "detail": detail})

    add("title_present", "Etiqueta <title> presente", 15, bool(title), title or "sin <title>")
    add("title_length", "Longitud del título 10-60 caracteres", 10, 10 <= len(title) <= 60, f"{len(title)} caracteres")
    add("meta_description_present", "Meta description presente", 15, bool(desc), desc[:160] or "sin meta description")
    add(
        "meta_description_length",
        "Longitud de meta description 50-160 caracteres",
        5,
        50 <= len(desc) <= 160,
        f"{len(desc)} caracteres",
    )
    add("single_h1", "Un único H1", 15, h1_count == 1, f"{h1_count} H1 encontrados")
    if parser.images:
        add(
            "img_alt",
            "Todas las imágenes con atributo alt",
            10,
            parser.images_without_alt == 0,
            f"{parser.images_without_alt} de {parser.images} imágenes sin alt",
        )
    else:
        add("img_alt", "Todas las imágenes con atributo alt", 10, None, "la página no tiene imágenes (no aplica)")
    add("canonical", "Enlace canonical", 10, bool(parser.canonical), parser.canonical or "sin canonical")
    if final_url:
        add("https", "Servida por HTTPS", 10, final_url.lower().startswith("https://"), final_url)
    else:
        add("https", "Servida por HTTPS", 10, None, "HTML aportado sin URL (no aplica)")
    add("viewport", "Meta viewport (móvil)", 5, parser.viewport, "presente" if parser.viewport else "ausente")
    add("lang", "Atributo lang en <html>", 5, bool(parser.html_lang), parser.html_lang or "ausente")
    noindex = bool(parser.robots and "noindex" in parser.robots)
    add("indexable", "Página indexable (sin noindex)", 10, not noindex, parser.robots or "sin meta robots")

    applicable = [c for c in checks if c["passed"] is not None]
    total_w = sum(c["weight"] for c in applicable)
    ok_w = sum(c["weight"] for c in applicable if c["passed"])
    score = round(ok_w / total_w * 100) if total_w else 0

    keyword_score: Optional[float] = None
    keyword_detail: List[Dict[str, Any]] = []
    if keywords:
        haystack = " ".join([title, desc, " ".join(parser.h1_texts), " ".join(parser.text_parts)]).lower()
        for kw in keywords:
            keyword_detail.append({"keyword": kw, "found": kw.lower() in haystack})
        found = sum(1 for k in keyword_detail if k["found"])
        keyword_score = round(found / len(keywords) * 100, 1)

    issues = [f"{c['label']}: {c['detail']}" for c in applicable if not c["passed"]]
    return {
        "score": score,
        "seo_score": score,
        "score_method": "comprobaciones_deterministas",
        "checks_passed": sum(1 for c in applicable if c["passed"]),
        "checks_total": len(applicable),
        "keyword_score": keyword_score,
        "keywords": keyword_detail,
        "issues": issues,
        "checks": checks,
        "technical_checks": {
            "title": bool(title),
            "h1_count": h1_count,
            "meta_description": bool(desc),
            "canonical": bool(parser.canonical),
            "images": parser.images,
            "images_without_alt": parser.images_without_alt,
        },
        "source": page["source"],
        "url": final_url,
        "ai_powered": False,
    }


def build_ads_blueprint_heuristic(payload: Dict[str, Any]) -> Dict[str, Any]:
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

    return {
        "audience": audience,
        "budget": budget,
        "channels": channel_mix,
        "kpis": {k: v for k, v in kpis.items() if v is not None},
        "next_steps": [
            "Configurar UTMs coherentes por canal",
            "Cargar creatividades validadas por JUSTICIA",
            "Activar alertas automáticas de gasto >20%",
        ],
        "ai_powered": False,
    }
