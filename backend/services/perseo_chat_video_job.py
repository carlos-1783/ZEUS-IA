"""
Generación de vídeo (slides) tras chat PERSEO con imagen de referencia.
Se ejecuta en BackgroundTasks: actualiza document_payload del workspace.
"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.document_approval import DocumentApproval

logger = logging.getLogger(__name__)


def build_deliverable_from_chat_content(content: Dict[str, Any], title: str) -> Dict[str, Any]:
    """Adapta el content del entregable workspace al formato de generate_marketing_video."""
    structure: List[Dict[str, str]] = []
    vs = content.get("video_script")
    if isinstance(vs, list):
        for item in vs:
            if not isinstance(item, dict):
                continue
            seg = str(item.get("segment") or "Escena").strip() or "Escena"
            copy = str(item.get("copy") or "").strip()[:1200]
            if seg or copy:
                structure.append({"segment": seg, "copy": copy})
    copy_text = str(content.get("copy") or content.get("body") or "").strip()
    if not structure and copy_text:
        chunks = [c.strip() for c in copy_text.split("\n\n") if c.strip()][:8]
        if not chunks:
            chunks = [copy_text[:1200]]
        for i, ch in enumerate(chunks):
            structure.append({"segment": f"Parte {i + 1}", "copy": ch[:950]})
    if not structure:
        structure = [
            {
                "segment": "Campaña",
                "copy": (copy_text or title or "PERSEO")[:900],
            }
        ]
    summary = (copy_text[:600] if copy_text else "") or (title or "Campaña PERSEO")[:600]
    cta = str(content.get("cta") or "Reserva ahora").strip()
    out: Dict[str, Any] = {
        "summary": summary,
        "video_script": {"structure": structure, "goal": "Entregable chat PERSEO"},
        "distribution_plan": {},
        "cta_slide": cta,
    }
    img_ref = str(content.get("image_url") or "").strip()
    if img_ref:
        out["reference_image_url"] = img_ref
    try:
        spf = float(settings.PERSEO_VIDEO_SECONDS_PER_SLIDE)
    except (TypeError, ValueError):
        spf = 5.0
    out["seconds_per_slide"] = max(1.0, min(spf, 120.0))
    return out


def run_perseo_chat_video_generation(doc_id: int, user_id: int) -> None:
    """
    Genera MP4 o GIF desde el copy del documento y lo copia a static/uploads/videos
    con prefijo u{user_id}_ (compatible con /api/v1/upload/file/...).
    """
    db = SessionLocal()
    try:
        doc = (
            db.query(DocumentApproval)
            .filter(DocumentApproval.id == doc_id, DocumentApproval.user_id == user_id)
            .first()
        )
        if not doc:
            logger.warning("perseo_chat_video: documento %s no encontrado o user mismatch", doc_id)
            return

        payload = dict(doc.document_payload or {})
        content = payload.get("content")
        if not isinstance(content, dict):
            logger.warning("perseo_chat_video: sin content en doc %s", doc_id)
            return

        if content.get("generated_video_url"):
            logger.info("perseo_chat_video: doc %s ya tiene vídeo generado", doc_id)
            return

        title = str(payload.get("title") or "Campaña")
        deliverable = build_deliverable_from_chat_content(content, title)

        from services.video_service import generate_marketing_video

        artifact_id = f"chat_{doc_id}_{user_id}"
        video_result = generate_marketing_video(
            deliverable, "PERSEO", f"chatdoc{doc_id}", artifact_id=artifact_id
        )

        if not video_result.get("success"):
            content["generated_video_status"] = "failed"
            content["generated_video_error"] = str(
                video_result.get("reason") or video_result.get("error") or "generation_failed"
            )[:400]
            payload["content"] = content
            doc.document_payload = payload
            db.add(doc)
            db.commit()
            logger.warning("perseo_chat_video: fallo doc=%s %s", doc_id, content["generated_video_error"])
            return

        src = Path(video_result["path"])
        if not src.is_file():
            content["generated_video_status"] = "failed"
            content["generated_video_error"] = "Archivo generado no encontrado en disco"
            payload["content"] = content
            doc.document_payload = payload
            db.add(doc)
            db.commit()
            return

        ext = str(video_result.get("format") or "mp4").lower()
        if ext not in ("mp4", "gif"):
            ext = "mp4"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        fname = f"u{user_id}_{stamp}_doc{doc_id}_perseo.{ext}"
        dest_dir = Path(settings.STATIC_DIR) / "uploads" / "videos"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / fname
        shutil.copy2(src, dest)

        path_url = f"{settings.STATIC_URL.rstrip('/')}/uploads/videos/{fname}"
        if not path_url.startswith("/"):
            path_url = "/" + path_url.lstrip("/")

        content["generated_video_url"] = path_url
        content["generated_video_status"] = "ready"
        content["generated_video_format"] = ext
        content["generated_video_asset"] = {
            "file_size": video_result.get("file_size"),
            "frame_count": video_result.get("frame_count"),
            "status": video_result.get("status"),
        }
        payload["content"] = content
        doc.document_payload = payload

        logs = list(doc.audit_log or [])
        logs.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": "perseo_chat_video_generated",
                "generated_video_url": path_url,
            }
        )
        doc.audit_log = logs
        db.add(doc)
        db.commit()
        logger.info("perseo_chat_video: doc=%s url=%s", doc_id, path_url)
    except Exception as e:
        logger.exception("perseo_chat_video: error doc=%s: %s", doc_id, e)
        try:
            doc = (
                db.query(DocumentApproval)
                .filter(DocumentApproval.id == doc_id, DocumentApproval.user_id == user_id)
                .first()
            )
            if doc:
                payload = dict(doc.document_payload or {})
                c = payload.get("content")
                if isinstance(c, dict):
                    c["generated_video_status"] = "failed"
                    c["generated_video_error"] = str(e)[:400]
                    payload["content"] = c
                    doc.document_payload = payload
                    db.add(doc)
                    db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()


def run_perseo_chat_video_generation_safe(doc_id: int, user_id: int) -> None:
    """
    Wrapper para BackgroundTasks: cualquier excepción queda aislada (no debe matar el worker).
    """
    try:
        run_perseo_chat_video_generation(doc_id, user_id)
    except Exception:
        logger.exception(
            "perseo_chat_video safe wrapper falló doc_id=%s user_id=%s",
            doc_id,
            user_id,
        )
