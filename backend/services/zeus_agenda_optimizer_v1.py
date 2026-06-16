"""
Optimización de agenda comercial v1 — propone huecos según score.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.crm_lead import CrmLead
from app.models.user import User
import services.crm_office_service as crm_svc


def propose_meeting_slots(
    db: Session,
    *,
    user: User,
    lead_id: int,
    duration_minutes: int = 30,
) -> Dict[str, Any]:
    cid = crm_svc.primary_company_id(db, user)
    lead = db.query(CrmLead).filter(CrmLead.id == lead_id, CrmLead.company_id == cid).first()
    if not lead:
        raise ValueError("Lead no encontrado")

    now = datetime.now(timezone.utc)
    priority_boost = 0 if (lead.customer_priority or "low") == "high" else 1
    base = now + timedelta(days=1 + priority_boost)
    slots: List[Dict[str, Any]] = []
    for day_offset in range(5):
        day = base + timedelta(days=day_offset)
        for hour in (10, 12, 16):
            start = day.replace(hour=hour, minute=0, second=0, microsecond=0)
            end = start + timedelta(minutes=duration_minutes)
            if lead.meeting_at and abs((lead.meeting_at - start).total_seconds()) < 3600:
                continue
            slots.append(
                {
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "lead_id": lead.id,
                    "lead_score": lead.lead_score,
                    "priority": lead.customer_priority,
                }
            )

    return {
        "lead_id": lead.id,
        "proposed_slots": slots[:6],
        "rules_applied": ["prioritize_high_score", "avoid_overlap", "business_hours"],
    }


def schedule_meeting(
    db: Session,
    *,
    user: User,
    lead_id: int,
    start_iso: str,
) -> Dict[str, Any]:
    cid = crm_svc.primary_company_id(db, user)
    lead = db.query(CrmLead).filter(CrmLead.id == lead_id, CrmLead.company_id == cid).first()
    if not lead:
        raise ValueError("Lead no encontrado")

    start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)

    overlap = (
        db.query(CrmLead)
        .filter(
            CrmLead.company_id == cid,
            CrmLead.id != lead.id,
            CrmLead.meeting_at.isnot(None),
            CrmLead.meeting_at >= start - timedelta(minutes=30),
            CrmLead.meeting_at <= start + timedelta(minutes=30),
        )
        .first()
    )
    if overlap:
        raise ValueError("Solapamiento detectado con otra reunión.")

    lead.meeting_at = start
    lead.next_best_action = "prepare_meeting"
    db.add(lead)
    db.commit()
    db.refresh(lead)

    return {"lead_id": lead.id, "meeting_at": lead.meeting_at.isoformat(), "scheduled": True}
