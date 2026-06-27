"""JUSTICIA GDPR engine — real DB checks for consent, retention, exposure."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models.compliance_event import ComplianceEvent
from app.models.document_approval import DocumentApproval
from app.models.user import User


def _persist_event(db: Session, event_type: str, severity: str, source: str, details: Dict[str, Any]) -> ComplianceEvent:
    row = ComplianceEvent(
        event_type=event_type,
        severity=severity,
        source=source,
        details_json=json.dumps(details, ensure_ascii=False, default=str),
    )
    db.add(row)
    db.flush()
    return row


def run_gdpr_check(db: Session, user: User, *, systems: List[str] | None = None) -> Dict[str, Any]:
    """Detect personal data usage, missing consent, retention violations, exposure risks."""
    issues: List[Dict[str, Any]] = []
    alerts: List[ComplianceEvent] = []

    if not getattr(user, "autoriza_envio_documentos_a_asesores", False):
        ev = _persist_event(
            db,
            "missing_consent",
            "high",
            "gdpr_engine",
            {"check": "autoriza_envio_documentos_a_asesores", "user_id": user.id},
        )
        alerts.append(ev)
        issues.append({"type": "missing_consent", "message": "Usuario sin consentimiento explícito para envío a asesores"})

    old_threshold = datetime.now(timezone.utc) - timedelta(days=365 * 3)
    stale = (
        db.query(DocumentApproval)
        .filter(
            DocumentApproval.user_id == user.id,
            DocumentApproval.created_at < old_threshold,
            DocumentApproval.status.notin_(("exported", "filed_external", "approved")),
        )
        .count()
    )
    if stale:
        ev = _persist_event(
            db,
            "retention_exceeded",
            "medium",
            "gdpr_engine",
            {"stale_documents": int(stale), "threshold_days": 1095},
        )
        alerts.append(ev)
        issues.append({"type": "retention_exceeded", "message": f"{stale} documento(s) sin archivar >3 años"})

    exposed = (
        db.query(DocumentApproval)
        .filter(
            DocumentApproval.user_id == user.id,
            DocumentApproval.visible_in_workspace.is_(True),
            DocumentApproval.status.in_(("draft", "pending_approval")),
            DocumentApproval.document_type.in_(("gdpr", "contract", "privacy")),
        )
        .count()
    )
    if exposed:
        ev = _persist_event(
            db,
            "data_exposure_risk",
            "high",
            "gdpr_engine",
            {"exposed_pending": int(exposed)},
        )
        alerts.append(ev)
        issues.append({"type": "data_exposure_risk", "message": f"{exposed} documento(s) sensibles visibles en workspace"})

    systems = systems or []
    if "whatsapp" in [s.lower() for s in systems]:
        ev = _persist_event(
            db,
            "whatsapp_consent_review",
            "medium",
            "gdpr_engine",
            {"system": "whatsapp"},
        )
        alerts.append(ev)
        issues.append({"type": "whatsapp_consent", "message": "Verificar consentimiento WhatsApp (Art. 6 RGPD)"})

    try:
        from app.models.thalos_event import ThalosEvent

        recent_pii = (
            db.query(ThalosEvent)
            .filter(ThalosEvent.message.ilike("%email%"))
            .order_by(ThalosEvent.id.desc())
            .limit(5)
            .count()
        )
        if recent_pii:
            issues.append({"type": "pii_in_logs", "message": "Posible PII en logs THALOS — revisar anonimización"})
    except Exception:
        pass

    return {
        "issues": issues,
        "alerts_created": len(alerts),
        "alert_ids": [a.public_id for a in alerts],
        "systems_checked": systems,
        "real_execution": True,
        "data_origin": "database",
    }
