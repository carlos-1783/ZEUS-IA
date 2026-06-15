"""Cashflow ledger — balance y movimientos reales."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.company import UserCompany
from app.models.user import User
from services.cashflow_ledger_service import get_balance, get_summary

router = APIRouter()


def _primary_company_id(db: Session, user: User) -> Optional[int]:
    link = (
        db.query(UserCompany)
        .filter(UserCompany.user_id == user.id)
        .order_by(UserCompany.id.asc())
        .first()
    )
    return int(link.company_id) if link else None


@router.get("/summary")
def cashflow_summary(
    company_id: Optional[int] = Query(None),
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    cid = company_id or _primary_company_id(db, current_user)
    if not cid:
        raise HTTPException(status_code=400, detail="company_id requerido.")
    return {"success": True, **get_summary(db, company_id=cid, days=days)}


@router.get("/balance")
def cashflow_balance(
    company_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    cid = company_id or _primary_company_id(db, current_user)
    if not cid:
        raise HTTPException(status_code=400, detail="company_id requerido.")
    return {"success": True, "company_id": cid, "balance": get_balance(db, company_id=cid)}
