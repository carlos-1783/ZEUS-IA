from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class PolicyStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ClaimStatus(str, Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class ClaimDocument(BaseModel):
    """Referencia a un fichero ya subido vía POST /api/v1/upload."""

    name: str = Field(..., min_length=1, max_length=255)
    url: str = Field(..., min_length=1, max_length=1000)
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    uploaded_at: Optional[datetime] = None


# --- Policies ---

class InsurancePolicyBase(BaseModel):
    customer_id: int = Field(..., gt=0)
    coverages: Dict[str, Any] = Field(default_factory=dict, description="Estructura libre por ramo")
    insured_risk: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Descripción del bien asegurado")
    premium_amount: Decimal = Field(..., gt=0)
    start_date: date = Field(default_factory=date.today)
    renewal_date: Optional[date] = None
    status: PolicyStatus = PolicyStatus.DRAFT
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class InsurancePolicyCreate(InsurancePolicyBase):
    pass


class InsurancePolicyUpdate(BaseModel):
    coverages: Optional[Dict[str, Any]] = None
    insured_risk: Optional[Dict[str, Any]] = None
    premium_amount: Optional[Decimal] = Field(None, gt=0)
    start_date: Optional[date] = None
    renewal_date: Optional[date] = None
    status: Optional[PolicyStatus] = None
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class InsurancePolicyInDB(InsurancePolicyBase):
    id: int
    company_id: int
    policy_number: str
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class InsurancePolicyResponse(BaseModel):
    success: bool = True
    data: InsurancePolicyInDB


class InsurancePolicyListResponse(BaseModel):
    success: bool = True
    data: List[InsurancePolicyInDB]
    total: int
    page: int
    limit: int
    total_pages: int


# --- Claims ---

class InsuranceClaimBase(BaseModel):
    policy_id: int = Field(..., gt=0)
    claim_date: date = Field(default_factory=date.today)
    description: str = Field(..., min_length=1)
    estimated_amount: Optional[Decimal] = Field(None, ge=0)
    documents: List[ClaimDocument] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class InsuranceClaimCreate(InsuranceClaimBase):
    pass


class InsuranceClaimUpdate(BaseModel):
    status: Optional[ClaimStatus] = None
    resolved_amount: Optional[Decimal] = Field(None, ge=0)
    estimated_amount: Optional[Decimal] = Field(None, ge=0)
    description: Optional[str] = None
    documents: Optional[List[ClaimDocument]] = None

    model_config = ConfigDict(from_attributes=True)


class InsuranceClaimInDB(BaseModel):
    id: int
    policy_id: int
    company_id: int
    claim_date: date
    description: str
    status: ClaimStatus
    estimated_amount: Optional[Decimal] = None
    resolved_amount: Optional[Decimal] = None
    documents: List[ClaimDocument] = Field(default_factory=list)
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class InsuranceClaimResponse(BaseModel):
    success: bool = True
    data: InsuranceClaimInDB


class InsuranceClaimListResponse(BaseModel):
    success: bool = True
    data: List[InsuranceClaimInDB]
    total: int
    page: int
    limit: int
    total_pages: int
