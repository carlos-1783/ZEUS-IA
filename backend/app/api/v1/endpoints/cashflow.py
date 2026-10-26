"""Cashflow ledger — balance y movimientos reales."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
import services.crm_office_service as crm_svc
from services.cashflow_ledger_service import get_balance, get_summary

router = APIRouter()


@router.get("/summary")
def cashflow_summary(
    company_id: Optional[int] = Query(None),
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    # Empresa de la sesion; un company_id ajeno -> 403 (antes devolvia el saldo real de la otra empresa
    # con la app como postgres, o un 200 a cero con RLS).
    cid = crm_svc.resolve_company_for_user(db, current_user, company_id, context="cashflow")
    return {"success": True, **get_summary(db, company_id=cid, days=days)}


@router.get("/balance")
def cashflow_balance(
    company_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    cid = crm_svc.resolve_company_for_user(db, current_user, company_id, context="cashflow")
    return {"success": True, "company_id": cid, "balance": get_balance(db, company_id=cid)}
