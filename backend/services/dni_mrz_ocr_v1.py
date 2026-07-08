"""Extracción de MRZ desde imagen (OCR) para flujo DNI en producción."""

from __future__ import annotations

import base64
import io
import logging
import re
from typing import List

from fastapi import HTTPException

logger = logging.getLogger(__name__)

MRZ_LINE_RE = re.compile(r"^[A-Z0-9<]{18,}$")


def _decode_image_bytes(image_base64: str) -> bytes:
    raw = (image_base64 or "").strip()
    if not raw:
        raise HTTPException(status_code=422, detail="Imagen vacía.")
    if "," in raw and raw.lower().startswith("data:"):
        raw = raw.split(",", 1)[1]
    try:
        return base64.b64decode(raw, validate=False)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Imagen base64 inválida.") from exc


def _ocr_text_from_image(image_bytes: bytes) -> str:
    try:
        from PIL import Image, ImageEnhance, ImageFilter
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="OCR no disponible (Pillow).") from exc

    try:
        import pytesseract
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="OCR no disponible en el servidor (instalar pytesseract).",
        ) from exc

    img = Image.open(io.BytesIO(image_bytes))
    gray = img.convert("L")
    enhanced = ImageEnhance.Contrast(gray).enhance(2.0)
    sharpened = enhanced.filter(ImageFilter.SHARPEN)
    config = "--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<"
    try:
        return pytesseract.image_to_string(sharpened, config=config)
    except Exception as exc:
        logger.warning("pytesseract failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="No se pudo ejecutar OCR. Verifica que tesseract-ocr esté instalado.",
        ) from exc


def _extract_mrz_lines(text: str) -> List[str]:
    lines: List[str] = []
    for raw_line in (text or "").splitlines():
        line = re.sub(r"[^A-Z0-9<]", "", raw_line.upper())
        if MRZ_LINE_RE.match(line):
            lines.append(line)
    return lines


def extract_mrz_from_image_base64(image_base64: str) -> str:
    """Devuelve MRZ multilínea extraído por OCR."""
    image_bytes = _decode_image_bytes(image_base64)
    ocr_text = _ocr_text_from_image(image_bytes)
    lines = _extract_mrz_lines(ocr_text)
    if len(lines) >= 3:
        return "\n".join(lines[:3])
    if len(lines) == 2 and max(len(lines[0]), len(lines[1])) >= 36:
        return "\n".join(lines)
    if not lines:
        raise HTTPException(
            status_code=422,
            detail="No se detectó MRZ en la imagen. Enfoca el reverso del DNI y vuelve a capturar.",
        )
    raise HTTPException(
        status_code=422,
        detail="MRZ incompleto en la imagen. Asegúrate de capturar las 3 líneas del reverso.",
    )
