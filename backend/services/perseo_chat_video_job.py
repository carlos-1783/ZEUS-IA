"""
Generación de vídeo (slides) tras chat PERSEO con imagen de referencia.
Se ejecuta en BackgroundTasks: actualiza document_payload del workspace.

Nota producto: esto es composición tipo presentación (PIL + MoviePy + H.264), no vídeo
generativo I2V como Google Veo 3; ese nivel requiere API externa (Vertex/Veo) y no está en este job.
"""

from __future__ import annotations

import logging
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.document_approval import DocumentApproval

logger = logging.getLogger(__name__)


def build_deliverable_from_chat_content(content: Dict[str, Any], title: str) -> Dict[str, Any]:
    """Adapta el content del entregable workspace al formato de generate_marketing_video."""
    structure: List[Dict[str, str]] = []
    vs = content.get("video_script")
    max_slides = 6
    if isinstance(vs, list):
        for item in vs:
            if len(structure) >= max_slides:
                break
            if not isinstance(item, dict):
                continue
            seg = str(item.get("segment") or "Escena").strip() or "Escena"
            copy = str(item.get("copy") or "").strip()[:1200]
            if seg or copy:
                structure.append({"segment": seg, "copy": copy})
    copy_text = str(content.get("copy") or content.get("body") or "").strip()
    if not structure and copy_text:
        chunks = [c.strip() for c in copy_text.split("\n\n") if c.strip()][:max_slides]
        if not chunks:
            chunks = [copy_text[:1200]]
        for i, ch in enumerate(chunks):
            if len(structure) >= max_slides:
                break
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


def _fail_pending_document(doc_id: int, user_id: int, message: str) -> None:
    """Marca generated_video_status=failed para no dejar el UI en 'pending' eterno."""
    db = SessionLocal()
    try:
        doc = (
            db.query(DocumentApproval)
            .filter(DocumentApproval.id == doc_id, DocumentApproval.user_id == user_id)
            .first()
        )
        if not doc:
            return
        payload = dict(doc.document_payload or {})
        c = payload.get("content")
        if not isinstance(c, dict):
            return
        if c.get("generated_video_status") == "ready" and c.get("generated_video_url"):
            return
        c["generated_video_status"] = "failed"
        c["generated_video_error"] = message[:400]
        payload["content"] = c
        doc.document_payload = payload
        db.add(doc)
        db.commit()
    except Exception:
        logger.exception("perseo_chat_video: no se pudo persistir fallo doc=%s", doc_id)
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


def _generate_with_timeout(
    deliverable: Dict[str, Any],
    doc_id: int,
    user_id: int,
    artifact_id: str,
) -> Dict[str, Any]:
    """Ejecuta generate_marketing_video en un hilo con join(timeout) para no bloquear pending indefinidamente."""
    from services.video_service import generate_marketing_video

    try:
        timeout_sec = float(getattr(settings, "PERSEO_VIDEO_JOB_TIMEOUT_SEC", 240) or 240)
    except (TypeError, ValueError):
        timeout_sec = 240.0
    timeout_sec = max(60.0, min(timeout_sec, 900.0))

    out: Dict[str, Any] = {}
    err: List[BaseException] = []

    def _work() -> None:
        try:
            out["result"] = generate_marketing_video(
                deliverable, "PERSEO", f"chatdoc{doc_id}", artifact_id=artifact_id
            )
        except BaseException as e:
            err.append(e)

    th = threading.Thread(target=_work, name=f"perseo_vid_{doc_id}", daemon=True)
    th.start()
    th.join(timeout=timeout_sec)
    if th.is_alive():
        logger.error(
            "perseo_chat_video: timeout tras %.0fs doc=%s (el hilo sigue en segundo plano hasta terminar)",
            timeout_sec,
            doc_id,
        )
        return {
            "success": False,
            "reason": (
                f"timeout_{int(timeout_sec)}s: la generación tardó demasiado (CPU/RAM). "
                "Reintenta desde el workspace o sube RAM en Railway."
            ),
        }
    if err:
        logger.exception("perseo_chat_video: excepción en generate_marketing_video doc=%s", doc_id)
        return {"success": False, "reason": str(err[0])[:400]}
    return out.get("result") or {"success": False, "reason": "sin_resultado"}


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
            _fail_pending_document(
                doc_id,
                user_id,
                "Entregable sin estructura content válida; no se puede generar vídeo.",
            )
            return

        if content.get("generated_video_url"):
            logger.info("perseo_chat_video: doc %s ya tiene vídeo generado", doc_id)
            return

        title = str(payload.get("title") or "Campaña")
        deliverable = build_deliverable_from_chat_content(content, title)

        artifact_id = f"chat_{doc_id}_{user_id}"
        video_result = _generate_with_timeout(deliverable, doc_id, user_id, artifact_id)

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
    Wrapper para BackgroundTasks: cualquier excepción queda aislada (no debe tumbar el worker).
    """
    try:
        run_perseo_chat_video_generation(doc_id, user_id)
    except Exception:
        logger.exception(
            "perseo_chat_video safe wrapper falló doc_id=%s user_id=%s",
            doc_id,
            user_id,
        )
        _fail_pending_document(
            doc_id,
            user_id,
            "Error interno al generar vídeo (revisa logs del servidor). Reintenta desde el workspace.",
        )


def schedule_retry_from_api(doc_id: int, user_id: int) -> Optional[str]:
    """
    Llamado desde el endpoint HTTP: devuelve None si OK, o mensaje de error corto.
    No ejecuta el vídeo aquí: el caller debe añadir BackgroundTasks(run_perseo_chat_video_generation_safe).
    """
    db = SessionLocal()
    try:
        doc = (
            db.query(DocumentApproval)
            .filter(DocumentApproval.id == doc_id, DocumentApproval.user_id == user_id)
            .first()
        )
        if not doc:
            return "documento_no_encontrado"
        if str(doc.agent_name or "").upper().strip() != "PERSEO":
            return "solo_perseo"
        payload = dict(doc.document_payload or {})
        c = payload.get("content")
        if not isinstance(c, dict):
            return "sin_content"
        if not str(c.get("image_url") or "").strip():
            return "sin_imagen_referencia"
        st = str(c.get("generated_video_status") or "").lower()
        if st == "ready" and str(c.get("generated_video_url") or "").strip():
            return "ya_generado"
        if st == "failed":
            c.pop("generated_video_url", None)
        started_raw = str(c.get("generated_video_started_at") or "").strip()
        if st == "pending" and started_raw:
            try:
                started = datetime.fromisoformat(started_raw.replace("Z", "+00:00"))
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                age = (datetime.now(timezone.utc) - started).total_seconds()
                if age < 45:
                    return "ya_en_cola"
            except Exception:
                pass
        c["generated_video_status"] = "pending"
        c["generated_video_started_at"] = datetime.now(timezone.utc).isoformat()
        c.pop("generated_video_error", None)
        payload["content"] = c
        doc.document_payload = payload
        db.add(doc)
        db.commit()
        return None
    except Exception:
        logger.exception("schedule_retry_from_api doc=%s", doc_id)
        try:
            db.rollback()
        except Exception:
            pass
        return "db_error"
    finally:
        db.close()
