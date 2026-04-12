"""
ROCE — motor FFmpeg para edición básica de vídeo.
Todas las rutas quedan bajo STATIC_DIR/uploads; nunca se aceptan rutas arbitrarias.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_DEFAULT_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def ffmpeg_binary() -> str:
    return (os.getenv("FFMPEG_PATH") or "ffmpeg").strip() or "ffmpeg"


def uploads_root() -> Path:
    from app.core.config import settings

    return (Path(settings.STATIC_DIR) / "uploads").resolve()


def resolve_safe_under_uploads(relative: str) -> Path:
    """
    relative: p.ej. "videos/u1_xxx.mp4" (sin prefijo uploads/)
    """
    rel = (relative or "").strip().lstrip("/").replace("\\", "/")
    if not rel or ".." in rel or rel.startswith("/"):
        raise ValueError("ruta_invalida")
    allowed_prefixes = ("videos/", "media/", "video_roce/", "roce_audio/")
    if not any(rel.startswith(p) for p in allowed_prefixes):
        raise ValueError("prefijo_no_permitido")
    root = uploads_root()
    p = (root / rel).resolve()
    p.relative_to(root)
    return p


def run_ffmpeg(args: List[str], *, timeout_sec: float, cwd: Optional[Path] = None) -> Tuple[int, str, str]:
    """Ejecuta ffmpeg; nunca lanza por timeout (devuelve código != 0 vía return)."""
    bin_ff = ffmpeg_binary()
    full = [bin_ff, "-hide_banner", "-loglevel", "error", *args]
    try:
        proc = subprocess.run(
            full,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            cwd=str(cwd) if cwd else None,
            check=False,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except subprocess.TimeoutExpired:
        logger.warning("ffmpeg timeout %.1fs args=%s", timeout_sec, args[:12])
        return 124, "", "timeout"
    except FileNotFoundError:
        logger.error("ffmpeg no encontrado: %s", bin_ff)
        return 127, "", "ffmpeg_not_found"
    except Exception as e:
        logger.exception("ffmpeg exec error")
        return 1, "", str(e)


def probe_duration(path: Path) -> Optional[float]:
    """Duración en segundos (ffprobe)."""
    ffprobe = (os.getenv("FFPROBE_PATH") or "ffprobe").strip() or "ffprobe"
    try:
        r = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if r.returncode != 0:
            return None
        return float((r.stdout or "").strip())
    except Exception:
        return None


def font_path() -> str:
    fp = (os.getenv("ROCE_VIDEO_FONT") or _DEFAULT_FONT).strip()
    if Path(fp).is_file():
        return fp
    for alt in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ):
        if Path(alt).is_file():
            return alt
    return fp


def op_trim(input_path: Path, output_path: Path, start_time: float, duration: float, timeout_sec: float) -> bool:
    st = max(0.0, float(start_time))
    dur = max(0.1, float(duration))
    args = [
        "-y",
        "-ss",
        f"{st:.3f}",
        "-i",
        str(input_path),
        "-t",
        f"{dur:.3f}",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "26",
        "-pix_fmt",
        "yuv420p",
        "-an",
        str(output_path),
    ]
    code, _, err = run_ffmpeg(args, timeout_sec=timeout_sec)
    if code != 0:
        logger.warning("trim falló code=%s err=%s", code, err[:500])
    return code == 0 and output_path.is_file() and output_path.stat().st_size > 0


def op_convert(input_path: Path, output_path: Path, fmt: str, timeout_sec: float) -> bool:
    fmt = (fmt or "mp4").lower()
    if fmt != "mp4":
        fmt = "mp4"
    args = [
        "-y",
        "-i",
        str(input_path),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "26",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    code, _, err = run_ffmpeg(args, timeout_sec=timeout_sec)
    if code != 0:
        logger.warning("convert falló code=%s err=%s", code, err[:500])
    return code == 0 and output_path.is_file() and output_path.stat().st_size > 0


def op_drawtext(
    input_path: Path,
    output_path: Path,
    text: str,
    position: str,
    font_size: int,
    timeout_sec: float,
) -> bool:
    text = (text or "").strip()[:200]
    if not text:
        shutil.copy2(input_path, output_path)
        return True
    pos = (position or "bottom").lower()
    if pos == "top":
        y_expr = "20"
    elif pos == "center":
        y_expr = "(h-text_h)/2"
    else:
        y_expr = "h-text_h-24"
    fs = max(12, min(int(font_size or 24), 72))
    font = font_path()
    # textfile evita problemas de escape en drawtext
    tmpd = Path(tempfile.mkdtemp(prefix="roce_txt_"))
    try:
        tf = tmpd / "caption.txt"
        tf.write_text(text, encoding="utf-8")
        vf = (
            f"drawtext=fontfile={font}:textfile={str(tf).replace(chr(92), '/')}:"
            f"fontsize={fs}:fontcolor=white:borderw=2:bordercolor=black:"
            f"x=(w-text_w)/2:y={y_expr}"
        )
        args = [
            "-y",
            "-i",
            str(input_path),
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "26",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(output_path),
        ]
        code, _, err = run_ffmpeg(args, timeout_sec=timeout_sec)
        if code != 0:
            logger.warning("drawtext falló code=%s err=%s", code, err[:500])
        return code == 0 and output_path.is_file() and output_path.stat().st_size > 0
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)


def op_add_music(
    video_path: Path,
    audio_path: Path,
    output_path: Path,
    timeout_sec: float,
) -> bool:
    args = [
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-shortest",
        str(output_path),
    ]
    code, _, err = run_ffmpeg(args, timeout_sec=timeout_sec)
    if code != 0:
        logger.warning("mux audio falló code=%s err=%s", code, err[:500])
    return code == 0 and output_path.is_file() and output_path.stat().st_size > 0


def op_concat_two(a: Path, b: Path, output_path: Path, timeout_sec: float) -> bool:
    """Concatena dos vídeos (re-encode a H.264 para compatibilidad)."""
    tmpd = Path(tempfile.mkdtemp(prefix="roce_cat_"))
    try:
        lst = tmpd / "list.txt"
        lst.write_text(f"file '{a.as_posix()}'\nfile '{b.as_posix()}'\n", encoding="utf-8")
        args = [
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(lst),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "26",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
        code, _, err = run_ffmpeg(args, timeout_sec=timeout_sec, cwd=tmpd)
        if code != 0:
            logger.warning("concat falló code=%s err=%s", code, err[:500])
        return code == 0 and output_path.is_file() and output_path.stat().st_size > 0
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)


def apply_operations(
    source: Path,
    operations: List[Dict[str, Any]],
    work_dir: Path,
    *,
    budget_sec: float,
) -> Tuple[bool, Path, str]:
    """
    Aplica operaciones en serie. budget_sec: tiempo máximo acumulado para subprocess.
    Devuelve (ok, output_path, error_message).
    """
    t0 = __import__("time").time()
    current = work_dir / "step_0.mp4"
    shutil.copy2(source, current)
    step = 0

    def remaining() -> float:
        return max(5.0, budget_sec - (__import__("time").time() - t0))

    for raw in operations:
        op = str(raw.get("op") or "").lower().strip()
        step += 1
        nxt = work_dir / f"step_{step}.mp4"
        ok = False
        if op == "trim":
            ok = op_trim(
                current,
                nxt,
                float(raw.get("start_time", 0) or 0),
                float(raw.get("duration", 5) or 5),
                min(25.0, remaining()),
            )
        elif op == "text":
            ok = op_drawtext(
                current,
                nxt,
                str(raw.get("text") or ""),
                str(raw.get("position") or "bottom"),
                int(raw.get("font_size") or 24),
                min(25.0, remaining()),
            )
        elif op == "music":
            rel = str(raw.get("audio_file_id") or raw.get("audio_file") or "").strip()
            try:
                ap = resolve_safe_under_uploads(rel)
            except ValueError as e:
                return False, current, str(e)
            ok = op_add_music(current, ap, nxt, min(25.0, remaining()))
        elif op == "convert":
            ok = op_convert(current, nxt, str(raw.get("format") or "mp4"), min(25.0, remaining()))
        elif op == "concat":
            rels = raw.get("source_file_ids") or []
            if not isinstance(rels, list) or len(rels) < 1:
                return False, current, "concat_sin_fuentes"
            try:
                second = resolve_safe_under_uploads(str(rels[0]))
            except ValueError as e:
                return False, current, str(e)
            ok = op_concat_two(current, second, nxt, min(25.0, remaining()))
        else:
            return False, current, f"operacion_desconocida:{op}"

        if not ok:
            return False, current, f"fallo_op:{op}"
        current = nxt

    return True, current, ""
