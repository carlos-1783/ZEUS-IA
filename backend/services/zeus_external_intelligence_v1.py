"""
Inteligencia externa v1 — sin inventar datos; unknown si no hay fuente.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.crm_lead import CrmLead
from app.models.customer import Customer
from app.models.user import User
import services.crm_office_service as crm_svc


def research_business(
    db: Session,
    *,
    user: User,
    query: str,
    lead_id: Optional[int] = None,
    customer_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Investiga datos públicos disponibles. Si no hay API configurada → unknown.
    Persiste insights en CRM (lead o customer metadata).
    """
    q = (query or "").strip()
    insights: Dict[str, Any] = {
        "public_business_data": "unknown",
        "insurance_estimations": "unknown",
        "market_pricing": "unknown",
        "competitor_analysis": "unknown",
        "query": q,
        "note": "Sin fuente externa configurada; no se inventan datos.",
    }

    # Placeholder for future real APIs — explicitly unknown
    cid = crm_svc.primary_company_id(db, user)
    payload = json.dumps(insights, ensure_ascii=False)

    if lead_id:
        lead = db.query(CrmLead).filter(CrmLead.id == lead_id, CrmLead.company_id == cid).first()
        if lead:
            lead.external_insights_json = payload
            db.add(lead)
            db.commit()
    elif customer_id:
        cust = db.query(Customer).filter(Customer.id == customer_id, Customer.company_id == cid).first()
        if cust:
            meta = dict(cust.metadata_ or {}) if isinstance(cust.metadata_, dict) else {}
            meta["external_insights"] = insights
            cust.metadata_ = meta
            db.add(cust)
            db.commit()

    return {"success": True, "insights": insights, "persisted": bool(lead_id or customer_id)}
