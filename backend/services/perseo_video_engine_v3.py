"""
PERSEO Video Engine v3.0 — conversión real con FFmpeg (imagen → vídeo vertical 15s).

Pipeline: download_asset → ai_copy → ffmpeg_loop_image → timed drawtext overlays → cloud/local storage → CRM.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.company import Company, UserCompany
from app.models.user import User
from services.crm_office_service import company_ids_for_user, log_activity
from services.perseo_storage_v2 import s3_configured, storage_backend, upload_file
from services.perseo_video_engine_v1 import _ffmpeg_exe
from services.zeus_execution_controller_v1 import get_execution_status

logger = logging.getLogger(__name__)

ENGINE_VERSION = "3.0.0"
DURATION_SEC = 15
RESOLUTION = (1080, 1920)
FPS = 30
MAX_WORDS_PER_SCENE = 15

GENERIC_PHRASES = (
    "lorem ipsum",
    "descubre más",
    "nuestra empresa",
    "somos líderes",
    "calidad garantizada",
    "el mejor servicio",
    "sin compromiso",
    "términos y condiciones",
    "consulta con tu médico",
)

SCENE_TIMINGS = (
    ("hook", 0, 3, "bold_center"),
    ("problem", 3, 7, "center"),
    ("solution", 7, 11, "center"),
    ("cta", 11, 15, "highlight_box"),
)


def _ffmpeg_path() -> str:
    custom = (os.getenv("FFMPEG_PATH") or "").strip()
    if custom and Path(custom).is_file():
        return custom
    return _ffmpeg_exe()


def _temp_root() -> Path:
    raw = (os.getenv("TEMP_DIR") or os.getenv("PERSEO_TEMP_DIR") or "").strip()
    if raw:
        p = Path(raw)
        p.mkdir(parents=True, exist_ok=True)
        return p
    return Path(tempfile.gettempdir())


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", (text or "").strip()))


def _limit_words(text: str, max_words: int = MAX_WORDS_PER_SCENE) -> str:
    words = re.findall(r"\S+", (text or "").strip())
    return " ".join(words[:max_words])


def _is_generic_copy(script: Dict[str, str]) -> bool:
    blob = " ".join(script.get(k, "") for k in ("hook", "problem", "solution", "cta")).lower()
    if any(p in blob for p in GENERIC_PHRASES):
        return True
    if not (script.get("cta") or "").strip():
        return True
    for key in ("hook", "problem", "solution", "cta"):
        if _word_count(script.get(key, "")) < 2:
            return True
    return False


def _validate_script(script: Dict[str, str]) -> None:
    missing = [k for k in ("hook", "problem", "solution", "cta") if not (script.get(k) or "").strip()]
    if missing:
        raise HTTPException(
            status_code=422,
            detail={"error": "invalid_script", "missing": missing, "message": "Script incompleto"},
        )
    if _is_generic_copy(script):
        raise HTTPException(
            status_code=422,
            detail={"error": "generic_copy", "message": "Copy genérico o sin CTA — regeneración requerida"},
        )
    for key in ("hook", "problem", "solution", "cta"):
        if _word_count(script[key]) > MAX_WORDS_PER_SCENE:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "scene_too_long",
                    "field": key,
                    "max_words": MAX_WORDS_PER_SCENE,
                },
            )


def resolve_tenant_company(db: Session, user: User, tenant_id: str) -> Tuple[Company, int]:
    tid = (tenant_id or "").strip()
    if not tid:
        raise HTTPException(status_code=422, detail="tenant_id required")

    allowed = company_ids_for_user(db, user)
    company: Optional[Company] = None

    if tid.isdigit():
        cid = int(tid)
        if allowed and cid not in allowed:
            raise HTTPException(status_code=403, detail="Sin acceso al tenant")
        company = db.query(Company).filter(Company.id == cid).first()
    else:
        company = db.query(Company).filter(Company.slug == tid).first()
        if company and allowed and company.id not in allowed:
            raise HTTPException(status_code=403, detail="Sin acceso al tenant")

    if not company:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")
    return company, company.id


def _branding_for_tenant(
    company: Company,
    branding: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    meta = company.metadata_ if isinstance(company.metadata_, dict) else {}
    brand_block = meta.get("branding") if isinstance(meta.get("branding"), dict) else {}
    override = branding or {}
    primary = (
        str(override.get("primary_color") or brand_block.get("primary_color") or "#4338ca").strip()
    )
    if not re.match(r"^#[0-9A-Fa-f]{6}$", primary):
        primary = "#4338ca"
    logo = str(override.get("logo") or brand_block.get("logo") or "").strip()
    return {
        "company_name": company.company_name,
        "primary_color": primary,
        "logo": logo,
    }


def _resolve_image_path(image_url: str, user_id: int) -> Path:
    raw = (image_url or "").strip()
    if not raw:
        raise HTTPException(status_code=422, detail="image_url required")

    if raw.startswith("http://") or raw.startswith("https://"):
        try:
            resp = requests.get(raw, timeout=30)
            resp.raise_for_status()
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"No se pudo descargar imagen: {exc}") from exc
        suffix = Path(urlparse(raw).path).suffix or ".jpg"
        if suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
            suffix = ".jpg"
        dest = _temp_root() / f"perseo_v3_{user_id}_{uuid.uuid4().hex[:8]}{suffix}"
        dest.write_bytes(resp.content)
        return dest

    if raw.startswith("/static/"):
        rel = raw[len("/static/") :]
        path = Path(settings.STATIC_DIR) / rel
    elif raw.startswith("/"):
        path = Path(settings.STATIC_DIR) / raw.lstrip("/")
    else:
        path = Path(settings.STATIC_DIR) / raw.lstrip("/")

    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail=f"Imagen no encontrada: {raw}")
    return path


def _generate_conversion_copy(
    *,
    product_info: Optional[str],
    branding: Dict[str, Any],
    image_url: Optional[str],
) -> Dict[str, Any]:
    from services.perseo_ai_service_v2 import openai_configured

    product = (product_info or branding.get("company_name") or "tu negocio").strip()
    if openai_configured():
        from services.perseo_ai_service_v2 import _text_completion

        system = (
            "Eres PERSEO, copywriter de conversión para vídeo vertical 15s. "
            "Responde SOLO JSON con keys: hook, problem, solution, cta. "
            "Reglas estrictas: máximo 15 palabras por campo, sin disclaimers, "
            "sin texto genérico, siempre CTA accionable con urgencia, en español."
        )
        user_text = f"Producto/servicio: {product}. Marca: {branding.get('company_name', '')}."
        if image_url:
            user_text += f" Imagen referencia: {image_url[:200]}."
        try:
            out = _text_completion(system, user_text)
            script = {
                "hook": _limit_words(str(out.get("hook") or "")),
                "problem": _limit_words(str(out.get("problem") or "")),
                "solution": _limit_words(str(out.get("solution") or "")),
                "cta": _limit_words(str(out.get("cta") or "")),
            }
            if not _is_generic_copy(script):
                return {"script": script, "ai_powered": True, "mode": "conversion_only"}
        except Exception as exc:
            logger.warning("[PERSEO_V3] OpenAI copy failed: %s", exc)

    script = {
        "hook": _limit_words(f"¿Cansado de perder clientes con {product[:40]}?"),
        "problem": _limit_words("Cada día pierdes ventas sin un mensaje claro"),
        "solution": _limit_words(f"{branding.get('company_name', 'Nosotros')} lo resuelve hoy mismo"),
        "cta": _limit_words("Reserva ahora — plazas limitadas"),
    }
    return {"script": script, "ai_powered": False, "mode": "heuristic_conversion"}


def _hex_to_ffmpeg_color(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    if len(h) == 6:
        return f"0x{h}@0.75"
    return "0x4338ca@0.75"


def _font_file() -> str:
    candidates = [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path(r"C:\Windows\Fonts\arialbd.ttf"),
        Path(r"C:\Windows\Fonts\arial.ttf"),
    ]
    for p in candidates:
        if p.is_file():
            return str(p).replace("\\", "/").replace(":", "\\:")
    return ""


def _build_drawtext_filter(
    tmpdir: Path,
    script: Dict[str, str],
    branding: Dict[str, Any],
) -> str:
    w, h = RESOLUTION
    font = _font_file()
    font_part = f"fontfile={font}:" if font else ""
    cta_color = _hex_to_ffmpeg_color(branding.get("primary_color", "#4338ca"))

    parts: List[str] = [
        f"scale={w}:{h}:force_original_aspect_ratio=decrease",
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black",
        "format=yuv420p",
    ]

    for key, start, end, style in SCENE_TIMINGS:
        text = script.get(key, "")
        tf = tmpdir / f"{key}.txt"
        tf.write_text(text, encoding="utf-8")
        tpath = str(tf).replace("\\", "/").replace(":", "\\:")
        y_pos = "h*0.12" if style == "bold_center" else "h*0.42"
        fs = "64" if style == "bold_center" else "48"
        base = (
            f"drawtext={font_part}textfile='{tpath}':fontsize={fs}:fontcolor=white:"
            f"x=(w-text_w)/2:y={y_pos}:enable='between(t\\,{start}\\,{end})'"
        )
        if style == "highlight_box":
            base = (
                f"drawtext={font_part}textfile='{tpath}':fontsize=52:fontcolor=white:"
                f"box=1:boxcolor={cta_color}:boxborderw=16:"
                f"x=(w-text_w)/2:y=h*0.78:enable='between(t\\,{start}\\,{end})'"
            )
        parts.append(base)

    return ",".join(parts)


def _run_ffmpeg_pipeline(image_path: Path, vf: str, output_path: Path) -> None:
    ffmpeg = _ffmpeg_path()
    cmd = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-loop",
        "1",
        "-framerate",
        str(FPS),
        "-i",
        str(image_path),
        "-t",
        str(DURATION_SEC),
        "-vf",
        vf,
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        str(getattr(settings, "PERSEO_FFMPEG_PRESET", "veryfast")),
        "-crf",
        str(getattr(settings, "PERSEO_VIDEO_CRF", 23)),
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-r",
        str(FPS),
        str(output_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or "ffmpeg failure")
    if not output_path.exists() or output_path.stat().st_size < 2048:
        raise RuntimeError("empty video output")


def _persist_video(
    video_path: Path,
    *,
    user_id: int,
    company_id: int,
) -> Dict[str, Any]:
    if storage_backend() == "s3" and s3_configured():
        stored = upload_file(
            video_path,
            user_id=user_id,
            category=f"tenant_{company_id}/videos",
            content_type="video/mp4",
        )
        return {"video_url": stored["url"], "storage": "cloud", **stored}

    dest_dir = Path(settings.STATIC_DIR) / "uploads" / "videos" / f"tenant_{company_id}"
    dest_dir.mkdir(parents=True, exist_ok=True)
    fname = f"perseo_v3_{uuid.uuid4().hex[:10]}.mp4"
    final = dest_dir / fname
    shutil.copy2(video_path, final)
    return {
        "video_url": f"/static/uploads/videos/tenant_{company_id}/{fname}",
        "storage": "local",
        "path": str(final),
    }


def _crm_integrate(
    db: Session,
    *,
    user: User,
    company_id: int,
    video_url: str,
    script: Dict[str, str],
    lead_id: Optional[int],
    campaign_id: Optional[str],
    customer_id: Optional[int],
) -> Dict[str, Any]:
    payload = {
        "video_url": video_url,
        "script": script,
        "engine": "perseo_video_engine_v3",
        "version": ENGINE_VERSION,
        "campaign_id": campaign_id,
    }
    log_activity(
        db,
        company_id=company_id,
        user_id=user.id,
        customer_id=customer_id,
        record_id=None,
        action="perseo_video_generated",
        summary="Vídeo PERSEO v3 generado",
        payload=payload,
        commit=False,
    )

    if lead_id:
        from app.models.crm_lead import CrmLead

        lead = (
            db.query(CrmLead)
            .filter(CrmLead.id == lead_id, CrmLead.company_id == company_id)
            .first()
        )
        if lead:
            insights = {}
            try:
                insights = json.loads(lead.external_insights_json or "{}")
            except json.JSONDecodeError:
                insights = {}
            assets = insights.get("video_assets") if isinstance(insights.get("video_assets"), list) else []
            assets.append({"video_url": video_url, "script": script, "campaign_id": campaign_id})
            insights["video_assets"] = assets[-20:]
            lead.external_insights_json = json.dumps(insights, ensure_ascii=False)
            db.add(lead)
            payload["lead_attached"] = True

    company = db.query(Company).filter(Company.id == company_id).first()
    if company:
        meta = dict(company.metadata_ or {})
        campaigns = meta.get("perseo_campaigns") if isinstance(meta.get("perseo_campaigns"), dict) else {}
        cid = campaign_id or f"auto_{uuid.uuid4().hex[:8]}"
        camp = campaigns.get(cid) if isinstance(campaigns.get(cid), dict) else {}
        camp_videos = camp.get("videos") if isinstance(camp.get("videos"), list) else []
        camp_videos.append(video_url)
        camp["videos"] = camp_videos[-50:]
        camp["last_video_at"] = __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat()
        campaigns[cid] = camp
        meta["perseo_campaigns"] = campaigns
        assets = meta.get("video_assets") if isinstance(meta.get("video_assets"), list) else []
        assets.append({"url": video_url, "script": script})
        meta["video_assets"] = assets[-100:]
        company.metadata_ = meta
        db.add(company)
        payload["campaign_linked"] = cid

    db.commit()
    return {
        "crm_saved": True,
        "store_video_asset": True,
        "link_to_campaign": bool(campaign_id or company),
        "attach_to_lead": bool(lead_id and payload.get("lead_attached")),
    }


def generate_perseo_video_v3(
    db: Session,
    user: User,
    *,
    tenant_id: str,
    image_url: str,
    product_info: Optional[str] = None,
    branding: Optional[Dict[str, Any]] = None,
    lead_id: Optional[int] = None,
    campaign_id: Optional[str] = None,
    customer_id: Optional[int] = None,
) -> Dict[str, Any]:
    execution = get_execution_status(db)
    if execution["execution_mode"] == "ERROR":
        raise HTTPException(status_code=503, detail="execution_mode ERROR")
    if not execution["writes_enabled"]:
        raise HTTPException(
            status_code=403,
            detail="writes_enabled false — activa AFRODITA_EXECUTION_ENABLED",
        )

    _ffmpeg_path()
    company, company_id = resolve_tenant_company(db, user, tenant_id)
    brand = _branding_for_tenant(company, branding)

    copy_result = _generate_conversion_copy(
        product_info=product_info,
        branding=brand,
        image_url=image_url,
    )
    script = copy_result["script"]
    _validate_script(script)

    image_path = _resolve_image_path(image_url, user.id)
    work = _temp_root() / f"perseo_v3_job_{uuid.uuid4().hex[:10]}"
    work.mkdir(parents=True, exist_ok=True)
    out_mp4 = work / "output.mp4"

    try:
        vf = _build_drawtext_filter(work, script, brand)
        _run_ffmpeg_pipeline(image_path, vf, out_mp4)
        stored = _persist_video(out_mp4, user_id=user.id, company_id=company_id)
        crm = _crm_integrate(
            db,
            user=user,
            company_id=company_id,
            video_url=stored["video_url"],
            script=script,
            lead_id=lead_id,
            campaign_id=campaign_id,
            customer_id=customer_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("[PERSEO_V3] generation failed tenant=%s", tenant_id)
        raise HTTPException(
            status_code=500,
            detail={"error": "ffmpeg_failure", "message": str(exc)[:400]},
        ) from exc
    finally:
        if image_path.parent == _temp_root() and image_path.exists():
            try:
                image_path.unlink()
            except OSError:
                pass
        if work.exists():
            shutil.rmtree(work, ignore_errors=True)

    return {
        "success": True,
        "engine": "perseo_video_engine_v3",
        "version": ENGINE_VERSION,
        "execution": "real",
        "multi_tenant": {
            "tenant_id": str(company_id),
            "tenant_slug": company.slug,
            "dynamic_branding": True,
        },
        "video_url": stored["video_url"],
        "script": script,
        "downloadable": True,
        "format": "mp4",
        "codec": "h264",
        "duration_sec": DURATION_SEC,
        "resolution": f"{RESOLUTION[0]}x{RESOLUTION[1]}",
        "storage": stored.get("storage", "local"),
        "copy_engine": copy_result,
        "crm": crm,
    }


def video_engine_v3_configured() -> bool:
    try:
        _ffmpeg_path()
        return True
    except Exception:
        return False
