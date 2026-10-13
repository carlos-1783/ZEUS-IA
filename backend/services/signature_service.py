"""JUSTICIA — sello de integridad (hash SHA-256 + fecha + usuario) guardado en BD.

Fase 2 (honestidad legal): antes se llamaba "firma digital" y dejaba el documento en
status="approved". Un SHA-256 calculado en servidor NO es una firma electronica en el sentido
del Reglamento eIDAS (UE 910/2014): no identifica al firmante con un certificado cualificado
ni garantiza el control exclusivo de la clave. Por eso:

- Se llama "sello de integridad (hash)" y cada respuesta lleva `legal_notice`.
- NO cambia el estado de un documento existente (un borrador sigue siendo borrador y sigue
  pendiente de aprobacion humana). Solo guarda el hash, quien lo sello y cuando.
- Un sello sin documento previo crea un `legal_documents` con doc_type="integrity_seal" y
  status="integrity_sealed" (nunca "approved").
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.legal_document import LegalDocument
from app.models.user import User

logger = logging.getLogger(__name__)

SEAL_KIND = "integrity_seal"
SEAL_STATUS = "integrity_sealed"
SEAL_LABEL = "Sello de integridad (hash)"
LEGAL_NOTICE = (
    "Sello de integridad (hash SHA-256): prueba que el contenido no ha cambiado desde este "
    "momento. No equivale a una firma electrónica eIDAS ni aprueba el documento."
)


def apply_signature(
    db: Session,
    user: User,
    *,
    document_id: Optional[str] = None,
    document_name: str = "",
    file_hash: str = "",
    signer_label: str = "JUSTICIA",
) -> Dict[str, Any]:
    """Calcula el sello de integridad (SHA-256 compuesto) y lo guarda en legal_documents.

    Nombre historico mantenido por compatibilidad de llamadas; no es una firma electronica.
    """
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
    now = datetime.now(timezone.utc)
    ts = now.isoformat()
    composite = f"{name}:{digest}:{signer_label}:{user.id}:{ts}"
    seal = hashlib.sha256(composite.encode("utf-8")).hexdigest()

    if row:
        # El estado del documento NO cambia: sellar no es aprobar.
        row.signature_hash = seal
        row.signer_id = user.id
        row.signed_at = now
        db.add(row)
        db.flush()
    else:
        import services.crm_office_service as crm_svc

        row = LegalDocument(
            user_id=user.id,
            company_id=crm_svc.primary_company_id(db, user),
            doc_type=SEAL_KIND,
            content=f"{SEAL_LABEL}: {name}",
            status=SEAL_STATUS,
            owner_agent="JUSTICIA",
            signature_hash=seal,
            signer_id=user.id,
            signed_at=now,
        )
        db.add(row)
        db.flush()

    logger.info(
        "JUSTICIA sello de integridad doc=%s user=%s status=%s", row.public_id, user.id, row.status
    )
    return {
        "kind": SEAL_KIND,
        "label": SEAL_LABEL,
        "document_id": row.public_id,
        "document": name,
        "document_status": row.status,
        "integrity_hash": seal,
        "sealed_at": ts,
        "sealed_by_user_id": user.id,
        "seal_label": signer_label,
        "is_electronic_signature": False,
        "approved": False,
        "legal_notice": LEGAL_NOTICE,
        "real_execution": True,
        "stored_in_db": True,
    }
