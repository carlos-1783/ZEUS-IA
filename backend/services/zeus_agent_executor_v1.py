"""
Executor unificado v2 — agentes ejecutan servicios reales (execution_over_text).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.customer import CustomerCreate
from app.schemas.zeus_action import ZeusAction
from app.schemas.zeus_task import ZeusExecutionResult, ZeusExecutionStepResult
from services import zeus_orchestrator_handlers as orch
from services.cashflow_ledger_service import get_balance, get_summary
from services.zeus_core_metrics_v1 import get_core_metrics
from services.zeus_human_approval_v1 import request_approval, requires_approval

import services.crm_office_service as crm_svc

logger = logging.getLogger(__name__)

MANDATORY_ACTIONS = {
    "ZEUS": frozenset({"create_customer", "get_customers", "send_campaign", "get_cashflow", "get_metrics"}),
    "RAFAEL": frozenset({"generate_invoice", "generate_model_303", "get_tax_summary"}),
    "PERSEO": frozenset({"create_campaign", "launch_campaign", "track_leads"}),
}


def track_leads_summary(db: Session, user: User) -> Dict[str, Any]:
    from app.models.crm_lead import CrmLead

    cid = crm_svc.primary_company_id(db, user)
    leads = db.query(CrmLead).filter(CrmLead.company_id == cid, CrmLead.status == "open").all()
    return {
        "open_leads": len(leads),
        "high_priority": sum(1 for l in leads if (l.customer_priority or "") == "high"),
        "with_meeting": sum(1 for l in leads if l.meeting_at is not None),
    }


    db: Session,
    *,
    user: User,
    agent: str,
    action: str,
    payload: Optional[Dict[str, Any]] = None,
    force_execute: bool = False,
) -> Dict[str, Any]:
    """
    Ejecuta acción de agente. Si requiere aprobación y force_execute=False → cola HITL.
    """
    agent_u = (agent or "ZEUS").strip().upper()
    if agent_u == "ZEUS CORE":
        agent_u = "ZEUS"
    act = (action or "").strip().lower()
    data = dict(payload or {})
    cid = crm_svc.primary_company_id(db, user)

    if requires_approval(act, data) and not force_execute:
        approval = request_approval(
            db,
            user=user,
            company_id=cid,
            agent_name=agent_u,
            action_type=act,
            payload=data,
        )
        return {
            "success": True,
            "executed": False,
            "needs_approval": True,
            "approval_id": approval.id,
            "message": f"Acción «{act}» pendiente de aprobación humana (ID {approval.id}).",
        }

    zeus_action = ZeusAction(
        action_type=_map_action_to_zeus_type(act),
        company_id=cid,
        user_id=user.id,
        payload=data,
        requires_confirmation=act in ("send_campaign", "launch_campaign") and not force_execute,
    )

    result = await _dispatch(db, user, agent_u, act, zeus_action, data, force_execute=force_execute)
    if not result.get("executed") and result.get("success"):
        return result
    if result.get("executed") is False and not result.get("needs_approval"):
        pass
    return result


def _map_action_to_zeus_type(action: str) -> str:
    mapping = {
        "get_customers": "list_customers",
        "get_metrics": "get_metrics",
        "get_cashflow": "get_cashflow",
        "send_campaign": "send_campaign",
        "launch_campaign": "send_campaign",
        "create_campaign": "send_campaign",
        "create_customer": "create_customer",
        "generate_invoice": "generate_invoice",
        "generate_model_303": "generate_model_303",
        "get_tax_summary": "get_tax_summary",
        "track_leads": "track_leads",
    }
    return mapping.get(action, action)


async def _dispatch(
    db: Session,
    user: User,
    agent: str,
    action: str,
    zeus_action: ZeusAction,
    payload: Dict[str, Any],
    *,
    force_execute: bool,
) -> Dict[str, Any]:
    from services.zeus_orchestrator_service import execute_action

    # ZEUS
    if action == "create_customer":
        name = str(payload.get("name") or "").strip()
        email = str(payload.get("email") or "").strip()
        if not name or not email:
            return {"success": False, "executed": False, "message": "name y email requeridos."}
        cust = crm_svc.create_customer(
            db, user, CustomerCreate(name=name, email=email, phone=payload.get("phone"))
        )
        return {
            "success": True,
            "executed": True,
            "message": f"Cliente creado: {cust.name} (ID {cust.id})",
            "data": {"customer_id": cust.id},
        }

    if action in ("get_customers", "list_customers"):
        r = orch.execute_list_customers(db, user, zeus_action)
        return r.model_dump()

    if action in ("send_campaign", "launch_campaign", "create_campaign"):
        r = await execute_action(db, user, zeus_action, force_execute=force_execute)
        return r.model_dump()

    if action == "get_cashflow":
        cid = crm_svc.primary_company_id(db, user)
        bal = get_balance(db, company_id=cid)
        summary = get_summary(db, company_id=cid, days=int(payload.get("days") or 30))
        return {
            "success": True,
            "executed": True,
            "message": f"Cashflow balance: {bal:.2f} €",
            "data": {"balance": bal, "summary": summary},
        }

    if action == "get_metrics":
        metrics = get_core_metrics(db, user=user, days=int(payload.get("days") or 30))
        return {
            "success": True,
            "executed": True,
            "message": (
                f"Métricas: revenue {metrics['revenue']}€, staff_cost {metrics['staff_cost']}€, "
                f"product_cost {metrics['product_cost']}€"
            ),
            "data": metrics,
        }

    # RAFAEL
    if action == "generate_invoice":
        invoice_id = payload.get("invoice_id")
        if not invoice_id:
            return {"success": False, "executed": False, "message": "invoice_id requerido."}
        from services.rafael_fiscal_engine_v2 import generate_invoice_pdf_flow

        out = generate_invoice_pdf_flow(db, user=user, invoice_id=int(invoice_id))
        return {"success": True, "executed": True, "message": "Factura PDF generada.", "data": out}

    if action == "generate_model_303":
        year = int(payload.get("year") or 2026)
        quarter = int(payload.get("quarter") or 1)
        from services.rafael_fiscal_engine_v2 import generate_model_303_flow

        out = generate_model_303_flow(
            db, user=user, company_id=crm_svc.primary_company_id(db, user), year=year, quarter=quarter
        )
        return {"success": True, "executed": True, "message": "Modelo 303 generado.", "data": out}

    if action == "get_tax_summary":
        from services.rafael_fiscal_engine_v2 import fetch_period_financials

        cid = crm_svc.primary_company_id(db, user)
        year = int(payload.get("year") or 2026)
        quarter = int(payload.get("quarter") or 1)
        fin = fetch_period_financials(db, company_id=cid, year=year, quarter=quarter)
        return {"success": True, "executed": True, "message": "Resumen fiscal del periodo.", "data": fin}

    # PERSEO
    if action == "track_leads":
        data = track_leads_summary(db, user)
        return {"success": True, "executed": True, "message": f"Leads abiertos: {data['open_leads']}", "data": data}

    if action == "create_campaign":
        preview = orch.preview_send_campaign(db, user, zeus_action)
        return {"success": True, "executed": True, "message": preview.get("message"), "data": preview}

    r = await execute_action(db, user, zeus_action, force_execute=force_execute)
    out = r.model_dump()
    out["executed"] = r.executed
    return out
