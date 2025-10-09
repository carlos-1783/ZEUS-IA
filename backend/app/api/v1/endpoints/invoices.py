from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from datetime import date, datetime

from app.db.session import get_db
from app.models.erp import Invoice, InvoiceItem, Payment, Product, InventoryMovement, InventoryMovementType
from app.schemas.erp import (
    InvoiceCreate, InvoiceUpdate, InvoiceInDB, InvoiceResponse, InvoiceListResponse,
    InvoiceItemCreate, InvoiceItemInDB,
    PaymentCreate, PaymentInDB, PaymentResponse,
    InvoiceStatus, InvoiceType, PaymentStatus, PaymentMethod
)
from app.core.security import get_current_active_user
from app.models.user import User

router = APIRouter()

def get_invoice_or_404(
    db: Session,
    invoice_id: int,
    current_user: User
) -> InvoiceInDB:
    """
    Obtiene una factura por ID o lanza una excepción 404 si no se encuentra.
    
    Args:
        db: Sesión de base de datos
        invoice_id: ID de la factura a buscar
        current_user: Usuario autenticado
        
    Returns:
        InvoiceInDB: El objeto de la factura en formato Pydantic si se encuentra
        
    Raises:
        HTTPException: 404 si la factura no existe
        HTTPException: 403 si el usuario no tiene permisos
    """
    from fastapi import HTTPException, status
    from sqlalchemy.orm import joinedload
    
    # Optimizar la consulta cargando relaciones comunes
    invoice = db.query(Invoice).options(
        joinedload(Invoice.customer),
        joinedload(Invoice.items),
        joinedload(Invoice.payments)
    ).filter(
        Invoice.id == invoice_id
    ).first()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice with ID {invoice_id} not found"
        )
    
    # Verificar que el usuario tenga acceso a la factura
    # Aquí podrías agregar lógica de autorización adicional según tus necesidades
    # Por ejemplo, verificar si el usuario pertenece a la misma organización
    
    # Convertir el modelo SQLAlchemy a Pydantic
    return InvoiceInDB.model_validate(invoice)

def calculate_invoice_totals(invoice: Invoice, db: Session) -> Dict[str, float]:
    """Calculate invoice subtotal, tax, and total"""
    subtotal = 0.0
    tax_amount = 0.0
    
    for item in invoice.items:
        item_subtotal = item.quantity * item.unit_price
        item_tax = item_subtotal * (item.tax_rate / 100.0)
        item_total = item_subtotal + item_tax - item.discount
        
        subtotal += item_subtotal
        tax_amount += item_tax
    
    total = subtotal + tax_amount - invoice.discount_amount
    
    # Calculate amount paid
    amount_paid = sum(payment.amount for payment in invoice.payments if payment.status == PaymentStatus.COMPLETED)
    amount_due = max(0.0, total - amount_paid)
    
    return {
        "subtotal": subtotal,
        "tax_amount": tax_amount,
        "total": total,
        "amount_paid": amount_paid,
        "amount_due": amount_due
    }

@router.get("/", response_model=InvoiceListResponse)
def list_invoices(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, le=1000, description="Maximum number of records to return"),
    customer_id: Optional[int] = Query(None, description="Filter by customer ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    invoice_type: Optional[str] = Query(None, description="Filter by invoice type"),
    start_date: Optional[date] = Query(None, description="Filter by issue date (greater than or equal)"),
    end_date: Optional[date] = Query(None, description="Filter by issue date (less than or equal)"),
    current_user: User = Depends(get_current_active_user)
):
    """
    List all invoices with optional filtering and pagination
    """
    query = db.query(Invoice)
    
    # Apply filters
    if customer_id:
        query = query.filter(Invoice.customer_id == customer_id)
        
    if status:
        query = query.filter(Invoice.status == status)
        
    if invoice_type:
        query = query.filter(Invoice.invoice_type == invoice_type)
        
    if start_date:
        query = query.filter(Invoice.issue_date >= start_date)
        
    if end_date:
        query = query.filter(Invoice.issue_date <= end_date)
    
    # Get total count for pagination
    total = query.count()
    
    # Apply pagination and ordering
    invoices = query.order_by(Invoice.issue_date.desc())\
                   .offset(skip)\
                   .limit(limit)\
                   .all()
    
    # Calculate pagination metadata
    total_pages = (total + limit - 1) // limit if limit > 0 else 1
    current_page = (skip // limit) + 1 if limit > 0 else 1
    
    return {
        "success": True,
        "data": invoices,
        "total": total,
        "page": current_page,
        "limit": limit,
        "total_pages": total_pages
    }

@router.post("/", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
def create_invoice(
    *,
    invoice_in: InvoiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Create a new invoice
    """
    # Check if customer exists if specified
    if invoice_in.customer_id:
        from app.models.customer import Customer
        customer = db.query(Customer).filter(Customer.id == invoice_in.customer_id).first()
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Customer with ID {invoice_in.customer_id} not found"
            )
    
    # Generate invoice number (in a real app, use a proper sequence)
    invoice_number = f"INV-{datetime.utcnow().strftime('%Y%m%d')}-{db.query(func.count(Invoice.id)).scalar() + 1}"
    
    # Create invoice
    invoice_data = invoice_in.dict(exclude={"items"}, exclude_unset=True)
    invoice = Invoice(
        **invoice_data,
        invoice_number=invoice_number,
        created_by=current_user.id
    )
    
    db.add(invoice)
    db.flush()  # Get the invoice ID for items
    
    # Add items
    for item_data in invoice_in.items:
        item = InvoiceItem(
            invoice_id=invoice.id,
            **item_data.dict()
        )
        db.add(item)
        
        # If this is a product, update inventory if needed
        if item.product_id and invoice_in.status == InvoiceStatus.PAID:
            # In a real app, you'd want to check if inventory tracking is enabled
            # and handle variants properly
            product = db.query(Product).filter(Product.id == item.product_id).first()
            if product and product.track_inventory:
                movement = InventoryMovement(
                    product_id=product.id,
                    movement_type=InventoryMovementType.SALE,
                    quantity=-item.quantity,  # Negative for sales
                    unit_cost=product.cost or 0,
                    reference=f"Invoice #{invoice_number}",
                    created_by=current_user.id
                )
                db.add(movement)
                
                # Update stock level
                product.quantity_on_hand = max(0, product.quantity_on_hand - item.quantity)
    
    # Calculate and update totals
    totals = calculate_invoice_totals(invoice, db)
    for key, value in totals.items():
        setattr(invoice, key, value)
    
    db.commit()
    db.refresh(invoice)
    
    return {"success": True, "data": invoice}

@router.get("/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(
    invoice_id: int = Path(..., description="ID of the invoice to retrieve"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get a specific invoice by ID
    """
    invoice = get_invoice_or_404(db, invoice_id, current_user)
    return {"success": True, "data": invoice}

@router.put("/{invoice_id}", response_model=InvoiceResponse)
def update_invoice(
    *,
    invoice_id: int = Path(..., description="ID of the invoice to update"),
    invoice_in: dict = Body(..., description="Invoice fields to update"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Update an invoice
    """
    invoice = get_invoice_or_404(db, invoice_id, current_user)
    
    # Prevent updates to certain fields
    for field in ["id", "invoice_number", "created_at", "created_by"]:
        invoice_in.pop(field, None)
    
    # Update fields
    for field, value in invoice_in.items():
        if hasattr(invoice, field):
            setattr(invoice, field, value)
    
    # Recalculate totals if items were updated
    if "items" in invoice_in:
        # In a real app, you'd want to handle item updates more carefully
        # This is a simplified version that just recalculates totals
        totals = calculate_invoice_totals(invoice, db)
        for key, value in totals.items():
            setattr(invoice, key, value)
    
    invoice.updated_at = func.now()
    db.commit()
    db.refresh(invoice)
    
    return {"success": True, "data": invoice}

@router.post("/{invoice_id}/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def create_payment(
    *,
    invoice_id: int = Path(..., description="ID of the invoice to pay"),
    payment_in: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Record a payment for an invoice
    """
    invoice = get_invoice_or_404(db, invoice_id, current_user)
    
    # Create payment
    payment = Payment(
        **payment_in.dict(),
        invoice_id=invoice_id,
        created_by=current_user.id
    )
    
    db.add(payment)
    
    # Update invoice status based on payment
    totals = calculate_invoice_totals(invoice, db)
    
    if payment.status == PaymentStatus.COMPLETED:
        if totals["amount_due"] <= 0:
            invoice.status = InvoiceStatus.PAID
        elif totals["amount_paid"] > 0:
            invoice.status = InvoiceStatus.PARTIALLY_PAID
    
    # Update invoice amounts
    for key, value in totals.items():
        setattr(invoice, key, value)
    
    db.commit()
    db.refresh(payment)
    
    return {"success": True, "data": payment}

@router.get("/{invoice_id}/payments", response_model=List[PaymentInDB])
def list_invoice_payments(
    invoice_id: int = Path(..., description="ID of the invoice"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    List all payments for an invoice
    """
    # Verify invoice exists
    invoice = get_invoice_or_404(db, invoice_id, current_user)
    
    return invoice.payments

@router.post("/{invoice_id}/send", response_model=InvoiceResponse)
def send_invoice(
    invoice_id: int = Path(..., description="ID of the invoice to send"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Mark an invoice as sent
    """
    invoice = get_invoice_or_404(db, invoice_id, current_user)
    
    if invoice.status != InvoiceStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft invoices can be sent"
        )
    
    invoice.status = InvoiceStatus.SENT
    invoice.sent_at = func.now()
    
    # In a real app, you would also send the invoice via email here
    
    db.commit()
    db.refresh(invoice)
    
    return {"success": True, "data": invoice}

@router.post("/{invoice_id}/void", response_model=InvoiceResponse)
def void_invoice(
    invoice_id: int = Path(..., description="ID of the invoice to void"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Void an invoice
    """
    invoice = get_invoice_or_404(db, invoice_id, current_user)
    
    if invoice.status == InvoiceStatus.VOID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice is already void"
        )
    
    if invoice.status == InvoiceStatus.PAID:
        # In a real app, you might want to issue a refund
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot void a paid invoice"
        )
    
    # Reverse inventory movements if needed
    if invoice.status in [InvoiceStatus.PAID, InvoiceStatus.PARTIALLY_PAID]:
        for item in invoice.items:
            if item.product_id:
                product = db.query(Product).filter(Product.id == item.product_id).first()
                if product and product.track_inventory:
                    movement = InventoryMovement(
                        product_id=product.id,
                        movement_type=InventoryMovementType.RETURN,
                        quantity=item.quantity,  # Positive for returns
                        unit_cost=product.cost or 0,
                        reference=f"Void invoice #{invoice.invoice_number}",
                        created_by=current_user.id
                    )
                    db.add(movement)
                    
                    # Update stock level
                    product.quantity_on_hand += item.quantity
    
    # Update invoice status
    invoice.status = InvoiceStatus.VOID
    invoice.voided_at = func.now()
    invoice.voided_by = current_user.id
    
    db.commit()
    db.refresh(invoice)
    
    return {"success": True, "data": invoice}
