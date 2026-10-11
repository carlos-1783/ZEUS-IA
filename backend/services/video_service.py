"""
Vídeo de presentación para entregables PERSEO (composición, no generación I2V).

Paridad con plataformas tipo **Google Veo 3.x** (video generado por modelo, audio,
movimiento físico, 4K): no es alcanzable solo con PIL/MoviePy; requeriría integrar
la API de Veo/Gemini (Vertex) u otro proveedor I2V con clave y coste por clip.

Este módulo apunta a **edición tipo “presentación broadcast”**: 16:9 configurable,
tipografía TrueType, crossfade entre diapositivas, H.264 con CRF y fps constante.
"""

from __future__ import annotations

import io
import logging
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont  # type: ignore

from services.automation.utils import store_output, timestamp

logger = logging.getLogger(__name__)


# Diseño base 1280×720; las coordenadas se escalan a PERSEO_VIDEO_WIDTH (16:9).
DESIGN_W = 1280
DESIGN_H = 720
BACKGROUND = (12, 20, 38)
PANEL = (241, 245, 249)
ACCENT = (59, 130, 246)
SUBACCENT = (96, 165, 250)
TEXT_COLOR = (15, 23, 42)
WHITE = (255, 255, 255)


@dataclass(frozen=True)
class _VideoEncodeParams:
    width: int
    height: int
    fps: int
    crossfade_sec: float
    crf: int
    seconds_per_slide: float


def _video_encode_params(deliverable: Dict[str, Any]) -> _VideoEncodeParams:
    from app.core.config import settings

    w = max(1280, min(int(settings.PERSEO_VIDEO_WIDTH), 3840))
    h = w * 9 // 16
    fps = max(12, min(int(settings.PERSEO_VIDEO_FPS), 60))
    cf = max(0.0, min(float(settings.PERSEO_VIDEO_CROSSFADE_SEC), 2.0))
    crf = max(16, min(int(settings.PERSEO_VIDEO_CRF), 28))
    try:
        spf = deliverable.get("seconds_per_slide")
        if spf is None:
            spf = float(settings.PERSEO_VIDEO_SECONDS_PER_SLIDE)
        else:
            spf = float(spf)
    except (TypeError, ValueError):
        spf = 5.0
    spf = max(1.0, min(spf, 120.0))
    return _VideoEncodeParams(w, h, fps, cf, crf, spf)


def _scale_xy(w: int, h: int, x: int, y: int) -> Tuple[int, int]:
    return int(x * w / DESIGN_W), int(y * h / DESIGN_H)


def _truetype_font(size_px: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    size_px = max(12, size_px)
    candidates = [
        Path(r"C:\Windows\Fonts\segoeuib.ttf"),
        Path(r"C:\Windows\Fonts\segoeui.ttf"),
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    ]
    for p in candidates:
        try:
            if p.is_file():
                return ImageFont.truetype(str(p), size=size_px)
        except OSError:
            continue
    return ImageFont.load_default()


def _expand_timeline_crossfade(
    slides: List[Image.Image],
    *,
    hold_seconds: float,
    fps: int,
    crossfade_seconds: float,
) -> List[Image.Image]:
    import numpy as np  # pyright: ignore[reportMissingImports]

    hold = max(1, int(round(hold_seconds * float(fps))))
    xf = int(round(crossfade_seconds * float(fps)))
    xf = max(0, min(xf, max(0, hold - 1)))

    if not slides:
        return []
    if len(slides) == 1:
        base = slides[0].convert("RGB")
        return [base.copy() for _ in range(hold)]

    out: List[Image.Image] = []
    n = len(slides)
    for i in range(n):
        arr = np.array(slides[i].convert("RGB"), dtype=np.float32)
        if i < n - 1:
            arr_next = np.array(slides[i + 1].convert("RGB"), dtype=np.float32)
            for _ in range(hold - xf):
                out.append(Image.fromarray(arr.astype(np.uint8)))
            for t in range(xf):
                a = (t + 1) / (xf + 1) if xf > 0 else 0.0
                blend = (1.0 - a) * arr + a * arr_next
                out.append(Image.fromarray(np.clip(blend, 0, 255).astype(np.uint8)))
        else:
            for _ in range(hold):
                out.append(Image.fromarray(arr.astype(np.uint8)))
    return out


def generate_marketing_video(
    deliverable: Dict[str, Any],
    agent: str,
    prefix: str,
    artifact_id: Optional[str] = None,
    *,
    company_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Genera el recurso de video asociado a un entregable (MP4; GIF si no hay ffmpeg).

    Fase 2 / Step 1: se codifica en un directorio temporal y el resultado se guarda en R2
    como entregable de la empresa (antes: storage/outputs en disco efimero). Sin empresa o
    sin R2 no hay donde guardarlo y se devuelve success=False con el motivo.
    """
    import tempfile

    enc = _video_encode_params(deliverable)
    logical = _build_frames(deliverable, enc.width, enc.height, user_id=user_id)
    if not logical:
        logger.warning("No se generaron frames para el vídeo de PERSEO")
        return {"success": False, "reason": "no_frames"}

    frames = _expand_timeline_crossfade(
        logical,
        hold_seconds=enc.seconds_per_slide,
        fps=enc.fps,
        crossfade_seconds=enc.crossfade_sec,
    )

    base_name = artifact_id or f"{prefix}_{timestamp()}"
    with tempfile.TemporaryDirectory(prefix="perseo_video_") as tmp:
        work = Path(tmp)
        mp4_path = work / f"{base_name}.mp4"
        logger.info(f"Intentando generar MP4 para {base_name}...")
        if _write_mp4(frames, mp4_path, fps=enc.fps, crf=enc.crf):
            return _store_video_asset(
                agent, mp4_path, "mp4", "generated", len(frames), company_id=company_id, user_id=user_id
            )

        logger.warning("MP4 falló, generando GIF como fallback...")
        gif_path = work / f"{base_name}_fallback.gif"
        gif_ms = max(20, int(round(1000.0 / max(1, enc.fps))))
        if _write_gif(frames, gif_path, frame_duration_ms=gif_ms):
            payload = _store_video_asset(
                agent, gif_path, "gif", "fallback_gif", len(frames), company_id=company_id, user_id=user_id
            )
            if payload.get("success"):
                payload["note"] = "MP4 no disponible (FFmpeg requerido). Se generó GIF como alternativa."
            return payload

    logger.error("No se pudo generar ni MP4 ni GIF para el entregable PERSEO")
    return {"success": False, "reason": "generation_failed"}


def _store_video_asset(
    agent: str,
    file_path: Path,
    fmt: str,
    status: str,
    frame_count: int,
    *,
    company_id: Optional[int],
    user_id: Optional[int],
) -> Dict[str, Any]:
    data = file_path.read_bytes()
    ctype = "video/mp4" if fmt == "mp4" else "image/gif"
    stored = store_output(agent, file_path.name, data, ctype, company_id=company_id, user_id=user_id)
    if not stored:
        return {
            "success": False,
            "reason": "storage_unavailable",
            "error": "Vídeo generado pero sin almacenamiento externo (R2) o sin empresa donde guardarlo.",
        }
    return {
        "success": True,
        "file_id": stored["file_id"],
        "url": stored["url"],
        "filename": stored["filename"],
        "download_path": stored["download_path"],
        "format": fmt,
        "status": status,
        "frame_count": frame_count,
        "file_size": len(data),
    }


def _ensure_rgb_max(im: Image.Image) -> Image.Image:
    im = im.convert("RGB")
    try:
        resample = Image.Resampling.LANCZOS
    except AttributeError:
        resample = Image.LANCZOS  # type: ignore[attr-defined]
    im.thumbnail((1920, 1920), resample)
    return im


def _load_reference_image(raw: str, user_id: Optional[int]) -> Optional[Image.Image]:
    """Imagen de referencia desde R2, solo si es un fichero de una empresa del usuario.

    Fase 2 / Step 1: antes se leia cualquier ruta de STATIC_DIR o se descargaba cualquier
    URL http(s) desde el servidor (SSRF). Si no se puede resolver, el video se genera sin
    diapositiva de referencia (se registra el motivo)."""
    from fastapi import HTTPException

    from app.db.base import SessionLocal
    from services import object_storage
    from services.perseo_media_io import find_input

    if not (raw or "").strip() or not user_id:
        return None
    db = SessionLocal()
    try:
        row = find_input(db, raw, user_id)
        data = object_storage.read_bytes(row)
        return _ensure_rgb_max(Image.open(io.BytesIO(data)))
    except HTTPException as exc:
        logger.warning("Imagen de referencia no resoluble (%s): %s", exc.status_code, exc.detail)
    except Exception as exc:
        logger.warning("No se pudo cargar la imagen de referencia: %s", type(exc).__name__)
    finally:
        db.close()
    return None


def _render_reference_slide(
    pil_img: Image.Image, caption: str, width: int, height: int
) -> Image.Image:
    image = Image.new("RGB", (width, height), color=BACKGROUND)
    draw = ImageDraw.Draw(image)
    fs_title = max(28, int(44 * width / DESIGN_W))
    fs_small = max(18, int(26 * width / DESIGN_W))
    font_title = _truetype_font(fs_title)
    font_small = _truetype_font(fs_small)
    x0, y0 = _scale_xy(width, height, 140, 90)
    draw.text((x0, y0), "Referencia visual", fill=WHITE, font=font_title, spacing=4)
    box_left, box_top = _scale_xy(width, height, 140, 150)
    box_right, box_bottom = _scale_xy(width, height, DESIGN_W - 140, DESIGN_H - 150)
    bw, bh = box_right - box_left, box_bottom - box_top
    pic = pil_img.copy()
    try:
        resample = Image.Resampling.LANCZOS
    except AttributeError:
        resample = Image.LANCZOS  # type: ignore[attr-defined]
    pic.thumbnail((max(1, bw), max(1, bh)), resample)
    iw, ih = pic.size
    x = box_left + (bw - iw) // 2
    y = box_top + (bh - ih) // 2
    image.paste(pic, (x, y))
    wrap = max(28, int(52 * width / DESIGN_W))
    if caption.strip():
        wrapped = "\n".join(textwrap.wrap(caption.strip(), width=wrap))
        tx, ty = _scale_xy(width, height, 140, DESIGN_H - 130)
        draw.text((tx, ty), wrapped, fill=SUBACCENT, font=font_small, spacing=4)
    rx1, ry1 = _scale_xy(width, height, 140, DESIGN_H - 52)
    rx2, ry2 = _scale_xy(width, height, DESIGN_W - 140, DESIGN_H - 38)
    draw.rectangle((rx1, ry1, rx2, ry2), fill=ACCENT)
    fx, fy = _scale_xy(width, height, 152, DESIGN_H - 50)
    draw.text(
        (fx, fy),
        "ZEUS IA • PERSEO (imagen del chat)",
        fill=WHITE,
        font=font_small,
    )
    return image


def _build_frames(
    deliverable: Dict[str, Any], width: int, height: int, *, user_id: Optional[int] = None
) -> List[Image.Image]:
    frames: List[Image.Image] = []

    ref_raw = deliverable.get("reference_image_url") or deliverable.get("reference_image")
    if isinstance(ref_raw, str) and ref_raw.strip():
        ref_pil = _load_reference_image(ref_raw, user_id)
        if ref_pil:
            cap = str(deliverable.get("reference_caption") or "").strip()
            frames.append(_render_reference_slide(ref_pil, cap, width, height))
        else:
            logger.warning(
                "Hay reference_image_url pero no se pudo cargar para el vídeo: %s",
                ref_raw[:120],
            )

    summary = deliverable.get("summary")
    if summary:
        frames.append(_render_slide("Resumen ejecutivo", summary, width, height))

    script = deliverable.get("video_script") or {}
    structure = script.get("structure") or []
    for idx, segment in enumerate(structure, start=1):
        title = segment.get("segment") or f"Sección {idx}"
        copy = segment.get("copy") or ""
        frames.append(_render_slide(title, copy, width, height, accent=True))

    distribution = deliverable.get("distribution_plan") or {}
    launch_date = distribution.get("launch_date")
    if launch_date:
        frames.append(
            _render_slide(
                "Plan de difusión",
                f"Lanzamiento previsto el {launch_date}. "
                "Canales listos con copy y automatizaciones configuradas.",
                width,
                height,
            )
        )

    automation = distribution.get("automation") or {}
    if automation:
        bullets = "\n".join(
            f"- {key.upper()}: {value}"
            for key, value in automation.items()
        )
        frames.append(
            _render_slide(
                "Automatizaciones activas",
                bullets or "Secuencias en espera de activación.",
                width,
                height,
            )
        )

    cta = (deliverable.get("cta_slide") or "").strip() or (
        "Activa ZEUS IA hoy y deja que PERSEO automatice tu marketing 24/7."
    )
    frames.append(_render_slide("CTA", cta, width, height, highlight=True))

    return frames


def _render_slide(
    title: str,
    body: str,
    width: int,
    height: int,
    accent: bool = False,
    highlight: bool = False,
) -> Image.Image:
    image = Image.new("RGB", (width, height), color=BACKGROUND)
    draw = ImageDraw.Draw(image)

    panel_color = PANEL if not highlight else ACCENT
    x1, y1 = _scale_xy(width, height, 80, 80)
    x2, y2 = _scale_xy(width, height, DESIGN_W - 80, DESIGN_H - 80)
    radius = max(12, int(40 * width / DESIGN_W))
    draw.rounded_rectangle((x1, y1, x2, y2), radius=radius, fill=panel_color)

    title_color = ACCENT if accent and not highlight else TEXT_COLOR if not highlight else WHITE
    body_color = TEXT_COLOR if not highlight else WHITE

    fs_title = max(26, int(40 * width / DESIGN_W))
    fs_body = max(22, int(32 * width / DESIGN_W))
    font_title = _truetype_font(fs_title)
    font_body = _truetype_font(fs_body)

    tw = max(18, int(28 * width / DESIGN_W))
    bw = max(32, int(48 * width / DESIGN_W))
    title_wrapped = "\n".join(textwrap.wrap(title, width=tw))
    body_wrapped = "\n".join(textwrap.wrap(body, width=bw))

    tx, ty = _scale_xy(width, height, 140, 140)
    bx, by = _scale_xy(width, height, 140, 260)
    draw.text((tx, ty), title_wrapped, fill=title_color, font=font_title, spacing=6)
    draw.text((bx, by), body_wrapped, fill=body_color, font=font_body, spacing=6)

    fx1, fy1 = _scale_xy(width, height, 140, DESIGN_H - 160)
    fx2, fy2 = _scale_xy(width, height, DESIGN_W - 140, DESIGN_H - 140)
    draw.rectangle((fx1, fy1, fx2, fy2), fill=SUBACCENT if highlight else ACCENT)
    ox, oy = _scale_xy(width, height, 160, DESIGN_H - 158)
    draw.text(
        (ox, oy),
        "ZEUS IA • Generado automáticamente por PERSEO",
        fill=WHITE,
        font=font_body,
    )

    return image


def _ffmpeg_preset() -> str:
    from app.core.config import settings

    p = str(getattr(settings, "PERSEO_FFMPEG_PRESET", "veryfast") or "veryfast").strip()
    allowed = (
        "ultrafast",
        "superfast",
        "veryfast",
        "faster",
        "fast",
        "medium",
        "slow",
        "slower",
        "veryslow",
    )
    return p if p in allowed else "veryfast"


def _write_mp4(
    frames: List[Image.Image], output_path: Path, fps: float, crf: int
) -> bool:
    """
    Genera un MP4 a partir de frames PIL usando MoviePy.
    Usa el binario FFmpeg de imageio-ffmpeg si está disponible.
    """
    try:
        import numpy as np  # type: ignore
        # MoviePy 2.2.1 usa una estructura diferente
        try:
            from moviepy.editor import ImageSequenceClip  # type: ignore
        except ImportError:
            from moviepy.video.io.ImageSequenceClip import ImageSequenceClip  # type: ignore
    except ImportError as exc:
        logger.warning("MoviePy/Numpy no disponibles para generar MP4: %s", exc)
        logger.info("Instala con: pip install moviepy numpy")
        return False

    try:
        # Usar FFmpeg de imageio-ffmpeg (incluido con moviepy)
        import imageio_ffmpeg  # pyright: ignore[reportMissingImports]
        import os
        ffmpeg_binary = imageio_ffmpeg.get_ffmpeg_exe()
        logger.info(f"Usando FFmpeg de imageio-ffmpeg: {ffmpeg_binary}")
        # Configurar MoviePy para usar este binario
        os.environ['IMAGEIO_FFMPEG_EXE'] = ffmpeg_binary
    except Exception as ffmpeg_exc:
        logger.warning(f"No se pudo usar FFmpeg de imageio-ffmpeg: {ffmpeg_exc}")
        logger.warning("Se usará GIF como fallback.")
        return False
    
    try:
        # Convertir frames PIL a arrays numpy
        frame_arrays = []
        for frame in frames:
            # Convertir PIL Image a RGB si no lo es ya
            if frame.mode != 'RGB':
                frame = frame.convert('RGB')
            frame_arrays.append(np.array(frame))
        
        if not frame_arrays:
            logger.error("No hay frames para convertir a MP4")
            return False
        
        # Crear clip desde los frames
        clip = ImageSequenceClip(frame_arrays, fps=float(fps))
        preset = _ffmpeg_preset()

        # Escribir el archivo MP4
        clip.write_videofile(
            str(output_path),
            codec="libx264",
            audio=False,
            fps=float(fps),
            logger=None,
            preset=preset,
            ffmpeg_params=[
                "-crf",
                str(int(crf)),
                "-pix_fmt",
                "yuv420p",
            ],
        )
        clip.close()
        
        # Verificar que el archivo se creó correctamente
        if output_path.exists() and output_path.stat().st_size > 0:
            logger.info(f"✅ MP4 generado exitosamente: {output_path} ({output_path.stat().st_size} bytes)")
            return True
        else:
            logger.error(f"El archivo MP4 se creó pero está vacío o no existe: {output_path}")
            return False
            
    except FileNotFoundError as exc:
        logger.error(f"FFmpeg no encontrado en el sistema. Error: {exc}")
        logger.info("Instala FFmpeg desde https://ffmpeg.org/download.html")
        logger.info("O en Windows: choco install ffmpeg")
        logger.info("O en Linux: sudo apt-get install ffmpeg")
        return False
    except Exception as exc:
        logger.error(f"Fallo generando MP4 con MoviePy: {exc}", exc_info=True)
        try:
            if output_path.exists():
                output_path.unlink()
        except Exception:
            pass
        return False


def _write_gif(
    frames: List[Image.Image], output_path: Path, frame_duration_ms: int = 1000
) -> bool:
    try:
        frames[0].save(
            output_path,
            save_all=True,
            append_images=frames[1:],
            duration=frame_duration_ms,
            loop=0,
            optimize=True,
        )
        return True
    except Exception as exc:  # pragma: no cover
        logger.warning("Fallo generando GIF de fallback: %s", exc)
        try:
            if output_path.exists():
                output_path.unlink()
        except Exception:  # pragma: no cover
            pass
        return False

