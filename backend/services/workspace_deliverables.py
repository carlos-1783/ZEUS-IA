"""
Entregables de workspace: estructura fija, persistencia en document_approvals, visibles en /documents/pending.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.company import UserCompany
from app.models.document_approval import DocumentApproval
from app.models.user import User

logger = logging.getLogger(__name__)

WORKSPACE_DOCUMENT_TYPES: List[str] = [
    "marketing_campaign",
    "social_media_post",
    "fiscal_document",
    "legal_document",
    "hr_document",
]

AGENT_WORKSPACE_CATEGORY: Dict[str, str] = {
    "PERSEO": "marketing_campaign",
    "RAFAEL": "fiscal_document",
    "JUSTICIA": "legal_document",
    "AFRODITA": "hr_document",
}

DEFAULT_CONTENT_TYPE: Dict[str, str] = {
    "PERSEO": "social_media_post",
    "RAFAEL": "fiscal_document",
    "JUSTICIA": "legal_document",
    "AFRODITA": "hr_document",
}


def _clean_marketing_text(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    # Quitar preámbulos frecuentes de "asistente" que no aportan al copy final.
    drop_prefixes = (
        "lamento la confusión",
        "por supuesto",
        "claro",
        "aquí está un bosquejo",
        "te recomendaría trabajar",
        "como inteligencia artificial",
        "desafortunadamente, como inteligencia artificial",
    )
    lines = [ln.strip() for ln in text.splitlines()]
    kept: List[str] = []
    for ln in lines:
        low = ln.lower()
        if any(low.startswith(p) for p in drop_prefixes):
            continue
        if "no tengo la capacidad de crear vídeos" in low or "no tengo la capacidad de crear videos" in low:
            continue
        if "trabajar con un profesional de la producción de vídeos" in low or "trabajar con un profesional de la producción de videos" in low:
            continue
        kept.append(ln)
    text = "\n".join(kept).strip()
    # Si viene con formato "Título:" / "Descripción:", extraer descripción como cuerpo principal.
    m_title = re.search(r"t[ií]tulo:\s*[\"“]?([^\"\n]+)", text, flags=re.IGNORECASE)
    m_desc = re.search(r"descripci[oó]n:\s*[\"“]?(.+?)(?:\n\n|$)", text, flags=re.IGNORECASE | re.DOTALL)
    if m_desc:
        body = m_desc.group(1).strip().strip('"”')
        return body
    # Fallback: primera parte útil (evitar párrafos de disclaimer largos)
    parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if parts:
        candidate = parts[0]
        # Si viene enumerado (1. Inicio... 2. Medio...), mantener solo texto útil
        candidate = re.sub(r"\b\d+\.\s*", "", candidate).strip()
        return candidate
    return text


def _normalize_perseo_content(raw: str, extra_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    body = _clean_marketing_text(raw)
    title = "Campaña de promoción"
    title_match = re.search(r"t[ií]tulo:\s*[\"“]?([^\"\n]+)", raw or "", flags=re.IGNORECASE)
    if title_match:
        title = title_match.group(1).strip()
    elif body:
        title = body[:80].rstrip(".,;:! ") + ("..." if len(body) > 80 else "")

    content: Dict[str, Any] = {
        "copy": body or (raw or "").strip(),
        "cta": "Reserva ahora",
        "platforms": ["instagram", "facebook"],
        "format": "social_media_post",
    }
    # Derivar mini guion de video si hay estructura por tramos
    segments = re.findall(
        r"(inicio|medio|final)\s*\([^)]*\)\s*:\s*(.+?)(?=(?:\n\s*\d+\.\s*\*\*|$))",
        raw or "",
        flags=re.IGNORECASE | re.DOTALL,
    )
    if segments:
        content["video_script"] = [
            {"segment": s[0].strip().capitalize(), "copy": re.sub(r"\s+", " ", s[1]).strip()}
            for s in segments
        ]
    if extra_context:
        for key in ("image_url", "video_url", "pdf_url", "media_url"):
            v = extra_context.get(key)
            if v:
                content[key] = v
    return {"title": title, "content": content}


def normalize_perseo_chat_message(raw: str) -> str:
    """
    Normaliza el texto de chat de PERSEO para mostrar solo copy útil al usuario final.
    """
    normalized = _normalize_perseo_content(raw or "", extra_context=None)
    copy = str((normalized.get("content") or {}).get("copy") or "").strip()
    cta = str((normalized.get("content") or {}).get("cta") or "").strip()
    if copy and cta:
        return f"{copy}\n\nCTA: {cta}"
    return copy or (raw or "").strip()


def normalize_perseo_workspace_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normaliza payload legado de PERSEO para visualización consistente en workspace.
    No requiere escritura en BD; se puede aplicar al leer.
    """
    out = dict(payload or {})
    content = out.get("content")
    if not isinstance(content, dict):
        content = {"body": str(content or "")}

    raw_text = str(content.get("copy") or content.get("body") or out.get("title") or "")
    normalized = _normalize_perseo_content(raw_text, extra_context=content)
    out["title"] = normalized["title"]
    out["content"] = normalized["content"]
    # No perder metadatos de vídeo generado tras chat (no forman parte del copy normalizado)
    _preserve = (
        "generated_video_url",
        "generated_video_status",
        "generated_video_format",
        "generated_video_asset",
        "generated_video_error",
    )
    for key in _preserve:
        if key in content and content[key] is not None:
            out["content"][key] = content[key]
    return out


def primary_company_id_for_user(db: Session, user: User) -> Optional[int]:
    row = (
        db.query(UserCompany)
        .filter(UserCompany.user_id == user.id)
        .order_by(UserCompany.id.asc())
        .first()
    )
    return int(row.company_id) if row else None


def build_structured_payload(
    *,
    title: str,
    content_type: str,
    content: Any,
    status: str = "draft",
    visible_in_workspace: bool = True,
) -> Dict[str, Any]:
    body: Dict[str, Any]
    if isinstance(content, dict):
        body = content
    else:
        body = {"body": content}
    return {
        "title": title,
        "type": content_type,
        "content": body,
        "status": status,
        "visible_in_workspace": visible_in_workspace,
    }


def persist_workspace_deliverable(
    db: Session,
    *,
    user_id: int,
    company_id: Optional[int],
    agent_name: str,
    workspace_category: str,
    title: str,
    content_type: str,
    content: Any,
    status: str = "draft",
    visible_in_workspace: bool = True,
) -> DocumentApproval:
    agent_name = agent_name.upper().strip()
    payload = build_structured_payload(
        title=title,
        content_type=content_type,
        content=content,
        status=status,
        visible_in_workspace=visible_in_workspace,
    )
    doc = DocumentApproval(
        user_id=user_id,
        company_id=company_id,
        agent_name=agent_name,
        document_type=workspace_category,
        document_payload=payload,
        status=status,
        visible_in_workspace=visible_in_workspace,
        audit_log=[
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": "workspace_deliverable_created",
                "agent": agent_name,
                "workspace_category": workspace_category,
            }
        ],
    )
    try:
        db.add(doc)
        db.commit()
        db.refresh(doc)
        pl = dict(doc.document_payload or {})
        if doc.created_at:
            pl["created_at"] = doc.created_at.isoformat()
        doc.document_payload = pl
        db.add(doc)
        db.commit()
        db.refresh(doc)
    except Exception:
        db.rollback()
        raise
    logger.info(
        "Workspace deliverable persisted id=%s user=%s company=%s agent=%s type=%s",
        doc.id,
        user_id,
        company_id,
        agent_name,
        workspace_category,
    )
    return doc


def persist_agent_chat_deliverable(
    db: Session,
    user: User,
    agent_name: str,
    message: str,
    extra_context: Optional[Dict[str, Any]] = None,
) -> Optional[DocumentApproval]:
    if not message or not str(message).strip():
        return None
    agent_key = agent_name.upper().strip()
    if agent_key not in AGENT_WORKSPACE_CATEGORY:
        return None
    workspace_cat = AGENT_WORKSPACE_CATEGORY[agent_key]
    ctype = DEFAULT_CONTENT_TYPE[agent_key]
    raw = str(message).strip()
    title = raw.split("\n")[0][:200].strip() or f"Entregable {agent_key}"
    cid = primary_company_id_for_user(db, user)
    if agent_key == "PERSEO":
        normalized = _normalize_perseo_content(raw, extra_context=extra_context)
        title = normalized["title"]
        content = normalized["content"]
    else:
        content = {"body": raw, "format": "markdown_or_plain"}
        if extra_context:
            for key in ("image_url", "video_url", "pdf_url", "media_url"):
                v = extra_context.get(key)
                if v:
                    content[key] = v
    return persist_workspace_deliverable(
        db,
        user_id=user.id,
        company_id=cid,
        agent_name=agent_key,
        workspace_category=workspace_cat,
        title=title,
        content_type=ctype,
        content=content,
        status="draft",
        visible_in_workspace=True,
    )
