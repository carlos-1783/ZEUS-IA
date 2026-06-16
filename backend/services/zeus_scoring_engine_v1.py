"""
Scoring inteligente v1 — priorización comercial con datos reales.
score = (revenue * 0.4) + (payment_score * 0.2) + (engagement * 0.2) + (potential * 0.2)
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.crm_lead import CrmLead
from app.models.crm_office import CrmActivityLog
from app.models.customer import Customer
from app.models.fiscal import TPVSale
from app.models.user import User
import services.crm_office_service as crm_svc


def _payment_score_for_customer(db: Session, *, company_id: int, customer_id: int) -> float:
    since = datetime.now(timezone.utc) - timedelta(days=365)
    sales = (
        db.query(TPVSale)
        .filter(
            TPVSale.company_id == company_id,
            TPVSale.sale_date >= since,
        )
        .all()
    )
    paid = 0
    for s in sales:
        cd = s.customer_data if isinstance(s.customer_data, dict) else {}
        if cd.get("customer_id") == customer_id or cd.get("crm_customer_id") == customer_id:
            paid += 1
    return min(100.0, paid * 20.0)


def _engagement_score(db: Session, *, company_id: int, customer_id: Optional[int], lead_id: Optional[int]) -> float:
    since = datetime.now(timezone.utc) - timedelta(days=90)
    q = db.query(func.count(CrmActivityLog.id)).filter(
        CrmActivityLog.company_id == company_id,
        CrmActivityLog.created_at >= since,
    )
    if customer_id:
        q = q.filter(CrmActivityLog.customer_id == customer_id)
    count = int(q.scalar() or 0)
    return min(100.0, count * 10.0)


def compute_lead_score(
    *,
    revenue: float = 0.0,
    payment_score: float = 0.0,
    engagement: float = 0.0,
    potential: float = 0.0,
) -> float:
    raw = (revenue * 0.4) + (payment_score * 0.2) + (engagement * 0.2) + (potential * 0.2)
    return round(min(100.0, max(0.0, raw)), 2)


def _priority_from_score(score: float) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _next_action(score: float, has_meeting: bool) -> str:
    if has_meeting:
        return "prepare_meeting"
    if score >= 70:
        return "auto_schedule_meeting"
    if score >= 40:
        return "suggest_followup"
    return "nurture"


def score_customer(db: Session, *, user: User, customer_id: int) -> Dict[str, Any]:
    cid = crm_svc.primary_company_id(db, user)
    cust = db.query(Customer).filter(Customer.id == customer_id, Customer.company_id == cid).first()
    if not cust:
        raise ValueError("Cliente no encontrado")

    since = datetime.now(timezone.utc) - timedelta(days=365)
    revenue = float(
        db.query(func.coalesce(func.sum(TPVSale.total), 0.0))
        .filter(TPVSale.company_id == cid, TPVSale.sale_date >= since)
        .scalar()
        or 0
    )
    payment_score = _payment_score_for_customer(db, company_id=cid, customer_id=customer_id)
    engagement = _engagement_score(db, company_id=cid, customer_id=customer_id, lead_id=None)
    potential = float((cust.metadata_ or {}).get("estimated_value") or 0) if isinstance(cust.metadata_, dict) else 0.0
    if potential > 100:
        potential = min(100.0, potential / 1000.0)

    score = compute_lead_score(
        revenue=min(100.0, revenue / 100.0),
        payment_score=payment_score,
        engagement=engagement,
        potential=potential,
    )
    priority = _priority_from_score(score)
    nba = _next_action(score, False)
    return {
        "customer_id": customer_id,
        "lead_score": score,
        "customer_priority": priority,
        "next_best_action": nba,
    }


def score_lead(db: Session, *, user: User, lead_id: int) -> Dict[str, Any]:
    cid = crm_svc.primary_company_id(db, user)
    lead = db.query(CrmLead).filter(CrmLead.id == lead_id, CrmLead.company_id == cid).first()
    if not lead:
        raise ValueError("Lead no encontrado")

    revenue = 0.0
    payment_score = 0.0
    if lead.converted_customer_id:
        payment_score = _payment_score_for_customer(db, company_id=cid, customer_id=lead.converted_customer_id)
    engagement = _engagement_score(db, company_id=cid, customer_id=lead.converted_customer_id, lead_id=lead.id)
    potential = min(100.0, float(lead.estimated_value or 0) / 100.0) if lead.estimated_value else 30.0

    score = compute_lead_score(revenue=revenue, payment_score=payment_score, engagement=engagement, potential=potential)
    lead.lead_score = score
    lead.customer_priority = _priority_from_score(score)
    lead.next_best_action = _next_action(score, lead.meeting_at is not None)
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return {
        "lead_id": lead.id,
        "lead_score": lead.lead_score,
        "customer_priority": lead.customer_priority,
        "next_best_action": lead.next_best_action,
    }


def create_lead(
    db: Session,
    *,
    user: User,
    name: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    sector: Optional[str] = None,
    estimated_value: Optional[float] = None,
) -> CrmLead:
    cid = crm_svc.primary_company_id(db, user)
    lead = CrmLead(
        company_id=cid,
        owner_user_id=user.id,
        name=name.strip(),
        email=email,
        phone=phone,
        sector=sector,
        estimated_value=estimated_value,
        status="open",
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    score_lead(db, user=user, lead_id=lead.id)
    db.refresh(lead)
    return lead


def convert_lead_to_customer(db: Session, *, user: User, lead_id: int) -> Dict[str, Any]:
    from app.schemas.customer import CustomerCreate

    cid = crm_svc.primary_company_id(db, user)
    lead = db.query(CrmLead).filter(CrmLead.id == lead_id, CrmLead.company_id == cid).first()
    if not lead:
        raise ValueError("Lead no encontrado")
    if lead.converted_customer_id:
        return {"customer_id": lead.converted_customer_id, "already_converted": True}

    if not lead.email:
        raise ValueError("El lead necesita email para convertirse en cliente.")

    customer = crm_svc.create_customer(
        db,
        user,
        CustomerCreate(name=lead.name, email=lead.email, phone=lead.phone, notes=f"Convertido desde lead #{lead.id}"),
    )
    lead.status = "converted"
    lead.converted_customer_id = customer.id
    db.add(lead)
    db.commit()
    return {"customer_id": customer.id, "lead_id": lead.id}
