"""Cross-agent compliance signals → compliance_events."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.models.compliance_event import ComplianceEvent
from app.models.user import User


def _add(db: Session, event_type: str, severity: str, source: str, details: Dict[str, Any]) -> None:
    exists = (
        db.query(ComplianceEvent)
        .filter(
            ComplianceEvent.event_type == event_type,
            ComplianceEvent.source == source,
            ComplianceEvent.created_at >= datetime.now(timezone.utc) - timedelta(hours=24),
        )
        .first()
    )
    if exists:
        return
    db.add(
        ComplianceEvent(
            event_type=event_type,
            severity=severity,
            source=source,
            details_json=json.dumps(details, ensure_ascii=False, default=str),
        )
    )


def sync_cross_agent_events(db: Session, user: User) -> Dict[str, Any]:
    """THALOS, AFRODITA, PERSEO, RAFAEL → compliance_events."""
    synced = {"thalos": 0, "afrodita": 0, "perseo": 0, "rafael": 0}

    try:
        from app.models.thalos_alert import ThalosAlert

        open_alerts = db.query(ThalosAlert).filter(ThalosAlert.resolved.is_(False)).limit(10).all()
        for alert in open_alerts:
            _add(
                db,
                "security_alert",
                alert.level or "high",
                "THALOS",
                {"alert_id": alert.id, "title": alert.title, "rule_id": alert.rule_id},
            )
            synced["thalos"] += 1
    except Exception:
        pass

    try:
        from app.models.company_employee import CompanyEmployee

        emp_count = (
            db.query(CompanyEmployee)
            .filter(CompanyEmployee.user_id == user.id, CompanyEmployee.is_active.is_(True))
            .count()
        )
        if emp_count == 0:
            _add(db, "hr_compliance_gap", "medium", "AFRODITA", {"issue": "no_active_employees"})
            synced["afrodita"] += 1
    except Exception:
        pass

    try:
        from app.models.perseo_job import PerseoJob

        failed_jobs = (
            db.query(PerseoJob)
            .filter(PerseoJob.user_id == user.id, PerseoJob.status == "failed")
            .count()
        )
        if failed_jobs:
            _add(
                db,
                "marketing_content_risk",
                "low",
                "PERSEO",
                {"failed_jobs": int(failed_jobs)},
            )
            synced["perseo"] += 1
    except Exception:
        pass

    try:
        from app.models.expense import Expense

        unlinked = db.query(Expense).filter(Expense.created_by == user.id).count()
        if unlinked > 0:
            _add(
                db,
                "fiscal_data_review",
                "low",
                "RAFAEL",
                {"expense_records": int(unlinked)},
            )
            synced["rafael"] += 1
    except Exception:
        pass

    db.flush()
    return {"synced": synced, "real_execution": True}
