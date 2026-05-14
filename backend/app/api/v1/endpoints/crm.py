"""CRM oficina: clientes en ámbito empresa, expedientes, cobros vía TPV fiscal, actividad."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.customer import CustomerOut
from app.schemas.crm_office import (
    CrmActivityOut,
    CrmListResponse,
    CustomerRecordCreate,
    CustomerRecordOut,
    CustomerRecordUpdate,
    RecordChargeIn,
    RecordChargeOut,
)
import services.crm_office_service as crm_svc

router = APIRouter()


@router.get("/customers", response_model=CrmListResponse)
def crm_list_customers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    rows = crm_svc.list_customers(db, current_user)
    return CrmListResponse(success=True, data=[CustomerOut.model_validate(r) for r in rows])


@router.get(
    "/customers/{customer_id}/records",
    response_model=CrmListResponse,
)
def crm_list_records(
    customer_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    rows = crm_svc.list_records(db, current_user, customer_id)
    return CrmListResponse(success=True, data=[CustomerRecordOut.model_validate(r) for r in rows])


@router.post(
    "/customers/{customer_id}/records",
    response_model=CustomerRecordOut,
    status_code=status.HTTP_201_CREATED,
)
def crm_create_record(
    customer_id: int = Path(..., ge=1),
    body: CustomerRecordCreate = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    rec = crm_svc.create_record(
        db,
        current_user,
        customer_id,
        title=body.title,
        status=body.status,
        amount=body.amount,
        notes=body.notes,
    )
    return CustomerRecordOut.model_validate(rec)


@router.patch("/records/{record_id}", response_model=CustomerRecordOut)
def crm_update_record(
    record_id: int = Path(..., ge=1),
    body: CustomerRecordUpdate = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    rec = crm_svc.update_record(
        db,
        current_user,
        record_id,
        title=body.title,
        status=body.status,
        amount=body.amount,
        notes=body.notes,
    )
    return CustomerRecordOut.model_validate(rec)


@router.delete("/records/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def crm_delete_record(
    record_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    crm_svc.delete_record(db, current_user, record_id)
    return None


@router.post("/records/{record_id}/charge", response_model=RecordChargeOut)
def crm_register_charge(
    record_id: int = Path(..., ge=1),
    body: RecordChargeIn = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    out = crm_svc.register_record_charge(
        db,
        current_user,
        record_id,
        base_amount=body.base_amount,
        payment_method=body.payment_method,
        description=body.description or "",
        iva_rate=body.iva_rate,
        consumption_type=body.consumption_type,
    )
    return RecordChargeOut.model_validate(out)


@router.get("/customers/{customer_id}/activity", response_model=CrmListResponse)
def crm_list_activity(
    customer_id: int = Path(..., ge=1),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    rows = crm_svc.list_activity_for_customer(db, current_user, customer_id, limit=limit)
    return CrmListResponse(success=True, data=[CrmActivityOut.model_validate(r) for r in rows])
