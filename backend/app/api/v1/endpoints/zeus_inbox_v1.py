"""ZEUS recepcionista: entrada unica por foto/PDF (estilo WhatsApp).

POST /api/v1/zeus/inbox                 multipart: file (imagen/PDF) + note (texto opcional)
GET  /api/v1/zeus/inbox                 bandeja de la empresa del usuario
GET  /api/v1/zeus/inbox/{item_id}       detalle de una entrada (solo de su empresa)
POST /api/v1/zeus/inbox/{item_id}/classify  reintenta la clasificacion de una entrada pendiente
POST /api/v1/zeus/inbox/{item_id}/review    cierra la revision humana: revisado | descartado

Flujo: THALOS (guard por ruta) -> empresa del usuario resuelta en servidor -> validacion real
del fichero (tamano, tipo por contenido) -> R2 (stored_files, categoria "inbox") -> modelo de
vision (OpenAI) -> validacion de coherencia -> revision pendiente asignada al agente
responsable (document_approvals, pending_review) -> AgentActivity de ZEUS y del agente.

Decisiones honestas:
- Sin R2 configurado: 503 y NO se guarda ni se clasifica nada (no hay disco local de respaldo:
  en Railway se perderia en el siguiente deploy y no se puede pedir revision sobre un original
  que no existe). Queda un AgentActivity de ZEUS en estado failed.
- Sin OPENAI_API_KEY: el documento SI queda guardado (R2 + bandeja) en estado
  pendiente_clasificacion y se responde 503 con el motivo y la entrada; ningun campo inventado.
- Nada se contabiliza, ni se registra como factura, ni se envia a AEAT/terceros.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.agent_activity import AgentActivity
from app.models.document_approval import DocumentApproval
from app.models.stored_file import StoredFile
from app.models.user import User
from app.models.zeus_inbox_item import (
    STATUS_CLASSIFIED,
    STATUS_PENDING_CLASSIFICATION,
    ZeusInboxItem,
)
from services import object_storage
from services import zeus_inbox_service as inbox
from services.thalos_request_guard_v1 import thalos_request_guard
from services.upload_intake import (
    read_limited,
    resolve_company_for_upload,
    resolve_content_type,
    storage_http_error,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/zeus/inbox", tags=["zeus-inbox"])

MAX_BYTES = 15 * 1024 * 1024  # 15 MB (por debajo del limite del modelo de vision)
MAX_NOTE_CHARS = 2000
ALLOWED_CONTENT_TYPES = frozenset({"image/jpeg", "image/png", "image/webp", "application/pdf"})
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

REVIEW_NOTICE = (
    "Documento leido por IA y pendiente de revision humana. ZEUS no lo ha contabilizado, "
    "no lo ha registrado como factura y no lo ha enviado a nadie."
)
CLOSED_REVIEW_NOTICE = (
    "Revision humana cerrada. ZEUS no lo ha contabilizado, no lo ha registrado como factura "
    "y no lo ha enviado a nadie."
)


# ------------------------------------------------------------------ utilidades


def _log(
    db: Session,
    *,
    company_id: int,
    user: User,
    agent: str,
    action_type: str,
    description: str,
    details: Dict[str, Any],
    status: str = "completed",
) -> None:
    db.add(
        AgentActivity(
            company_id=company_id,
            agent_name=agent,
            action_type=action_type,
            action_description=description,
            details=details,
            status=status,
            user_email=getattr(user, "email", None),
            priority="normal",
            visible_to_client=True,
            completed_at=datetime.now(timezone.utc) if status == "completed" else None,
        )
    )


def _loads(raw: Optional[str], default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except ValueError:
        return default


def serialize_item(item: ZeusInboxItem, approval: Optional[DocumentApproval] = None) -> Dict[str, Any]:
    extracted = _loads(item.extracted_json, {})
    validation = _loads(item.validation_json, None)
    return {
        "id": item.id,
        "status": item.status,
        "doc_type": item.doc_type,
        "assigned_agent": item.assigned_agent,
        "confidence": item.confidence,
        "model_confidence": extracted.get("model_confidence"),
        "fields": extracted.get("fields"),
        "observations": extracted.get("observations"),
        "validation": validation,
        "note": item.note,
        "classification_error": item.classification_error,
        "model": item.model,
        "file": {
            "file_id": item.stored_file_id,
            "url": f"/api/v1/files/{item.stored_file_id}" if item.stored_file_id else None,
            "filename": item.original_filename,
            "content_type": item.content_type,
            "size_bytes": item.size_bytes,
        },
        "review": (
            {
                "document_approval_id": item.document_approval_id,
                "agent": item.assigned_agent,
                "status": approval.status if approval is not None else None,
            }
            if item.document_approval_id
            else None
        ),
        "notice": (
            CLOSED_REVIEW_NOTICE
            if approval is not None and approval.status in ("reviewed", "discarded")
            else REVIEW_NOTICE
        ),
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "classified_at": item.classified_at.isoformat() if item.classified_at else None,
    }


def _company_id(db: Session, user: User) -> int:
    # Empresa resuelta SIEMPRE en servidor (nunca un company_id enviado por el cliente).
    return resolve_company_for_upload(db, user)


def _get_item(db: Session, company_id: int, item_id: int) -> ZeusInboxItem:
    item = (
        db.query(ZeusInboxItem)
        .filter(ZeusInboxItem.id == item_id, ZeusInboxItem.company_id == company_id)
        .first()
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado en tu bandeja.")
    return item


def _approval_for(db: Session, item: ZeusInboxItem) -> Optional[DocumentApproval]:
    if not item.document_approval_id:
        return None
    return (
        db.query(DocumentApproval)
        .filter(
            DocumentApproval.id == item.document_approval_id,
            DocumentApproval.company_id == item.company_id,
        )
        .first()
    )


def _classify_and_route(
    db: Session, user: User, item: ZeusInboxItem, data: bytes
) -> JSONResponse:
    """Clasifica, valida y asigna. Devuelve la respuesta HTTP final (201/200, 503 o 502)."""
    company_id = item.company_id
    try:
        result = inbox.classify_document(data, item.content_type, item.original_filename, item.note)
    except inbox.ClassificationUnavailable as exc:
        item.classification_error = str(exc)
        _log(
            db, company_id=company_id, user=user, agent="ZEUS",
            action_type="inbox_classification_unavailable",
            description=f"Documento #{item.id} guardado sin clasificar: falta OPENAI_API_KEY.",
            details={"inbox_item_id": item.id, "stored_file_id": item.stored_file_id},
            status="failed",
        )
        db.commit()
        db.refresh(item)
        return JSONResponse(
            status_code=503,
            content={"success": False, "detail": str(exc), "item": serialize_item(item)},
        )
    except inbox.ClassificationFailed as exc:
        item.classification_error = str(exc)
        _log(
            db, company_id=company_id, user=user, agent="ZEUS",
            action_type="inbox_classification_failed",
            description=f"Fallo clasificando el documento #{item.id}; queda pendiente.",
            details={"inbox_item_id": item.id, "error": str(exc)},
            status="failed",
        )
        db.commit()
        db.refresh(item)
        return JSONResponse(
            status_code=502,
            content={
                "success": False,
                "detail": "No se pudo clasificar el documento ahora; queda guardado como "
                "pendiente. Reintenta mas tarde.",
                "item": serialize_item(item),
            },
        )

    agent = result["assigned_agent"]
    extracted = {
        "fields": result["fields"],
        "model_confidence": result["model_confidence"],
        "observations": result["observations"],
    }
    now = datetime.now(timezone.utc)
    approval = DocumentApproval(
        user_id=user.id,
        company_id=company_id,
        agent_name=agent,
        document_type=f"zeus_inbox_{result['doc_type']}",
        status="pending_review",
        visible_in_workspace=True,
        mime_type=item.content_type,
        file_size_bytes=item.size_bytes,
    )
    approval.document_payload = {
        "source": "zeus_inbox",
        "inbox_item_id": item.id,
        "stored_file_id": item.stored_file_id,
        "file_url": f"/api/v1/files/{item.stored_file_id}",
        "doc_type": result["doc_type"],
        "fields": result["fields"],
        "validation": result["validation"],
        "confidence": result["confidence"],
        "model_confidence": result["model_confidence"],
        "observations": result["observations"],
        "note": item.note,
        "notice": REVIEW_NOTICE,
    }
    approval.audit_log = [
        {
            "at": now.isoformat(),
            "action": "assigned_by_zeus_inbox",
            "agent": agent,
            "user_id": user.id,
            "confidence": result["confidence"],
        }
    ]
    db.add(approval)
    db.flush()

    item.status = STATUS_CLASSIFIED
    item.doc_type = result["doc_type"]
    item.confidence = result["confidence"]
    item.extracted_json = inbox.dumps(extracted)
    item.validation_json = inbox.dumps(result["validation"])
    item.classification_error = None
    item.model = (result.get("model") or "")[:64] or None
    item.assigned_agent = agent
    item.document_approval_id = approval.id
    item.classified_at = now

    _log(
        db, company_id=company_id, user=user, agent="ZEUS",
        action_type="inbox_classified",
        description=f"Documento #{item.id} clasificado como {result['doc_type']} "
        f"(confianza {result['confidence']}) y asignado a {agent}.",
        details={
            "inbox_item_id": item.id,
            "doc_type": result["doc_type"],
            "confidence": result["confidence"],
            "assigned_agent": agent,
            "issues": result["validation"]["issues"],
        },
    )
    _log(
        db, company_id=company_id, user=user, agent=agent,
        action_type="inbox_document_assigned",
        description=f"Revision pendiente: {result['doc_type']} recibido por ZEUS (documento #{item.id}).",
        details={
            "inbox_item_id": item.id,
            "document_approval_id": approval.id,
            "doc_type": result["doc_type"],
            "confidence": result["confidence"],
        },
        status="pending",
    )
    db.commit()
    db.refresh(item)
    db.refresh(approval)
    logger.info(
        "ZEUS inbox item=%s company=%s tipo=%s agente=%s confianza=%s",
        item.id, company_id, item.doc_type, agent, item.confidence,
    )
    return JSONResponse(
        status_code=201, content={"success": True, "item": serialize_item(item, approval)}
    )


# ------------------------------------------------------------------ endpoints


@router.post("")
async def receive_document(
    file: UploadFile = File(...),
    note: Optional[str] = Form(None),
    current_user: User = Depends(thalos_request_guard),
    db: Session = Depends(get_db),
):
    company_id = _company_id(db, current_user)

    note = (note or "").strip() or None
    if note is not None:
        if len(note) > MAX_NOTE_CHARS:
            raise HTTPException(status_code=413, detail=f"La nota supera {MAX_NOTE_CHARS} caracteres.")
        if _CONTROL_RE.search(note):
            raise HTTPException(status_code=400, detail="La nota contiene caracteres de control no permitidos.")

    content_type = resolve_content_type(file)
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Tipo de archivo no permitido: {content_type}. Envia una foto JPG/PNG/WEBP o un PDF.",
        )
    data = await read_limited(file, MAX_BYTES)
    try:
        object_storage.verify_content(data, content_type)
    except object_storage.ContentMismatch as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc

    if not object_storage.is_configured():
        _log(
            db, company_id=company_id, user=current_user, agent="ZEUS",
            action_type="inbox_storage_unavailable",
            description="Documento recibido pero NO guardado: almacenamiento externo (R2) no configurado.",
            details={"content_type": content_type, "size_bytes": len(data)},
            status="failed",
        )
        db.commit()
        raise HTTPException(
            status_code=503,
            detail="El almacenamiento de ficheros no esta configurado todavia. No se ha guardado "
            "ni clasificado el documento; contacta con el administrador.",
        )

    filename = file.filename or "documento"
    try:
        stored = object_storage.store_file(
            db,
            company_id=company_id,
            user_id=current_user.id,
            category="inbox",
            filename=filename,
            content_type=content_type,
            data=data,
            agent_name="ZEUS",
        )
    except (object_storage.StorageNotConfigured, object_storage.StorageError) as exc:
        raise storage_http_error(exc) from exc

    item = ZeusInboxItem(
        company_id=company_id,
        user_id=current_user.id,
        stored_file_id=stored.id,
        original_filename=stored.original_filename,
        content_type=stored.content_type,
        size_bytes=stored.size_bytes,
        sha256=stored.sha256,
        note=note,
        status=STATUS_PENDING_CLASSIFICATION,
    )
    db.add(item)
    db.flush()
    _log(
        db, company_id=company_id, user=current_user, agent="ZEUS",
        action_type="inbox_received",
        description=f"Documento #{item.id} recibido ({content_type}, {len(data)} bytes).",
        details={"inbox_item_id": item.id, "stored_file_id": stored.id, "content_type": content_type},
    )
    db.commit()
    db.refresh(item)
    return _classify_and_route(db, current_user, item, data)


@router.get("")
def list_inbox(
    status: Optional[str] = Query(None, pattern=r"^(pendiente_clasificacion|clasificado)$"),
    agent: Optional[str] = Query(None, pattern=r"^(ZEUS|RAFAEL|AFRODITA|JUSTICIA)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    company_id = _company_id(db, current_user)
    q = db.query(ZeusInboxItem).filter(ZeusInboxItem.company_id == company_id)
    if status:
        q = q.filter(ZeusInboxItem.status == status)
    if agent:
        q = q.filter(ZeusInboxItem.assigned_agent == agent)
    total = q.count()
    rows = q.order_by(ZeusInboxItem.id.desc()).offset(offset).limit(limit).all()
    approval_ids = [r.document_approval_id for r in rows if r.document_approval_id]
    approvals = {
        a.id: a
        for a in (
            db.query(DocumentApproval)
            .filter(DocumentApproval.id.in_(approval_ids), DocumentApproval.company_id == company_id)
            .all()
            if approval_ids
            else []
        )
    }
    return {
        "success": True,
        "total": total,
        "items": [serialize_item(r, approvals.get(r.document_approval_id)) for r in rows],
    }


@router.get("/{item_id}")
def get_inbox_item(
    item_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    company_id = _company_id(db, current_user)
    item = _get_item(db, company_id, item_id)
    return {"success": True, "item": serialize_item(item, _approval_for(db, item))}


@router.post("/{item_id}/classify")
def retry_classification(
    item_id: int,
    current_user: User = Depends(thalos_request_guard),
    db: Session = Depends(get_db),
):
    company_id = _company_id(db, current_user)
    item = _get_item(db, company_id, item_id)
    if item.status != STATUS_PENDING_CLASSIFICATION:
        raise HTTPException(status_code=409, detail="El documento ya esta clasificado y asignado.")
    if not inbox.classification_available():
        # Comprobacion previa: no se descarga el fichero de R2 si no se puede clasificar.
        return _classify_and_route(db, current_user, item, b"")
    row = object_storage.get_for_companies(db, item.stored_file_id or "", [company_id])
    if row is None:
        raise HTTPException(status_code=410, detail="El fichero original ya no esta disponible.")
    try:
        data = object_storage.read_bytes(row)
    except (object_storage.StorageNotConfigured, object_storage.StorageError) as exc:
        raise storage_http_error(exc) from exc
    return _classify_and_route(db, current_user, item, data)


# ------------------------------------------------------------------ cierre de la revision

REVIEW_DECISIONS = {"revisado": "reviewed", "descartado": "discarded"}
MAX_REVIEW_NOTE_CHARS = 1000


class InboxReviewBody(BaseModel):
    decision: str = Field(..., pattern=r"^(revisado|descartado)$")
    note: Optional[str] = Field(None, max_length=MAX_REVIEW_NOTE_CHARS)


@router.post("/{item_id}/review")
def review_inbox_item(
    item_id: int,
    body: InboxReviewBody,
    current_user: User = Depends(thalos_request_guard),
    db: Session = Depends(get_db),
):
    """Cierra la revision humana de una entrada clasificada (cualquier miembro de la empresa).

    Solo marca la revision (document_approvals.status = reviewed | discarded + audit_log) y deja
    log real. NO contabiliza, NO registra factura, NO envia nada al asesor ni a terceros.
    """
    company_id = _company_id(db, current_user)
    item = _get_item(db, company_id, item_id)
    note = (body.note or "").strip() or None
    if note is not None and _CONTROL_RE.search(note):
        raise HTTPException(status_code=400, detail="La nota contiene caracteres de control no permitidos.")
    approval = _approval_for(db, item)
    if approval is None:
        raise HTTPException(
            status_code=409,
            detail="El documento aun no esta clasificado: no hay revision pendiente que cerrar.",
        )
    if approval.status != "pending_review":
        raise HTTPException(
            status_code=409,
            detail=f"La revision de este documento ya esta cerrada (estado: {approval.status}).",
        )

    new_status = REVIEW_DECISIONS[body.decision]
    now = datetime.now(timezone.utc)
    approval.status = new_status
    approval.audit_log = approval.audit_log + [
        {
            "at": now.isoformat(),
            "action": f"inbox_review_{new_status}",
            "decision": body.decision,
            "user_id": current_user.id,
            "note": note,
            "side_effects": "ninguno (no contabiliza ni envia)",
        }
    ]
    _log(
        db, company_id=company_id, user=current_user, agent=item.assigned_agent or "ZEUS",
        action_type=f"inbox_review_{new_status}",
        description=f"Documento #{item.id} marcado como {body.decision} por un miembro de la empresa.",
        details={
            "inbox_item_id": item.id,
            "document_approval_id": approval.id,
            "decision": body.decision,
            "note": note,
        },
    )
    db.commit()
    db.refresh(item)
    db.refresh(approval)
    logger.info(
        "ZEUS inbox review item=%s company=%s user=%s decision=%s",
        item.id, company_id, current_user.id, body.decision,
    )
    return {"success": True, "item": serialize_item(item, approval), "decision": body.decision}
