"""JUSTICIA contract generator — real templates stored in legal_documents."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.legal_document import LegalDocument
from app.models.user import User

CONTRACT_TEMPLATES: Dict[str, str] = {
    "servicios": """# CONTRATO DE PRESTACIÓN DE SERVICIOS

**Partes:** {parties}

**Alcance:** {scope}

## Cláusulas
1. **Objeto** — El prestador ejecutará {scope} conforme al alcance acordado.
2. **Precio y pagos** — Calendario de pagos según anexo económico.
3. **Confidencialidad y RGPD** — Tratamiento de datos conforme al Reglamento (UE) 2016/679.
4. **Propiedad intelectual** — Salvo pacto expreso, las entregas licencian uso al cliente.
5. **Limitación de responsabilidad** — Capada al importe facturado en los 12 meses anteriores.
6. **Jurisdicción** — Tribunales del domicilio del cliente salvo pacto en contrario.

**Versión:** {version}
**Generado por:** JUSTICIA / ZEUS-IA
""",
    "media_buying": """# CONTRATO DE MEDIA BUYING

**Partes:** {parties}
**Alcance:** Campañas publicitarias — {scope}

## Cláusulas específicas
- Propiedad de creatividades y datos de campaña.
- Cumplimiento LSSI y políticas Meta/Google/TikTok.
- Transparencia de fees y rebates.

**Versión:** {version}
""",
}


def generate_contract(
    db: Session,
    user: User,
    *,
    parties: List[str],
    scope: str = "servicios",
    media_buying: bool = False,
    company_id: Optional[int] = None,
) -> Dict[str, Any]:
    template_key = "media_buying" if media_buying else "servicios"
    template = CONTRACT_TEMPLATES.get(template_key, CONTRACT_TEMPLATES["servicios"])
    parties_str = " · ".join(parties) if parties else "Parte A / Parte B (completar)"

    existing = (
        db.query(LegalDocument)
        .filter(
            LegalDocument.user_id == user.id,
            LegalDocument.doc_type == "contract",
            LegalDocument.status == "draft",
        )
        .order_by(LegalDocument.version.desc())
        .first()
    )
    version = (existing.version + 1) if existing else 1
    content = template.format(parties=parties_str, scope=scope, version=version)

    row = LegalDocument(
        user_id=user.id,
        company_id=company_id,
        doc_type="contract",
        content=content,
        status="draft",
        owner_agent="JUSTICIA",
        version=version,
        parent_id=existing.id if existing else None,
    )
    db.add(row)
    db.flush()

    return {
        "document_id": row.public_id,
        "db_id": row.id,
        "version": version,
        "status": row.status,
        "content_preview": content[:500],
        "delivery_format": "markdown",
        "real_execution": True,
        "stored_in_db": True,
    }
