from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.validators_es import validar_nif_cif


class PolicyStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class PolicyBranch(str, Enum):
    """Ramo de la póliza — piloto Mati (agente exclusiva Catalana Occidente,
    sin campo de aseguradora emisora)."""

    HOGAR = "hogar"
    COMUNIDAD = "comunidad"
    COCHE = "coche"
    VIDA = "vida"
    DECESOS = "decesos"
    SALUD = "salud"


# Campos mínimos obligatorios dentro de `insured_risk` por ramo (valor no
# vacío). Hogar, Comunidad y Decesos no tienen campos adicionales
# obligatorios más allá de lo que ya exista genéricamente en
# `insured_risk`/`coverages`.
REQUIRED_INSURED_RISK_FIELDS: Dict[str, List[str]] = {
    PolicyBranch.COCHE.value: ["matricula", "conductor_habitual", "marca_modelo"],
    PolicyBranch.VIDA.value: ["beneficiario", "capital_asegurado"],
    PolicyBranch.SALUD.value: ["numero_asegurados", "cuadro_medico"],
}


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
    branch: PolicyBranch = Field(..., description="Ramo: hogar, comunidad, coche, vida, decesos, salud")
    coverages: Dict[str, Any] = Field(default_factory=dict, description="Estructura libre por ramo")
    insured_risk: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Descripción del bien asegurado / campos específicos del ramo")
    premium_amount: Decimal = Field(..., gt=0)
    start_date: date = Field(default_factory=date.today)
    renewal_date: Optional[date] = None
    status: PolicyStatus = PolicyStatus.DRAFT
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class InsurancePolicyCreate(InsurancePolicyBase):
    # DNI/NIF/CIF real del cliente. Opcional en el payload solo si el
    # cliente ya tiene uno válido registrado (Customer.tax_id); si se
    # informa aquí, se valida con checksum real y se persiste sobre el
    # cliente. Validación server-side no negociable: sin un DNI/NIF/CIF
    # válido (aquí o ya en el cliente) no se puede emitir la póliza.
    customer_tax_id: Optional[str] = Field(None, max_length=50, description="DNI/NIF/CIF del cliente")

    @field_validator("customer_tax_id")
    @classmethod
    def _validate_customer_tax_id(cls, v: Optional[str]) -> Optional[str]:
        if v is None or not v.strip():
            return None
        if not validar_nif_cif(v):
            raise ValueError("DNI/NIF/CIF no válido (formato o dígito/letra de control incorrecto)")
        return v.strip().upper()

    @model_validator(mode="after")
    def _validate_branch_fields(self) -> "InsurancePolicyCreate":
        required = REQUIRED_INSURED_RISK_FIELDS.get(self.branch.value)
        if required:
            risk = self.insured_risk or {}
            missing = [f for f in required if not str(risk.get(f) or "").strip()]
            if missing:
                raise ValueError(
                    f"Faltan campos obligatorios para el ramo '{self.branch.value}' en insured_risk: {', '.join(missing)}"
                )
        return self


class InsurancePolicyUpdate(BaseModel):
    branch: Optional[PolicyBranch] = None
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
