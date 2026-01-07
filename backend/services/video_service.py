"""
Servicio sencillo de generación de vídeo para entregables de PERSEO.
Intenta producir un MP4 a partir del guion del entregable; si no hay
dependencias disponibles, genera un GIF como fallback para que el cliente
siempre reciba un recurso visual descargable.
"""

from __future__ import annotations

import logging
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image, ImageDraw, ImageFont  # type: ignore

from services.automation.utils import OUTPUT_BASE_DIR, ensure_dir, timestamp

logger = logging.getLogger(__name__)


WIDTH = 1280
HEIGHT = 720
BACKGROUND = (12, 20, 38)
PANEL = (241, 245, 249)
ACCENT = (59, 130, 246)
SUBACCENT = (96, 165, 250)
TEXT_COLOR = (15, 23, 42)
WHITE = (255, 255, 255)


def generate_marketing_video(
    deliverable: Dict[str, Any],
    agent: str,
    prefix: str,
    artifact_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Genera el recurso de vídeo asociado a un entregable.
    Intenta MP4 primero, si falla genera GIF como fallback.
    """
    frames = _build_frames(deliverable)
    if not frames:
        logger.warning("No se generaron frames para el vídeo de PERSEO")
        return {"success": False, "reason": "no_frames"}

    agent_dir = ensure_dir(OUTPUT_BASE_DIR / agent.lower())
    base_name = artifact_id or f"{prefix}_{timestamp()}"
    mp4_path = agent_dir / f"{base_name}.mp4"

    # Intentar generar MP4 primero
    logger.info(f"Intentando generar MP4 para {base_name}...")
    if _write_mp4(frames, mp4_path):
        file_size = mp4_path.stat().st_size if mp4_path.exists() else 0
        logger.info(f"✅ MP4 generado exitosamente: {mp4_path.name} ({file_size} bytes)")
        return _build_video_asset_payload(
            file_path=mp4_path,
            fmt="mp4",
            status="generated",
            frame_count=len(frames),
        )

    # Si falla MP4, generar GIF como fallback
    logger.warning("MP4 falló, generando GIF como fallback...")
    gif_path = agent_dir / f"{base_name}_fallback.gif"
    if _write_gif(frames, gif_path):
        file_size = gif_path.stat().st_size if gif_path.exists() else 0
        logger.info(f"✅ GIF fallback generado: {gif_path.name} ({file_size} bytes)")
        payload = _build_video_asset_payload(
            file_path=gif_path,
            fmt="gif",
            status="fallback_gif",
            frame_count=len(frames),
        )
        payload["note"] = "MP4 no disponible (FFmpeg requerido). Se generó GIF como alternativa."
        return payload

    logger.error("No se pudo generar ni MP4 ni GIF para el entregable PERSEO")
    return {"success": False, "reason": "generation_failed"}


def _build_video_asset_payload(
    file_path: Path,
    fmt: str,
    status: str,
    frame_count: int,
) -> Dict[str, Any]:
    file_size = file_path.stat().st_size if file_path.exists() else 0
    try:
        relative_path = file_path.relative_to(OUTPUT_BASE_DIR).as_posix()
    except ValueError:
        relative_path = file_path.name

    download_path = f"/automation/outputs/{relative_path}".replace("//", "/")

    return {
        "success": True,
        "path": str(file_path.resolve()),
        "relative_path": relative_path,
        "filename": file_path.name,
        "download_path": download_path,
        "format": fmt,
        "status": status,
        "frame_count": frame_count,
        "file_size": file_size,
    }


def _build_frames(deliverable: Dict[str, Any]) -> List[Image.Image]:
    frames: List[Image.Image] = []

    summary = deliverable.get("summary")
    if summary:
        frames.append(_render_slide("Resumen ejecutivo", summary))

    script = deliverable.get("video_script") or {}
    structure = script.get("structure") or []
    for idx, segment in enumerate(structure, start=1):
        title = segment.get("segment") or f"Sección {idx}"
        copy = segment.get("copy") or ""
        frames.append(_render_slide(title, copy, accent=True))

    distribution = deliverable.get("distribution_plan") or {}
    launch_date = distribution.get("launch_date")
    if launch_date:
        frames.append(
            _render_slide(
                "Plan de difusión",
                f"Lanzamiento previsto el {launch_date}. "
                "Canales listos con copy y automatizaciones configuradas.",
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
            )
        )

    cta = "Activa ZEUS IA hoy y deja que PERSEO automatice tu marketing 24/7."
    frames.append(_render_slide("CTA", cta, highlight=True))

    return frames


def _render_slide(title: str, body: str, accent: bool = False, highlight: bool = False) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), color=BACKGROUND)
    draw = ImageDraw.Draw(image)

    panel_color = PANEL if not highlight else ACCENT
    draw.rounded_rectangle(
        (80, 80, WIDTH - 80, HEIGHT - 80), radius=40, fill=panel_color
    )

    title_color = ACCENT if accent and not highlight else TEXT_COLOR if not highlight else WHITE
    body_color = TEXT_COLOR if not highlight else WHITE

    font_title = ImageFont.load_default()
    font_body = ImageFont.load_default()

    title_wrapped = "\n".join(textwrap.wrap(title, width=28))
    body_wrapped = "\n".join(textwrap.wrap(body, width=48))

    draw.text((140, 140), title_wrapped, fill=title_color, font=font_title, spacing=6)
    draw.text((140, 260), body_wrapped, fill=body_color, font=font_body, spacing=6)

    draw.rectangle((140, HEIGHT - 160, WIDTH - 140, HEIGHT - 140), fill=SUBACCENT if highlight else ACCENT)
    draw.text(
        (160, HEIGHT - 158),
        "ZEUS IA • Generado automáticamente por PERSEO",
        fill=WHITE,
        font=font_body,
    )

    return image


def _write_mp4(frames: List[Image.Image], output_path: Path, fps: int = 2) -> bool:
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
        clip = ImageSequenceClip(frame_arrays, fps=fps)
        
        # Escribir el archivo MP4
        clip.write_videofile(
            str(output_path),
            codec="libx264",
            audio=False,
            fps=fps,
            logger=None,
            preset='medium',  # Balance entre calidad y velocidad
            bitrate='1000k',  # Bitrate razonable para slides
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


def _write_gif(frames: List[Image.Image], output_path: Path, duration: int = 1200) -> bool:
    try:
        frames[0].save(
            output_path,
            save_all=True,
            append_images=frames[1:],
            duration=duration,
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

