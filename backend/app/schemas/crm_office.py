"""Esquemas API CRM oficina (expedientes, cobro, actividad)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CustomerRecordCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    status: str = Field(default="open", max_length=32)
    amount: Decimal = Field(default=Decimal("0"))
    notes: Optional[str] = None


class CustomerRecordUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    status: Optional[str] = Field(None, max_length=32)
    amount: Optional[Decimal] = None
    notes: Optional[str] = None


class CustomerRecordOut(BaseModel):
    id: int
    company_id: int
    customer_id: int
    title: str
    status: str
    amount: Decimal
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CrmActivityOut(BaseModel):
    id: int
    company_id: int
    user_id: Optional[int] = None
    customer_id: Optional[int] = None
    customer_record_id: Optional[int] = None
    action: str
    summary: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class RecordChargeIn(BaseModel):
    base_amount: Decimal = Field(..., gt=Decimal("0"))
    payment_method: str = Field(..., min_length=2, max_length=32)
    description: Optional[str] = Field(None, max_length=200)
    iva_rate: float = Field(default=21.0, ge=0, le=100)
    consumption_type: str = Field(default="onsite", max_length=32)


class RecordChargeOut(BaseModel):
    success: bool
    tpv_sale_id: int
    ticket_id: str
    customer_id: int
    customer_record_id: int


class CrmListResponse(BaseModel):
    success: bool = True
    data: List[Any] = []
