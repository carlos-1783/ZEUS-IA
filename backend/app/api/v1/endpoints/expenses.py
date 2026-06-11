"""Gastos (IVA soportado) para modelo 303."""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.expense import Expense
from app.models.user import User
import services.crm_office_service as crm_svc
from services.rafael_fiscal_engine_v2 import assert_user_company_access
from services.zeus_office_mode import require_company_id

router = APIRouter()


class ExpenseCreate(BaseModel):
    company_id: Optional[int] = None
    supplier_name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    issue_date: Optional[datetime] = None
    base_amount: float = Field(..., ge=0)
    tax_amount: float = Field(..., ge=0)
    tax_rate: float = Field(21, ge=0, le=100)
    category: Optional[str] = None
    invoice_ref: Optional[str] = None


class ExpenseOut(BaseModel):
    id: int
    company_id: int
    supplier_name: str
    base_amount: float
    tax_amount: float
    tax_rate: float
    issue_date: Optional[datetime] = None

    class Config:
        from_attributes = True


@router.get("/", response_model=List[ExpenseOut])
def list_expenses(
    company_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    cid = company_id or crm_svc.primary_company_id(db, current_user)
    cid = require_company_id(cid, context="listar gastos")
    assert_user_company_access(db, current_user, cid)
    rows = (
        db.query(Expense)
        .filter(Expense.company_id == cid)
        .order_by(Expense.issue_date.desc())
        .limit(500)
        .all()
    )
    return rows


@router.post("/", response_model=ExpenseOut, status_code=201)
def create_expense(
    body: ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    cid = body.company_id or crm_svc.primary_company_id(db, current_user)
    cid = require_company_id(cid, context="registrar gasto")
    assert_user_company_access(db, current_user, cid)
    if body.base_amount <= 0 and body.tax_amount <= 0:
        raise HTTPException(status_code=422, detail="El gasto debe tener importe mayor que cero.")

    row = Expense(
        company_id=cid,
        supplier_name=body.supplier_name.strip(),
        description=body.description,
        issue_date=body.issue_date or datetime.utcnow(),
        base_amount=body.base_amount,
        tax_amount=body.tax_amount,
        tax_rate=body.tax_rate,
        category=body.category,
        invoice_ref=body.invoice_ref,
        created_by=current_user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
