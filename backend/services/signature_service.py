"""JUSTICIA digital signature — SHA256 + timestamp + signer stored in DB."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.legal_document import LegalDocument
from app.models.user import User


def apply_signature(
    db: Session,
    user: User,
    *,
    document_id: Optional[str] = None,
    document_name: str = "",
    file_hash: str = "",
    signer_label: str = "JUSTICIA",
) -> Dict[str, Any]:
    """Generate SHA256 composite hash and persist on legal_documents row."""
    row: Optional[LegalDocument] = None
    if document_id:
        row = (
            db.query(LegalDocument)
            .filter(LegalDocument.public_id == document_id, LegalDocument.user_id == user.id)
            .first()
        )
        if not row:
            raise HTTPException(status_code=404, detail="Legal document not found")

    name = document_name or (f"doc-{row.public_id}" if row else "documento.pdf")
    digest = file_hash or (row.signature_hash or "")
    ts = datetime.now(timezone.utc).isoformat()
    composite = f"{name}:{digest}:{signer_label}:{user.id}:{ts}"
    signature = hashlib.sha256(composite.encode("utf-8")).hexdigest()

    if row:
        row.signature_hash = signature
        row.signer_id = user.id
        row.signed_at = datetime.now(timezone.utc)
        if row.status == "draft":
            row.status = "approved"
        db.add(row)
        db.flush()
    else:
        row = LegalDocument(
            user_id=user.id,
            doc_type="signed_artifact",
            content=f"Signed: {name}",
            status="approved",
            owner_agent="JUSTICIA",
            signature_hash=signature,
            signer_id=user.id,
            signed_at=datetime.now(timezone.utc),
        )
        db.add(row)
        db.flush()

    result = {
        "document_id": row.public_id,
        "document": name,
        "signature": signature,
        "signed_at": ts,
        "signer_id": user.id,
        "signer": signer_label,
        "real_execution": True,
        "stored_in_db": True,
    }

    try:
        from services.zeus_cross_module_events_v1 import emit_cross_module_event

        emit_cross_module_event(db, user, "document_signed", result)
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("[CROSS_MODULE] document_signed failed: %s", exc)

    return result
