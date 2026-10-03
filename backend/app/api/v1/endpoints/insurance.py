"""Vertical Seguros — endpoints REST reales (Multirriesgo).

Mismo patrón de aislamiento multi-tenant ya validado en el ciclo de
producción del núcleo (ver CICLO_PRODUCCION.md, Ciclo 1: invoices.py /
products.py): auth real vía `app.core.auth.get_current_active_user`
(NUNCA `app.core.security` — bug de audiencia JWT ya diagnosticado) y
filtro de empresa vía `crm_office_service.company_ids_for_user`.
"""

import logging
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.core.module_access import require_module
from app.core.validators_es import validar_nif_cif
from app.db.tenant_context import get_db_scoped, set_tenant_context
from app.models.customer import Customer
from app.models.insurance import ClaimStatus, InsuranceClaim, InsurancePolicy, PolicyBranch, PolicyStatus
from app.models.user import User
from app.schemas.insurance import (
    InsuranceClaimCreate,
    InsuranceClaimInDB,
    InsuranceClaimListResponse,
    InsuranceClaimResponse,
    InsuranceClaimUpdate,
    InsurancePolicyCreate,
    InsurancePolicyInDB,
    InsurancePolicyListResponse,
    InsurancePolicyResponse,
)
import services.crm_office_service as crm_svc
from services.zeus_office_mode import require_company_id

logger = logging.getLogger(__name__)

# Gating real de vertical: hasta que Carlos confirme qué `company_type`
# tendrán las empresas aseguradoras/correduría (ver
# app.core.verticals_registry, entrada "insurance" deliberadamente vacía),
# esta vertical queda cerrada por defecto -- solo accesible para
# superusuario. Aplicado a nivel de router: cubre TODOS los endpoints de
# abajo, no requiere recordar añadirlo endpoint por endpoint (y el test de
# guardia en tests/test_verticals_module_access.py falla si se quita).
router = APIRouter(dependencies=[Depends(require_module("insurance"))])


def _company_ids(db: Session, user: User) -> list:
    return crm_svc.company_ids_for_user(db, user)


def get_policy_or_404(db: Session, policy_id: int, current_user: User) -> InsurancePolicy:
    cids = _company_ids(db, current_user)
    policy = (
        db.query(InsurancePolicy)
        .filter(InsurancePolicy.id == policy_id)
        .filter(InsurancePolicy.company_id.in_(cids) if cids else False)
        .first()
    )
    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Policy with ID {policy_id} not found")
    return policy


def get_claim_or_404(db: Session, claim_id: int, current_user: User) -> InsuranceClaim:
    cids = _company_ids(db, current_user)
    claim = (
        db.query(InsuranceClaim)
        .filter(InsuranceClaim.id == claim_id)
        .filter(InsuranceClaim.company_id.in_(cids) if cids else False)
        .first()
    )
    if not claim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Claim with ID {claim_id} not found")
    return claim


def _generate_policy_number(db: Session) -> str:
    """POL-YYYYMMDD-XXXX, con reintento ante colisión (evita duplicados bajo
    concurrencia; el count-based de invoices.py es solo indicativo, no
    garantiza unicidad real bajo carga concurrente)."""
    for _ in range(5):
        candidate = f"POL-{datetime.utcnow().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"
        exists = db.query(InsurancePolicy.id).filter(InsurancePolicy.policy_number == candidate).first()
        if not exists:
            return candidate
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No se pudo generar un número de póliza único")


# --- Policies ---

@router.get("/policies", response_model=InsurancePolicyListResponse)
def list_policies(
    db: Session = Depends(get_db_scoped),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=1000),
    status_filter: Optional[str] = Query(None, alias="status"),
    branch_filter: Optional[str] = Query(None, alias="branch"),
    customer_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_active_user),
):
    """Lista de pólizas filtrada por empresa del usuario autenticado."""
    cids = _company_ids(db, current_user)
    query = db.query(InsurancePolicy).filter(InsurancePolicy.company_id.in_(cids) if cids else False)

    if status_filter:
        try:
            query = query.filter(InsurancePolicy.status == PolicyStatus(status_filter))
        except ValueError:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid status: {status_filter}")
    if branch_filter:
        try:
            query = query.filter(InsurancePolicy.branch == PolicyBranch(branch_filter))
        except ValueError:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid branch: {branch_filter}")
    if customer_id:
        query = query.filter(InsurancePolicy.customer_id == customer_id)

    total = query.count()
    policies = query.order_by(InsurancePolicy.created_at.desc()).offset(skip).limit(limit).all()

    total_pages = (total + limit - 1) // limit if limit > 0 else 1
    current_page = (skip // limit) + 1 if limit > 0 else 1

    return {
        "success": True,
        "data": policies,
        "total": total,
        "page": current_page,
        "limit": limit,
        "total_pages": total_pages,
    }


@router.post("/policies", response_model=InsurancePolicyResponse, status_code=status.HTTP_201_CREATED)
def create_policy(
    *,
    policy_in: InsurancePolicyCreate,
    db: Session = Depends(get_db_scoped),
    current_user: User = Depends(get_current_active_user),
):
    """Alta de póliza. El customer_id debe pertenecer a la misma empresa del usuario."""
    company_id = crm_svc.primary_company_id(db, current_user)
    require_company_id(company_id, context="alta de póliza")

    customer = (
        db.query(Customer)
        .filter(Customer.id == policy_in.customer_id, Customer.company_id == company_id)
        .first()
    )
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID {policy_in.customer_id} not found",
        )

    # DNI/NIF/CIF real y obligatorio para emitir una póliza (validación
    # server-side no negociable, no solo del frontend). `policy_in.customer_tax_id`
    # ya viene con checksum validado por el schema si se informó; si no se
    # informó, exige que el cliente ya tenga uno válido registrado.
    tax_id_input = policy_in.customer_tax_id
    effective_tax_id = tax_id_input or (customer.tax_id or "").strip().upper() or None
    if not effective_tax_id or not validar_nif_cif(effective_tax_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El cliente necesita un DNI/NIF/CIF válido para emitir una póliza",
        )
    if tax_id_input and tax_id_input != (customer.tax_id or ""):
        customer.tax_id = tax_id_input

    policy_number = _generate_policy_number(db)

    policy = InsurancePolicy(
        company_id=company_id,
        customer_id=policy_in.customer_id,
        policy_number=policy_number,
        branch=PolicyBranch(policy_in.branch.value),
        coverages=policy_in.coverages or {},
        insured_risk=policy_in.insured_risk or {},
        premium_amount=policy_in.premium_amount,
        start_date=policy_in.start_date,
        renewal_date=policy_in.renewal_date,
        status=PolicyStatus(policy_in.status.value),
        notes=policy_in.notes,
        created_by=current_user.id,
    )

    try:
        db.add(policy)
        db.commit()
        # `insurance_policies` tiene RLS fail-closed (migración 0049): el
        # `set_config(..., is_local=true)` de get_db_scoped se resetea solo
        # al hacer commit/rollback (fin de la transacción). Sin re-fijar el
        # contexto aquí, este `db.refresh()` (nueva transacción implícita)
        # se ejecutaría SIN app.current_company_id -> la policy fail-closed
        # esconde la fila que el propio usuario acaba de crear y
        # `db.refresh()` lanza `InvalidRequestError: Could not refresh
        # instance` (confirmado en vivo contra Postgres real con zeus_app).
        set_tenant_context(db, company_id, user_id=current_user.id, user_email=current_user.email)
        db.refresh(policy)
    except Exception:
        db.rollback()
        logger.exception("create_policy: fallo al persistir póliza company_id=%s", company_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No se pudo crear la póliza")

    logger.info(
        "insurance_policy_created policy_id=%s policy_number=%s branch=%s company_id=%s user_id=%s",
        policy.id, policy.policy_number, policy.branch.value, company_id, current_user.id,
    )

    return {"success": True, "data": policy}


@router.get("/policies/{policy_id}", response_model=InsurancePolicyResponse)
def get_policy(
    policy_id: int = Path(..., description="ID of the policy to retrieve"),
    db: Session = Depends(get_db_scoped),
    current_user: User = Depends(get_current_active_user),
):
    policy = get_policy_or_404(db, policy_id, current_user)
    return {"success": True, "data": policy}


@router.get("/policies/{policy_id}/claims", response_model=InsuranceClaimListResponse)
def list_policy_claims(
    policy_id: int = Path(..., description="ID of the policy"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=1000),
    db: Session = Depends(get_db_scoped),
    current_user: User = Depends(get_current_active_user),
):
    """Siniestros de una póliza — 404 si la póliza no pertenece a la empresa del usuario."""
    policy = get_policy_or_404(db, policy_id, current_user)

    query = db.query(InsuranceClaim).filter(InsuranceClaim.policy_id == policy.id)
    total = query.count()
    claims = query.order_by(InsuranceClaim.created_at.desc()).offset(skip).limit(limit).all()

    total_pages = (total + limit - 1) // limit if limit > 0 else 1
    current_page = (skip // limit) + 1 if limit > 0 else 1

    return {
        "success": True,
        "data": claims,
        "total": total,
        "page": current_page,
        "limit": limit,
        "total_pages": total_pages,
    }


# --- Claims ---

@router.post("/claims", response_model=InsuranceClaimResponse, status_code=status.HTTP_201_CREATED)
def create_claim(
    *,
    claim_in: InsuranceClaimCreate,
    db: Session = Depends(get_db_scoped),
    current_user: User = Depends(get_current_active_user),
):
    """Apertura de siniestro sobre una póliza de la empresa del usuario (404 si no)."""
    policy = get_policy_or_404(db, claim_in.policy_id, current_user)
    # Capturados en variables ANTES del commit: `insurance_policies` también
    # es fail-closed, y tras el commit de más abajo `policy` (cargado en una
    # transacción anterior) queda expirado como cualquier otro objeto de la
    # sesión -- acceder a `policy.id`/`policy.company_id` DESPUÉS del commit
    # (p. ej. como argumento de `set_tenant_context`, evaluado antes de que
    # la llamada se ejecute) dispara una recarga SIN contexto de tenant
    # todavía fijado y rompe con `ObjectDeletedError` (confirmado en vivo
    # contra Postgres real con zeus_app).
    policy_id = policy.id
    policy_company_id = policy.company_id

    claim = InsuranceClaim(
        policy_id=policy_id,
        company_id=policy_company_id,
        claim_date=claim_in.claim_date,
        description=claim_in.description,
        status=ClaimStatus.OPEN,
        estimated_amount=claim_in.estimated_amount,
        documents=[d.model_dump(mode="json") for d in (claim_in.documents or [])],
        created_by=current_user.id,
    )

    try:
        db.add(claim)
        db.commit()
        # Mismo motivo que en create_policy: `insurance_claims` es fail-closed
        # y `is_local=true` resetea el contexto al hacer commit -> hay que
        # re-fijarlo (con la variable capturada arriba, no con `policy.*`)
        # antes de este `db.refresh()`.
        set_tenant_context(db, policy_company_id, user_id=current_user.id, user_email=current_user.email)
        db.refresh(claim)
    except Exception:
        db.rollback()
        logger.exception("create_claim: fallo al persistir siniestro policy_id=%s", policy_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No se pudo abrir el siniestro")

    logger.info(
        "insurance_claim_created claim_id=%s policy_id=%s company_id=%s user_id=%s",
        claim.id, policy_id, policy_company_id, current_user.id,
    )

    return {"success": True, "data": claim}


@router.get("/claims", response_model=InsuranceClaimListResponse)
def list_claims(
    db: Session = Depends(get_db_scoped),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=1000),
    status_filter: Optional[str] = Query(None, alias="status"),
    policy_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_active_user),
):
    """Lista de siniestros filtrada por empresa del usuario autenticado."""
    cids = _company_ids(db, current_user)
    query = db.query(InsuranceClaim).filter(InsuranceClaim.company_id.in_(cids) if cids else False)

    if status_filter:
        try:
            query = query.filter(InsuranceClaim.status == ClaimStatus(status_filter))
        except ValueError:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid status: {status_filter}")
    if policy_id:
        query = query.filter(InsuranceClaim.policy_id == policy_id)

    total = query.count()
    claims = query.order_by(InsuranceClaim.created_at.desc()).offset(skip).limit(limit).all()

    total_pages = (total + limit - 1) // limit if limit > 0 else 1
    current_page = (skip // limit) + 1 if limit > 0 else 1

    return {
        "success": True,
        "data": claims,
        "total": total,
        "page": current_page,
        "limit": limit,
        "total_pages": total_pages,
    }


@router.get("/claims/{claim_id}", response_model=InsuranceClaimResponse)
def get_claim(
    claim_id: int = Path(..., description="ID of the claim to retrieve"),
    db: Session = Depends(get_db_scoped),
    current_user: User = Depends(get_current_active_user),
):
    claim = get_claim_or_404(db, claim_id, current_user)
    return {"success": True, "data": claim}


@router.patch("/claims/{claim_id}", response_model=InsuranceClaimResponse)
def update_claim(
    *,
    claim_id: int = Path(..., description="ID of the claim to update"),
    claim_in: InsuranceClaimUpdate,
    db: Session = Depends(get_db_scoped),
    current_user: User = Depends(get_current_active_user),
):
    """Cambia estado/importe resuelto de un siniestro. 404 si no pertenece a la empresa del usuario."""
    claim = get_claim_or_404(db, claim_id, current_user)

    update_data = claim_in.model_dump(exclude_unset=True)

    if "status" in update_data and update_data["status"] is not None:
        claim.status = ClaimStatus(update_data["status"].value if hasattr(update_data["status"], "value") else update_data["status"])
    if "resolved_amount" in update_data:
        claim.resolved_amount = update_data["resolved_amount"]
    if "estimated_amount" in update_data:
        claim.estimated_amount = update_data["estimated_amount"]
    if "description" in update_data and update_data["description"]:
        claim.description = update_data["description"]
    if "documents" in update_data and update_data["documents"] is not None:
        claim.documents = [d if isinstance(d, dict) else d.model_dump(mode="json") for d in update_data["documents"]]

    claim.updated_at = datetime.utcnow()
    # Capturado ANTES del commit (atributo ya cargado por get_claim_or_404):
    # tras el commit, cualquier acceso a un atributo expirado de `claim`
    # dispararía una query sin contexto de tenant fijado (ver más abajo).
    claim_company_id = claim.company_id

    try:
        db.commit()
        # Mismo motivo que en create_policy/create_claim: `insurance_claims`
        # es fail-closed y el contexto de tenant se resetea al hacer commit
        # (is_local=true) -> hay que re-fijarlo antes de este `db.refresh()`.
        set_tenant_context(db, claim_company_id, user_id=current_user.id, user_email=current_user.email)
        db.refresh(claim)
    except Exception:
        db.rollback()
        logger.exception("update_claim: fallo al actualizar siniestro claim_id=%s", claim_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No se pudo actualizar el siniestro")

    logger.info(
        "insurance_claim_updated claim_id=%s status=%s company_id=%s user_id=%s",
        claim.id, claim.status.value, claim.company_id, current_user.id,
    )

    return {"success": True, "data": claim}
