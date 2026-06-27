"""JUSTICIA audit service — real DB compliance across agents."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.compliance_event import ComplianceEvent
from app.models.document_approval import DocumentApproval
from app.models.legal_document import LegalDocument
from app.models.user import User
from services.gdpr_engine import run_gdpr_check
from services.justice_cross_agent_v1 import sync_cross_agent_events
from services.justice_system_audit_v1 import run_system_audit


def list_documents(
    db: Session,
    user: User,
    *,
    status: str | None = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    q = db.query(LegalDocument).filter(LegalDocument.user_id == user.id)
    if status:
        q = q.filter(LegalDocument.status == status)
    rows = q.order_by(LegalDocument.id.desc()).limit(min(limit, 200)).all()
    return [
        {
            "id": r.public_id,
            "type": r.doc_type,
            "status": r.status,
            "version": r.version,
            "owner_agent": r.owner_agent,
            "signature_hash": r.signature_hash,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]


def list_pending_documents_grouped(db: Session, user: User) -> Dict[str, Any]:
    """Pending documents from DB — grouped by agent + type, deduplicated."""
    rows = (
        db.query(DocumentApproval)
        .filter(
            DocumentApproval.user_id == user.id,
            DocumentApproval.visible_in_workspace.is_(True),
            DocumentApproval.status.in_(("draft", "pending_approval", "pending_review")),
        )
        .order_by(DocumentApproval.id.desc())
        .all()
    )
    seen: set[tuple[str, str]] = set()
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        key = (r.agent_name or "UNKNOWN", r.document_type or "unknown")
        if key in seen:
            continue
        seen.add(key)
        bucket = grouped.setdefault(r.agent_name or "UNKNOWN", [])
        bucket.append(
            {
                "id": r.id,
                "document_type": r.document_type,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
        )
    legal_pending = (
        db.query(LegalDocument)
        .filter(LegalDocument.user_id == user.id, LegalDocument.status == "draft")
        .count()
    )
    return {
        "grouped": grouped,
        "total_pending": len(seen) + int(legal_pending),
        "legal_documents_draft": int(legal_pending),
        "data_origin": "database",
    }


def run_real_audit(db: Session, user: User) -> Dict[str, Any]:
    if not getattr(settings, "JUSTICE_REAL_AUDIT_ENABLED", False):
        return {
            "success": False,
            "error": "JUSTICE_REAL_AUDIT_ENABLED=false",
            "real_execution": False,
        }

    sync_cross_agent_events(db, user)
    base = run_system_audit(db, user)
    gdpr = run_gdpr_check(db, user)

    legal_count = db.query(func.count(LegalDocument.id)).filter(LegalDocument.user_id == user.id).scalar() or 0
    compliance_count = db.query(func.count(ComplianceEvent.id)).scalar() or 0
    pending = list_pending_documents_grouped(db, user)

    base["legal_documents_count"] = int(legal_count)
    base["compliance_events_count"] = int(compliance_count)
    base["pending_documents"] = pending
    base["gdpr"] = gdpr
    base["real_execution"] = True
    base["strict_mode"] = True
    base["simulation_detected"] = False
    return {"success": True, **base}


def audit_status(db: Session, user: User) -> Dict[str, Any]:
    return {
        "legal_documents": int(
            db.query(func.count(LegalDocument.id)).filter(LegalDocument.user_id == user.id).scalar() or 0
        ),
        "compliance_events": int(db.query(func.count(ComplianceEvent.id)).scalar() or 0),
        "pending": list_pending_documents_grouped(db, user),
        "justice_real_audit_enabled": bool(getattr(settings, "JUSTICE_REAL_AUDIT_ENABLED", False)),
    }
