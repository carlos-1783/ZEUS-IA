"""THALOS v1 — motor de seguridad (lectura real de logs/actividades)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.agent_activity import AgentActivity
from app.models.cashflow_ledger import CashflowLedgerEntry
from app.models.thalos_security_event import ThalosLoginAttempt, ThalosSecurityEvent

logger = logging.getLogger(__name__)

SUSPICIOUS_PATTERNS = (
    "failed login",
    "unauthorized",
    "drop table",
    "union select",
    "rate limited",
    "403",
    "invalid credentials",
    "brute",
)

PROTECTED_EMAILS = frozenset(
    e.lower()
    for e in (
        "marketingdigitalper.seo@gmail.com",
        "admin",
        "root",
        "creator",
    )
)


def _persist_event(
    db: Session,
    *,
    event_type: str,
    severity: str,
    source: str,
    details: Dict[str, Any],
    user_id: Optional[int] = None,
    user_email: Optional[str] = None,
    ip_address: Optional[str] = None,
    company_id: Optional[int] = None,
    action_taken: Optional[str] = None,
    decision_rule: Optional[str] = None,
) -> ThalosSecurityEvent:
    row = ThalosSecurityEvent(
        event_type=event_type,
        severity=severity,
        source=source,
        user_id=user_id,
        user_email=user_email,
        ip_address=ip_address,
        company_id=company_id,
        details_json=json.dumps(details, ensure_ascii=False),
        action_taken=action_taken,
        decision_rule=decision_rule,
    )
    db.add(row)
    db.flush()
    return row


def record_login_attempt(
    db: Session,
    *,
    email: str,
    ip_address: Optional[str],
    success: bool,
) -> None:
    """Registro append-only de intentos de login (middleware opt-in)."""
    db.add(
        ThalosLoginAttempt(
            email=(email or "").strip().lower()[:255],
            ip_address=(ip_address or "")[:64] or None,
            success=1 if success else 0,
        )
    )
    db.flush()


def count_failed_logins(
    db: Session,
    *,
    email: Optional[str] = None,
    ip_address: Optional[str] = None,
    window_minutes: int = 60,
) -> int:
    since = datetime.now(timezone.utc) - timedelta(minutes=max(1, window_minutes))
    q = db.query(func.count(ThalosLoginAttempt.id)).filter(
        ThalosLoginAttempt.success == 0,
        ThalosLoginAttempt.created_at >= since,
    )
    if email:
        q = q.filter(ThalosLoginAttempt.email == email.strip().lower())
    if ip_address:
        q = q.filter(ThalosLoginAttempt.ip_address == ip_address)
    return int(q.scalar() or 0)


def scan_logs(
    db: Session,
    *,
    hours: int = 24,
    company_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Analiza agent_activities y patrones de seguridad recientes."""
    since = datetime.now(timezone.utc) - timedelta(hours=max(1, hours))
    activities: List[AgentActivity] = (
        db.query(AgentActivity)
        .filter(AgentActivity.created_at >= since)
        .order_by(AgentActivity.id.desc())
        .limit(500)
        .all()
    )

    alerts: List[Dict[str, Any]] = []
    for act in activities:
        blob = f"{act.action_type} {act.action_description} {json.dumps(act.details or {})}".lower()
        for pat in SUSPICIOUS_PATTERNS:
            if pat in blob:
                alerts.append(
                    {
                        "pattern": pat,
                        "agent": act.agent_name,
                        "action_type": act.action_type,
                        "activity_id": act.id,
                        "created_at": act.created_at.isoformat() if act.created_at else None,
                    }
                )
                break

    failed_by_email: Dict[str, int] = {}
    attempts = (
        db.query(ThalosLoginAttempt)
        .filter(ThalosLoginAttempt.created_at >= since, ThalosLoginAttempt.success == 0)
        .all()
    )
    for att in attempts:
        failed_by_email[att.email] = failed_by_email.get(att.email, 0) + 1

    brute_candidates = [
        {"email": em, "failed_count": cnt}
        for em, cnt in failed_by_email.items()
        if cnt >= 5 and em not in PROTECTED_EMAILS
    ]

    result = {
        "hours_scanned": hours,
        "activities_scanned": len(activities),
        "pattern_alerts": alerts,
        "failed_login_candidates": brute_candidates,
        "risk_level": "critical" if brute_candidates else ("high" if alerts else "ok"),
    }

    if alerts or brute_candidates:
        _persist_event(
            db,
            event_type="detect_suspicious_activity",
            severity=result["risk_level"],
            source="thalos_security_engine.scan_logs",
            details=result,
            company_id=company_id,
        )

    return result


def detect_cashflow_anomaly(
    db: Session,
    *,
    company_id: int,
    threshold_multiplier: float = 3.0,
) -> Dict[str, Any]:
    """Detecta movimientos de cashflow anómalos vs media del periodo."""
    since = datetime.now(timezone.utc) - timedelta(days=30)
    rows: List[CashflowLedgerEntry] = (
        db.query(CashflowLedgerEntry)
        .filter(
            CashflowLedgerEntry.company_id == company_id,
            CashflowLedgerEntry.created_at >= since,
        )
        .all()
    )
    if not rows:
        return {"company_id": company_id, "anomaly": False, "reason": "no_entries"}

    amounts = [float(r.amount or 0) for r in rows if float(r.amount or 0) > 0]
    if not amounts:
        return {"company_id": company_id, "anomaly": False, "reason": "no_positive_amounts"}

    avg = sum(amounts) / len(amounts)
    threshold = avg * threshold_multiplier
    suspicious = [
        {
            "id": r.id,
            "amount": r.amount,
            "direction": r.direction,
            "source": r.source,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
        if float(r.amount or 0) >= threshold and float(r.amount or 0) > 100
    ]

    anomaly = len(suspicious) > 0
    result = {
        "company_id": company_id,
        "anomaly": anomaly,
        "average_amount": round(avg, 2),
        "threshold": round(threshold, 2),
        "suspicious_entries": suspicious[:10],
    }

    if anomaly:
        _persist_event(
            db,
            event_type="audit_cashflow_anomaly",
            severity="high",
            source="thalos_security_engine.detect_cashflow_anomaly",
            details=result,
            company_id=company_id,
        )

    return result


def evaluate_decision_rules(
    db: Session,
    *,
    company_id: Optional[int] = None,
    user_email: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Evalúa reglas de decisión THALOS (solo diagnóstico; ejecución en executor)."""
    triggered: List[Dict[str, Any]] = []

    if user_email:
        fails = count_failed_logins(db, email=user_email, window_minutes=60)
        if fails > 5:
            triggered.append(
                {
                    "condition": "multiple_failed_logins > 5",
                    "action": "block_user",
                    "priority": "critical",
                    "context": {"email": user_email, "failed_count": fails},
                }
            )

    if company_id:
        cf = detect_cashflow_anomaly(db, company_id=company_id)
        if cf.get("anomaly"):
            triggered.append(
                {
                    "condition": "suspicious_payment_pattern",
                    "action": "audit_cashflow_anomaly",
                    "priority": "high",
                    "context": cf,
                }
            )

    triggered.append(
        {
            "condition": "system_idle_backup_time",
            "action": "trigger_backup",
            "priority": "medium",
            "context": {"note": "scheduled_check"},
        }
    )

    return triggered
