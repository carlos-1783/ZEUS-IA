"""JUSTICIA: «revisa mis contratos» con los contratos reales de la empresa (`legal_documents`).

Cuenta los contratos de la empresa por estado y lista los ultimos: los borradores son los que
requieren revision (un sello de integridad/hash NO es firma ni aprobacion, Fase 2). No analiza el texto con un modelo ni da asesoria: es el estado real.
Solo filas con `company_id` de la empresa (las legado sin empresa no se atribuyen a nadie).
"""

from __future__ import annotations

from typing import Any, Dict

from sqlalchemy import func
from sqlalchemy.orm import Session

CONTRACT_DOC_TYPES = ("contract", "contrato")


def contracts_status(db: Session, company_id: int, *, latest: int = 5) -> Dict[str, Any]:
    from app.models.legal_document import LegalDocument

    base = db.query(LegalDocument).filter(
        LegalDocument.company_id == company_id, LegalDocument.doc_type.in_(CONTRACT_DOC_TYPES)
    )
    by_status = {
        str(st or "desconocido"): int(n)
        for st, n in base.with_entities(LegalDocument.status, func.count(LegalDocument.id))
        .group_by(LegalDocument.status)
        .all()
    }
    # `signed_at`/`signature_hash` solo guardan el sello de integridad (hash): no es una firma
    # electronica eIDAS ni aprueba el contrato, asi que un borrador sellado sigue pendiente.
    drafts = base.filter(LegalDocument.status == "draft").count()
    sealed = base.filter(LegalDocument.signed_at.isnot(None)).count()
    rows = base.order_by(LegalDocument.updated_at.desc(), LegalDocument.id.desc()).limit(latest).all()
    return {
        "total": sum(by_status.values()),
        "by_status": by_status,
        "pending_review": int(drafts),
        "integrity_sealed": int(sealed),
        "latest": [
            {
                "document_id": r.public_id,
                "version": r.version,
                "status": r.status,
                "integrity_sealed": r.signed_at is not None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ],
        "source": "legal_documents",
    }
