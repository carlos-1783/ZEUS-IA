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


def _crop_mrz_zone(img):
  """Recorta la franja inferior donde suele estar el MRZ del DNI."""
  w, h = img.size
  top = int(h * 0.58)
  return img.crop((0, top, w, h))


def _preprocess_for_ocr(img):
    from PIL import ImageEnhance, ImageFilter, ImageOps

    gray = ImageOps.grayscale(img)
    cropped = _crop_mrz_zone(gray)
    scaled = cropped.resize((max(cropped.width * 2, 1), max(cropped.height * 2, 1)))
    enhanced = ImageEnhance.Contrast(scaled).enhance(2.4)
    return enhanced.filter(ImageFilter.SHARPEN)


def _ocr_text_from_image(image_bytes: bytes) -> str:
    try:
        from PIL import Image
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
    prepared = _preprocess_for_ocr(img)
    config = "--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<"
    texts: List[str] = []
    for psm in (6, 7, 11):
        try:
            texts.append(pytesseract.image_to_string(prepared, config=config.replace("6", str(psm))))
        except Exception:
            continue
    try:
        texts.append(pytesseract.image_to_string(_preprocess_for_ocr(img), config=config))
    except Exception as exc:
        logger.warning("pytesseract failed: %s", exc)
        if not texts:
            raise HTTPException(
                status_code=503,
                detail="No se pudo ejecutar OCR. Verifica que tesseract-ocr esté instalado.",
            ) from exc
    return "\n".join(texts)


def _normalize_ocr_line(line: str) -> str:
    cleaned = re.sub(r"[^A-Z0-9<]", "", (line or "").upper())
    if cleaned.startswith("IDESP"):
        cleaned = "I<ESP" + cleaned[5:]
    return cleaned


def _extract_mrz_lines(text: str) -> List[str]:
    lines: List[str] = []
    for raw_line in (text or "").splitlines():
        line = _normalize_ocr_line(raw_line)
        if MRZ_LINE_RE.match(line):
            lines.append(line.ljust(30, "<")[:30])
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
            detail="No se detectó MRZ en la imagen. Acerca el reverso del DNI, con buena luz y sin movimiento.",
        )
    raise HTTPException(
        status_code=422,
        detail="MRZ incompleto en la imagen. Captura solo el reverso con las 3 líneas visibles.",
    )
