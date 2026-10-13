"""Executive dashboard analytics from real DB sources (zeus_events, alerts, automations)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.agent_activity import AgentActivity
from services.chain_log import exclude_chain_steps
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
    if user is None or getattr(user, "id", None) is None:
        # Sin usuario no hay tenant: nunca devolver eventos de todas las cuentas.
        return q.filter(False)
    return q.filter(ZeusEvent.user_id == user.id)


# Nombre canonico de cada agente del Olimpo (AgentActivity.agent_name puede venir como
# "ZEUS" o "ZEUS CORE"). Es el catalogo del producto, no un KPI: el KPI son los activos.
_AGENT_CANON = {
    "ZEUS": "ZEUS CORE",
    "ZEUS CORE": "ZEUS CORE",
    "PERSEO": "PERSEO",
    "RAFAEL": "RAFAEL",
    "THALOS": "THALOS",
    "JUSTICIA": "JUSTICIA",
    "AFRODITA": "AFRODITA",
}

AUTOMATIONS_WINDOW_DAYS = 30


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

    if user is None or getattr(user, "id", None) is None:
        return 0, 0

    try:
        dq = db.query(ZeusDomainEvent).filter(
            ZeusDomainEvent.created_at >= since, ZeusDomainEvent.user_id == user.id
        )
        total = dq.count()
        if total > 0:
            return total, total
    except Exception as exc:
        logger.warning("[ANALYTICS] domain_events count: %s", exc)

    try:
        if not getattr(user, "email", None):
            return 0, 0
        aq = db.query(AgentActivity).filter(
            AgentActivity.created_at >= since, AgentActivity.user_email == user.email
        )
        aq = exclude_chain_steps(aq)  # J7: sin trazas chain_*
        total = aq.count()
        success = aq.filter(AgentActivity.status.in_(("completed", "success"))).count()
        return total, success
    except Exception as exc:
        logger.warning("[ANALYTICS] agent_activities count: %s", exc)
        return 0, 0


def _count_active_agents_24h(db: Session, user: Optional[User]) -> int:
    """Agentes del Olimpo con actividad real de ESTA cuenta en las ultimas 24h."""
    if user is None or not getattr(user, "email", None):
        return 0
    since = _utcnow() - timedelta(hours=24)
    aq = db.query(AgentActivity.agent_name).filter(
        AgentActivity.created_at >= since, AgentActivity.user_email == user.email
    )
    aq = exclude_chain_steps(aq)
    names = {
        _AGENT_CANON.get(str(r[0] or "").strip().upper())
        for r in aq.distinct().all()
    }
    names.discard(None)
    return len(names)


def _is_platform_superuser(user: Optional[User]) -> bool:
    return bool(user is not None and getattr(user, "is_superuser", False))


def _count_alerts(db: Session, user: Optional[User]) -> int:
    # Sin usuario no hay tenant: fail-closed (antes se contaban alertas de todas las cuentas).
    if user is None or getattr(user, "id", None) is None:
        return 0
    try:
        q = db.query(ZeusAlert).filter(ZeusAlert.resolved.is_(False), ZeusAlert.user_id == user.id)
        count = q.count()
        if count > 0:
            return count
    except Exception as exc:
        logger.warning("[ANALYTICS] zeus_alerts count: %s", exc)

    # compliance_events no tiene user_id ni company_id: son eventos de toda la plataforma.
    # Solo el superusuario puede verlos; a un cliente se le filtraban alertas de otras empresas.
    if not _is_platform_superuser(user):
        return 0
    try:
        since = _utcnow() - timedelta(days=7)
        cq = db.query(ComplianceEvent).filter(
            ComplianceEvent.severity.in_(("high", "medium")),
            ComplianceEvent.created_at >= since,
        )
        return cq.count()
    except Exception:
        return 0


def _user_automation_logs_q(db: Session, user: Optional[User], *, days: int = AUTOMATIONS_WINDOW_DAYS):
    from app.models.zeus_analytics import ZeusAutomationLog

    if user is None or getattr(user, "id", None) is None:
        return None
    since = _utcnow() - timedelta(days=days)
    return ZeusAutomationLog, db.query(ZeusAutomationLog).filter(
        ZeusAutomationLog.user_id == user.id, ZeusAutomationLog.executed_at >= since
    )


def _count_automations(db: Session, user: Optional[User]) -> int:
    """Automatizaciones distintas que se ejecutaron de verdad para esta cuenta (ultimos 30 dias).

    Antes se contaban las filas sembradas de un catalogo global (zeus_automations), asi que
    el KPI marcaba siempre 6 para cualquier empresa, ejecutara algo o no.
    """
    scoped = _user_automation_logs_q(db, user)
    if scoped is None:
        return 0
    model, q = scoped
    return q.with_entities(model.automation_name).distinct().count()


def _system_status(db: Session) -> str:
    try:
        from sqlalchemy import text

        db.execute(text("SELECT 1"))
        return "healthy"
    except Exception:
        return "degraded"


def build_executive_analytics(db: Session, user: Optional[User]) -> Dict[str, Any]:
    """KPI block for executive dashboard — solo conteos reales de la cuenta.

    `efficiency` es None (sin datos) si no hubo tareas en 24h: un 0 % aparentaba que todo fallaba.
    """
    tasks24h, success24h = _count_events_24h(db, user)
    efficiency = round((success24h / tasks24h) * 100) if tasks24h > 0 else None

    return {
        "agents": _count_active_agents_24h(db, user),
        "agents_total": OLYMPUS_AGENTS,
        "tasks24h": tasks24h,
        "alerts": _count_alerts(db, user),
        "automations": _count_automations(db, user),
        "automations_window_days": AUTOMATIONS_WINDOW_DAYS,
        "efficiency": efficiency,
        "system": _system_status(db),
        "real_data": True,
        "success_events_24h": success24h,
    }


def list_recent_events(
    db: Session,
    user: Optional[User],
    *,
    hours: int = 24,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    since = _utcnow() - timedelta(hours=hours)
    try:
        q = _user_scope_event_q(db, user).filter(ZeusEvent.created_at >= since)
        rows = q.order_by(ZeusEvent.created_at.desc()).limit(limit).all()
        if rows:
            return [
                {
                    "id": r.id,
                    "type": r.type,
                    "agent": r.agent,
                    "status": r.status,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]
    except Exception as exc:
        logger.warning("[ANALYTICS] list_recent_events: %s", exc)

    try:
        dq = db.query(ZeusDomainEvent).filter(ZeusDomainEvent.created_at >= since)
        if user and getattr(user, "id", None) is not None:
            dq = dq.filter(ZeusDomainEvent.user_id == user.id)
        rows = dq.order_by(ZeusDomainEvent.created_at.desc()).limit(limit).all()
        return [
            {
                "id": r.public_id,
                "type": r.event_name,
                "agent": r.source_module,
                "status": "success",
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    except Exception:
        return []


def list_unresolved_alerts(
    db: Session,
    user: Optional[User],
    *,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    if user is None or getattr(user, "id", None) is None:
        return []
    try:
        q = db.query(ZeusAlert).filter(ZeusAlert.resolved.is_(False), ZeusAlert.user_id == user.id)
        rows = q.order_by(ZeusAlert.created_at.desc()).limit(limit).all()
        if rows:
            return [
                {
                    "id": a.id,
                    "level": a.level,
                    "message": a.message,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in rows
            ]
    except Exception as exc:
        logger.warning("[ANALYTICS] list_unresolved_alerts: %s", exc)

    # Fallback a compliance_events (global, sin tenant) solo para el superusuario.
    if not _is_platform_superuser(user):
        return []
    try:
        since = _utcnow() - timedelta(days=7)
        cq = db.query(ComplianceEvent).filter(
            ComplianceEvent.severity.in_(("high", "medium")),
            ComplianceEvent.created_at >= since,
        )
        rows = cq.order_by(ComplianceEvent.created_at.desc()).limit(limit).all()
        return [
            {
                "id": c.public_id,
                "level": c.severity,
                "message": c.event_type,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in rows
        ]
    except Exception:
        return []


def list_automation_rows(db: Session, user: Optional[User], *, limit: int = 50) -> List[Dict[str, Any]]:
    """Automatizaciones ejecutadas para esta cuenta (zeus_automation_logs), ultima ejecucion primero.

    Antes devolvia el catalogo global sembrado con status "active" fijo y un last_run que
    actualizaban los eventos de cualquier empresa.
    """
    scoped = _user_automation_logs_q(db, user)
    if scoped is None:
        return []
    model, q = scoped
    rows = (
        q.with_entities(
            model.automation_name,
            func.count(model.id),
            func.max(model.executed_at),
        )
        .group_by(model.automation_name)
        .order_by(func.max(model.executed_at).desc())
        .limit(limit)
        .all()
    )
    out: List[Dict[str, Any]] = []
    for name, runs, last_run in rows:
        last = (
            q.filter(model.automation_name == name)
            .order_by(model.executed_at.desc())
            .first()
        )
        out.append(
            {
                "name": name,
                "status": last.status if last else None,
                "total_runs": int(runs or 0),
                "last_run": last_run.isoformat() if last_run else None,
            }
        )
    return out


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
