from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session, joinedload

# Import models
from app.models.user import User

# Import models and schemas
from app.models.customer import Customer, ContactPerson
from app.schemas.customer import (
    CustomerCreate, CustomerUpdate, CustomerOut, 
    ContactPersonCreate, ContactPersonUpdate, ContactPersonOut,
    CustomerResponse, ContactPersonResponse, CustomerListResponse
)

# Import core and db
from app.core.auth import get_current_active_user
from app.db.session import get_db

# Import logging
import logging

import services.crm_office_service as crm_svc

# Configurar logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get(
    "/test",
    response_model=Dict[str, str],
    status_code=status.HTTP_200_OK,
    summary="Endpoint de prueba",
    description="Endpoint mínimo para probar el enrutamiento sin dependencias.",
    response_description="Mensaje de prueba",
    responses={
        200: {"description": "Prueba exitosa"},
    },
)
async def test_endpoint() -> Dict[str, str]:
    """
    Endpoint de prueba simple que no depende de la base de datos.
    """
    return {
        "status": "success", 
        "message": "¡Endpoint de prueba funcionando correctamente!"
    }

def get_customer_or_404(
    db: Session,
    customer_id: int,
    current_user: User,
) -> Customer:
    """Cliente CRM en ámbito multi-empresa / propietario."""
    crm_svc.resolve_customer(db, current_user, customer_id)
    row = (
        db.query(Customer)
        .options(joinedload(Customer.contacts))
        .filter(Customer.id == customer_id)
        .first()
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID {customer_id} not found",
        )
    return row

@router.get(
    "",
    response_model=CustomerListResponse,
    operation_id="customers_list_api_v1",
    summary="List customers (tenant-scoped)",
)
async def list_customers(
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    rows = crm_svc.list_customers(db, current_user)
    total = len(rows)
    start = (page - 1) * limit
    page_rows = rows[start : start + limit]
    total_pages = max(1, (total + limit - 1) // limit) if total else 1
    return CustomerListResponse(
        success=True,
        message="OK",
        data=[CustomerOut.model_validate(r) for r in page_rows],
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
    )

@router.post(
    "",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="customers_create_api_v1",
    summary="Create Customer",
    description="Create a new customer with the provided details.",
    response_description="The created customer"
)
async def create_customer(
    *,
    db: Session = Depends(get_db),
    customer_in: CustomerCreate,
    current_user: User = Depends(get_current_active_user),
) -> CustomerResponse:
    """Alta de cliente CRM con empresa y email único por empresa."""
    try:
        customer = crm_svc.create_customer(db, current_user, customer_in)
        customer_out = CustomerOut.model_validate(customer)
        return CustomerResponse(
            success=True,
            message="Customer created successfully",
            data=customer_out,
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.exception("create_customer")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating customer: {str(e)}",
        )

@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    operation_id="customers_get_api_v1",
    summary="Get Customer",
    description="Retrieve a specific customer by ID.",
    response_description="The requested customer"
)
def get_customer(
    customer_id: int = Path(..., description="ID of the customer to retrieve"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> CustomerResponse:
    """
    Get a specific customer by ID
    """
    customer = get_customer_or_404(db, customer_id, current_user)
    customer_out = CustomerOut.model_validate(customer)
    return CustomerResponse(
        success=True,
        data=customer_out
    )

@router.put(
    "/{customer_id}",
    response_model=CustomerResponse,
    operation_id="customers_update_api_v1",
    summary="Update Customer",
    description="Update an existing customer with the provided details.",
    response_description="The updated customer"
)
def update_customer(
    *,
    customer_id: int = Path(..., description="ID of the customer to update"),
    customer_in: CustomerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Update a customer
    """
    from datetime import datetime

    customer = get_customer_or_404(db, customer_id, current_user)
    update_data = customer_in.model_dump(exclude_unset=True, exclude={"contacts"})
    new_email = update_data.get("email")
    if new_email is not None:
        scope_cid = customer.company_id or crm_svc.primary_company_id(db, current_user)
        crm_svc.assert_email_unique_in_company(
            db, scope_cid, new_email, exclude_customer_id=customer.id
        )
    for field, value in update_data.items():
        if field == "metadata":
            setattr(customer, "metadata_", value)
        else:
            setattr(customer, field, value)
    customer.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(customer)

    log_cid = customer.company_id or crm_svc.primary_company_id(db, current_user)
    if log_cid is not None:
        crm_svc.log_activity(
            db,
            company_id=log_cid,
            user_id=current_user.id,
            customer_id=customer.id,
            record_id=None,
            action="customer_updated",
            summary=f"Cliente actualizado: {customer.name}",
            payload={"customer_id": customer.id},
        )

    customer_out = CustomerOut.model_validate(customer)
    return CustomerResponse(
        success=True,
        data=customer_out,
    )

@router.delete(
    "/{customer_id}",
    response_model=CustomerResponse,
    status_code=status.HTTP_200_OK,
    operation_id="customers_delete_api_v1",
    summary="Delete Customer",
    description="Delete a customer and all associated contact persons.",
    response_description="The deleted customer"
)
def delete_customer(
    customer_id: int = Path(..., description="ID of the customer to delete"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Delete a customer and all related contacts
    """
    customer = get_customer_or_404(db, customer_id, current_user)
    customer_out = CustomerOut.model_validate(customer)
    log_cid = customer.company_id or crm_svc.primary_company_id(db, current_user)
    name = customer.name
    cust_id = customer.id
    try:
        if log_cid is not None:
            crm_svc.log_activity(
                db,
                company_id=log_cid,
                user_id=current_user.id,
                customer_id=cust_id,
                record_id=None,
                action="customer_deleted",
                summary=f"Cliente eliminado: {name}",
                payload={"customer_id": cust_id},
                commit=False,
            )
        db.query(ContactPerson).filter(ContactPerson.customer_id == cust_id).delete(
            synchronize_session=False
        )
        db.query(Customer).filter(Customer.id == cust_id).delete(synchronize_session=False)
        db.commit()
        return CustomerResponse(
            success=True,
            message="Customer deleted successfully",
            data=customer_out,
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting customer: {str(e)}",
        )

# Contact person endpoints
@router.post(
    "/{customer_id}/contacts",
    response_model=ContactPersonResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="customers_create_contact_api_v1",
    summary="Create Contact Person",
    description="Add a new contact person to a customer.",
    response_description="The created contact person"
)
def create_contact_person(
    *,
    customer_id: int = Path(..., description="ID of the customer to add the contact to"),
    contact_in: ContactPersonCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Add a new contact person to a customer.
    
    - **customer_id**: ID of the customer to add the contact to
    - **contact_in**: Contact person details
    """
    from sqlalchemy.exc import SQLAlchemyError
    
    # Verificar que el cliente existe y el usuario tiene acceso
    customer = get_customer_or_404(db, customer_id, current_user)
    
    try:
        # Si se está estableciendo como contacto principal, quitar el estado de los demás
        if contact_in.is_primary:
            db.query(ContactPerson).filter(
                ContactPerson.customer_id == customer_id,
                ContactPerson.is_primary == True
            ).update({"is_primary": False})
            db.flush()  # Aplicar cambios sin hacer commit
        
        # Crear el nuevo contacto
        contact_data = contact_in.model_dump()
        contact = ContactPerson(customer_id=customer_id, **contact_data)
        
        db.add(contact)
        db.commit()
        db.refresh(contact)
        
        # Convertir a modelo Pydantic para la respuesta
        contact_out = ContactPersonOut.model_validate(contact)
        return ContactPersonResponse(
            success=True,
            message="Contact person created successfully",
            data=contact_out
        )
        
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating contact: {str(e)}"
        )

@router.put(
    "/{customer_id}/contacts/{contact_id}",
    response_model=ContactPersonResponse,
    operation_id="actualizar_contacto_cliente_api_v1",
    summary="Update Contact Person",
    description="Update an existing contact person's details.",
    response_description="The updated contact person"
)
def update_contact_person(
    *,
    customer_id: int = Path(..., description="ID of the customer to update"),
    contact_id: int = Path(..., description="ID of the contact person to update"),
    contact_in: ContactPersonUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Update an existing contact person.
    
    - **customer_id**: ID of the customer to update
    - **contact_id**: ID of the contact person to update
    - **contact_in**: Updated contact person details
    """
    from sqlalchemy.exc import SQLAlchemyError
    from app.schemas.customer import ContactPersonInDB
    
    # Verificar que el cliente existe y el usuario tiene acceso
    customer = get_customer_or_404(db, customer_id, current_user)
    
    # Obtener el contacto existente
    contact = db.query(ContactPerson).filter(
        ContactPerson.id == contact_id,
        ContactPerson.customer_id == customer_id
    ).first()
    
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contact with ID {contact_id} not found for customer {customer_id}"
        )
    
    try:
        # Si se está estableciendo como contacto principal, quitar el estado de los demás
        if contact_in.is_primary and not contact.is_primary:
            db.query(ContactPerson).filter(
                ContactPerson.customer_id == customer_id,
                ContactPerson.id != contact_id,
                ContactPerson.is_primary == True
            ).update({"is_primary": False})
            db.flush()
        
        # Actualizar solo los campos proporcionados
        update_data = contact_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(contact, field, value)
        
        # Guardar cambios
        db.commit()
        db.refresh(contact)
        
        # Convertir a modelo Pydantic para la respuesta
        contact_out = ContactPersonOut.model_validate(contact)
        return ContactPersonResponse(
            success=True,
            message="Contact person updated successfully",
            data=contact_out
        )
        
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating contact: {str(e)}"
        )

@router.delete(
    "/{customer_id}/contacts/{contact_id}",
    response_model=ContactPersonResponse,
    operation_id="eliminar_contacto_cliente_api_v1",
    summary="Delete Contact Person",
    description="Delete a contact person by ID.",
    response_description="The deleted contact person"
)
def delete_contact_person(
    customer_id: int = Path(..., description="ID of the customer"),
    contact_id: int = Path(..., description="ID of the contact person to delete"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete a contact person by ID.
    
    - **contact_id**: ID of the contact person to delete
    """
    from sqlalchemy.exc import SQLAlchemyError
    
    # Verificar que el cliente existe y el usuario tiene acceso
    customer = get_customer_or_404(db, customer_id, current_user)
    
    # Obtener el contacto existente
    contact = db.query(ContactPerson).filter(
        ContactPerson.id == contact_id,
        ContactPerson.customer_id == customer_id
    ).first()
    
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contact with ID {contact_id} not found for customer {customer_id}"
        )
    
    try:
        # Convertir a modelo Pydantic para la respuesta antes de eliminar
        contact_out = ContactPersonOut.model_validate(contact)
        
        # Eliminar el contacto
        db.delete(contact)
        db.commit()
        
        return ContactPersonResponse(
            success=True,
            message="Contact person deleted successfully",
            data=contact_out
        )
        
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting contact: {str(e)}"
        )
