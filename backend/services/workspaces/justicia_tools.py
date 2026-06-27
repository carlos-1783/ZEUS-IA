"""
Herramientas de workspace para JUSTICIA — persistencia real en BD.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def sign_pdf_document(payload: Dict[str, Any], user_id: Optional[int] = None, db=None) -> Dict[str, Any]:
    if db and user_id:
        from app.models.user import User
        from services.signature_service import apply_signature

        user = db.query(User).filter(User.id == user_id).first()
        if user:
            return apply_signature(
                db,
                user,
                document_id=payload.get("document_id"),
                document_name=payload.get("document_name", "documento.pdf"),
                file_hash=payload.get("file_hash", ""),
                signer_label=payload.get("signer", "JUSTICIA"),
            )

    import hashlib
    from datetime import datetime, timezone

    from .base import log_tool_execution

    document_name = payload.get("document_name", "documento.pdf")
    digest = payload.get("file_hash", "")
    signer = payload.get("signer", "JUSTICIA")
    ts = datetime.now(timezone.utc).isoformat()
    composite = f"{document_name}:{digest}:{signer}:{ts}"
    signature = hashlib.sha256(composite.encode("utf-8")).hexdigest()
    result = {
        "document": document_name,
        "signature": signature,
        "signed_at": ts,
        "signer": signer,
        "real_execution": False,
    }
    log_tool_execution("JUSTICIA", "pdf_signer", "Firma sin BD", {"payload": payload, "result": result})
    return result


def generate_contract_kit(payload: Dict[str, Any], user_id: Optional[int] = None, db=None) -> Dict[str, Any]:
    if db and user_id:
        from app.models.user import User
        from services.contract_generator import generate_contract

        user = db.query(User).filter(User.id == user_id).first()
        if user:
            return generate_contract(
                db,
                user,
                parties=payload.get("parties", []),
                scope=payload.get("scope", "servicios"),
                media_buying=bool(payload.get("media_buying")),
            )

    from .justicia_tools_heuristic import generate_contract_heuristic

    return generate_contract_heuristic(payload)


def run_gdpr_audit(payload: Dict[str, Any], user_id: Optional[int] = None, db=None) -> Dict[str, Any]:
    if db and user_id:
        from app.models.user import User
        from services.gdpr_engine import run_gdpr_check

        user = db.query(User).filter(User.id == user_id).first()
        if user:
            systems: List[str] = payload.get("systems", [])
            return run_gdpr_check(db, user, systems=systems)

    from .justicia_tools_heuristic import run_gdpr_heuristic

    return run_gdpr_heuristic(payload)
