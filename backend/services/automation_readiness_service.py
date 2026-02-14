"""
📊 Automation Readiness Service
Calcula score de madurez para automatización y persiste en BD.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, Any, Optional

from sqlalchemy.orm import Session

from app.models.automation_readiness import AutomationReadiness
from app.models.user import User

logger = logging.getLogger(__name__)

# Umbrales de status
STATUS_READY_FOR_FULL_AUTOMATION = "READY_FOR_FULL_AUTOMATION"
STATUS_PARTIAL_READY = "PARTIAL_READY"
STATUS_NOT_READY = "NOT_READY"

SCORE_THRESHOLD_READY = 70
SCORE_THRESHOLD_PARTIAL = 40


def _calculate_score(data: Dict[str, Any]) -> int:
    """
    Calcula score 0-100 basado en métricas de readiness.
    - leads_last_30_days: hasta 20 pts (5 por cada 5 leads, máx 20)
    - avg_response_time_hours: hasta 20 pts (rápido = más pts)
    - active_channels: hasta 15 pts (3 por canal, máx 5 canales)
    - monthly_revenue_estimate: hasta 15 pts
    - has_defined_offer: 15 pts
    - has_sales_process: 15 pts
    - team_size: bonus hasta 10 pts
    """
    score = 0
    leads = data.get("leads_last_30_days", 0) or 0
    score += min(20, (leads // 5) * 5)  # 0, 5, 10, 15, 20

    avg_hours = data.get("avg_response_time_hours", 24) or 24
    if avg_hours <= 1:
        score += 20
    elif avg_hours <= 4:
        score += 15
    elif avg_hours <= 12:
        score += 10
    elif avg_hours <= 24:
        score += 5

    channels = data.get("active_channels", 0) or 0
    score += min(15, channels * 3)

    revenue = data.get("monthly_revenue_estimate", 0) or 0
    if revenue >= 10000:
        score += 15
    elif revenue >= 5000:
        score += 12
    elif revenue >= 1000:
        score += 8
    elif revenue >= 500:
        score += 5

    if data.get("has_defined_offer"):
        score += 15
    if data.get("has_sales_process"):
        score += 15

    team = data.get("team_size", 0) or 0
    if team >= 5:
        score += 10
    elif team >= 2:
        score += 5

    return min(100, score)


def _get_status(score: int) -> str:
    if score >= SCORE_THRESHOLD_READY:
        return STATUS_READY_FOR_FULL_AUTOMATION
    if score >= SCORE_THRESHOLD_PARTIAL:
        return STATUS_PARTIAL_READY
    return STATUS_NOT_READY


def evaluate_and_persist(
    db: Session,
    company_id: int,
    data: Dict[str, Any],
) -> AutomationReadiness:
    """
    Evalúa readiness, calcula score y persiste en BD.
    """
    score = _calculate_score(data)
    status = _get_status(score)

    record = AutomationReadiness(
        company_id=company_id,
        leads_last_30_days=data.get("leads_last_30_days", 0) or 0,
        avg_response_time_hours=float(data.get("avg_response_time_hours", 0) or 0),
        active_channels=data.get("active_channels", 0) or 0,
        monthly_revenue_estimate=float(data.get("monthly_revenue_estimate", 0) or 0),
        has_defined_offer=bool(data.get("has_defined_offer", False)),
        has_sales_process=bool(data.get("has_sales_process", False)),
        team_size=data.get("team_size", 0) or 0,
        score=score,
        status=status,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    logger.info(f"[AUTOMATION_READINESS] company_id={company_id} score={score} status={status}")
    return record


def get_latest(db: Session, company_id: int) -> Optional[AutomationReadiness]:
    """Obtiene la última evaluación para una empresa."""
    return (
        db.query(AutomationReadiness)
        .filter(AutomationReadiness.company_id == company_id)
        .order_by(AutomationReadiness.evaluated_at.desc())
        .first()
    )
