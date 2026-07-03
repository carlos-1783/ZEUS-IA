"""Executive dashboard analytics from real DB sources (zeus_events, alerts, automations)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.agent_activity import AgentActivity
from app.models.compliance_event import ComplianceEvent
from app.models.user import User
from app.models.zeus_analytics import ZeusAlert, ZeusAutomation, ZeusEvent
from app.models.zeus_domain_event import ZeusDomainEvent

logger = logging.getLogger(__name__)

OLYMPUS_AGENTS = 6

DEFAULT_AUTOMATIONS = (
    "contract_rrhh_pipeline",
    "crm_payment_risk",
    "teamflow_handoff",
    "document_pipeline",
    "workspace_playbook",
    "event_bus_dispatch",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _user_scope_event_q(db: Session, user: Optional[User]):
    q = db.query(ZeusEvent)
    if user and not getattr(user, "is_superuser", False):
        q = q.filter(ZeusEvent.user_id == user.id)
    return q


def ensure_default_automations(db: Session) -> None:
    try:
        for name in DEFAULT_AUTOMATIONS:
            exists = db.query(ZeusAutomation).filter(ZeusAutomation.name == name).first()
            if not exists:
                db.add(ZeusAutomation(name=name, status="active", last_run=None))
        db.flush()
    except Exception as exc:
        logger.warning("[ANALYTICS] ensure_default_automations: %s", exc)


def record_zeus_event(
    db: Session,
    *,
    event_type: str,
    agent: str,
    status: str = "success",
    user_id: Optional[int] = None,
) -> None:
    try:
        db.add(
            ZeusEvent(
                type=event_type,
                agent=(agent or "ZEUS")[:64],
                status=(status or "success")[:32],
                user_id=user_id,
            )
        )
        touch = (
            db.query(ZeusAutomation)
            .filter(ZeusAutomation.name == event_type, ZeusAutomation.status == "active")
            .first()
        )
        if not touch:
            touch = (
                db.query(ZeusAutomation)
                .filter(ZeusAutomation.name == "event_bus_dispatch", ZeusAutomation.status == "active")
                .first()
            )
        if touch:
            touch.last_run = _utcnow()
        db.flush()
    except Exception as exc:
        logger.warning("[ANALYTICS] record_zeus_event failed: %s", exc)


def record_zeus_alert(
    db: Session,
    *,
    level: str,
    message: str,
    user_id: Optional[int] = None,
    resolved: bool = False,
) -> None:
    try:
        db.add(
            ZeusAlert(
                level=(level or "medium")[:16],
                message=message[:2000],
                user_id=user_id,
                resolved=resolved,
            )
        )
        db.flush()
    except Exception as exc:
        logger.warning("[ANALYTICS] record_zeus_alert failed: %s", exc)


def _count_events_24h(db: Session, user: Optional[User]) -> tuple[int, int]:
    since = _utcnow() - timedelta(hours=24)
    try:
        q = _user_scope_event_q(db, user).filter(ZeusEvent.created_at >= since)
        total = q.count()
        success = q.filter(ZeusEvent.status == "success").count()
        if total > 0:
            return total, success
    except Exception as exc:
        logger.warning("[ANALYTICS] zeus_events count: %s", exc)

    try:
        dq = db.query(ZeusDomainEvent).filter(ZeusDomainEvent.created_at >= since)
        if user and not getattr(user, "is_superuser", False):
            dq = dq.filter(ZeusDomainEvent.user_id == user.id)
        total = dq.count()
        return total, total
    except Exception:
        pass

    try:
        aq = db.query(AgentActivity).filter(AgentActivity.created_at >= since)
        if user and not getattr(user, "is_superuser", False):
            aq = aq.filter(AgentActivity.user_email == user.email)
        total = aq.count()
        success = aq.filter(AgentActivity.status.in_(("completed", "success"))).count()
        return total, success
    except Exception:
        return 0, 0


def _count_alerts(db: Session, user: Optional[User]) -> int:
    try:
        q = db.query(ZeusAlert).filter(ZeusAlert.resolved.is_(False))
        if user and not getattr(user, "is_superuser", False):
            q = q.filter(ZeusAlert.user_id == user.id)
        count = q.count()
        if count > 0:
            return count
    except Exception as exc:
        logger.warning("[ANALYTICS] zeus_alerts count: %s", exc)

    try:
        since = _utcnow() - timedelta(days=7)
        cq = db.query(ComplianceEvent).filter(
            ComplianceEvent.severity.in_(("high", "medium")),
            ComplianceEvent.created_at >= since,
        )
        return cq.count()
    except Exception:
        return 0


def _count_automations(db: Session) -> int:
    try:
        ensure_default_automations(db)
        return db.query(ZeusAutomation).filter(ZeusAutomation.status == "active").count()
    except Exception as exc:
        logger.warning("[ANALYTICS] zeus_automations count: %s", exc)
        return len(DEFAULT_AUTOMATIONS)


def _system_status(db: Session) -> str:
    try:
        from sqlalchemy import text

        db.execute(text("SELECT 1"))
        return "healthy"
    except Exception:
        return "degraded"


def build_executive_analytics(db: Session, user: Optional[User]) -> Dict[str, Any]:
    """KPI block for executive dashboard — real counts, safe fallbacks."""
    tasks24h, success24h = _count_events_24h(db, user)
    total = max(tasks24h, 1)
    efficiency = round((success24h / total) * 100)

    return {
        "agents": OLYMPUS_AGENTS,
        "tasks24h": tasks24h,
        "alerts": _count_alerts(db, user),
        "automations": _count_automations(db),
        "efficiency": efficiency,
        "system": _system_status(db),
        "real_data": True,
        "success_events_24h": success24h,
    }


def backfill_events_from_domain_bus(db: Session, *, limit: int = 500) -> int:
    """One-time style backfill: domain events → zeus_events (idempotent by count check)."""
    try:
        if db.query(func.count(ZeusEvent.id)).scalar():
            return 0
        rows = db.query(ZeusDomainEvent).order_by(ZeusDomainEvent.id.desc()).limit(limit).all()
        for row in rows:
            record_zeus_event(
                db,
                event_type=row.event_name,
                agent=row.source_module or "ZEUS",
                status="success",
                user_id=row.user_id,
            )
        db.flush()
        return len(rows)
    except Exception as exc:
        logger.warning("[ANALYTICS] backfill failed: %s", exc)
        return 0
