from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body
from services.thalos_request_guard_v1 import thalos_request_guard
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_
from datetime import date, datetime, time

from app.db.tenant_context import get_db_scoped
from app.models.erp import (
    Invoice, InvoiceItem, Payment, Product, InventoryMovement, InventoryMovementType,
    InvoiceType as ModelInvoiceType, InvoiceStatus as ModelInvoiceStatus,
    PaymentMethod as ModelPaymentMethod, PaymentStatus as ModelPaymentStatus,
)
from app.schemas.erp import (
    InvoiceCreate, InvoiceUpdate, InvoiceInDB, InvoiceResponse, InvoiceListResponse,
    InvoiceItemCreate, InvoiceItemInDB,
    PaymentCreate, PaymentInDB, PaymentResponse,
    InvoiceStatus, InvoiceType, PaymentStatus, PaymentMethod
)
from app.core.auth import get_current_active_user
from app.models.user import User
from services.event_bus import emit_cashflow_updated, emit_payment_registered
import services.crm_office_service as crm_svc
from services.zeus_office_mode import (
    require_company_id,
    validate_invoice_logical,
    validate_payment_logical,
)

import logging
logger = logging.getLogger(__name__)

router = APIRouter()

def _invoice_tenant_scope(current_user: User, cids: List[int]):
    """
    Filtro de aislamiento multi-tenant para facturas.

    - Si el usuario pertenece a una o más empresas, solo ve facturas de esas
      empresas (o facturas legacy sin company_id que él mismo creó).
    - Si el usuario no pertenece a ninguna empresa, solo ve las facturas que
      él mismo creó (created_by), nunca las de otros.
    """
    if not cids:
        return Invoice.created_by == current_user.id
    return or_(
        Invoice.company_id.in_(cids),
        and_(Invoice.company_id.is_(None), Invoice.created_by == current_user.id),
    )

def get_invoice_orm_or_404(
    db: Session,
    invoice_id: int,
    current_user: User
) -> Invoice:
    """
    Igual que get_invoice_or_404 pero devuelve la entidad ORM (mutable y
    persistible). Los endpoints que modifican la factura DEBEN usar esta
    funcion: mutar el InvoiceInDB (pydantic) no persiste nada.
    Mismo filtro de tenant (_invoice_tenant_scope): 404 si es de otra empresa.
    """
    from fastapi import HTTPException, status
    from sqlalchemy.orm import joinedload

    cids = crm_svc.company_ids_for_user(db, current_user)
    invoice = db.query(Invoice).options(
        joinedload(Invoice.items),
        joinedload(Invoice.payments)
    ).filter(
        Invoice.id == invoice_id
    ).filter(
        _invoice_tenant_scope(current_user, cids)
    ).first()
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice with ID {invoice_id} not found"
        )
    return invoice

def get_invoice_or_404(
    db: Session,
    invoice_id: int,
    current_user: User
) -> InvoiceInDB:
    """
    Obtiene una factura por ID (acotada a las empresas del usuario) o lanza
    una excepción 404 si no se encuentra o no pertenece a su ámbito.

    Args:
        db: Sesión de base de datos
        invoice_id: ID de la factura a buscar
        current_user: Usuario autenticado

    Returns:
        InvoiceInDB: El objeto de la factura en formato Pydantic si se encuentra

    Raises:
        HTTPException: 404 si la factura no existe o no pertenece a la empresa del usuario
    """
    invoice = get_invoice_orm_or_404(db, invoice_id, current_user)

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
    amount_paid = sum(payment.amount for payment in invoice.payments if payment.status == ModelPaymentStatus.COMPLETED)
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
    db: Session = Depends(get_db_scoped),
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
    List all invoices with optional filtering and pagination (tenant-scoped)
    """
    # Aislamiento de tenant: solo facturas de las empresas del usuario
    # autenticado (o facturas legacy sin company_id creadas por él mismo).
    # Usa el mismo helper que get_invoice_or_404 (_invoice_tenant_scope).
    cids = crm_svc.company_ids_for_user(db, current_user)
    query = db.query(Invoice).filter(_invoice_tenant_scope(current_user, cids))

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
    db: Session = Depends(get_db_scoped),
    current_user: User = Depends(get_current_active_user)
):
    """
    Create a new invoice
    """
    # Check if customer exists and belongs to the user's tenant scope.
    # crm_svc.resolve_customer raises 404 if the customer isn't visible to
    # this user (prevents referencing another company's customer by ID).
    if invoice_in.customer_id:
        crm_svc.resolve_customer(db, current_user, invoice_in.customer_id)

    company_id = crm_svc.primary_company_id(db, current_user)
    require_company_id(company_id, context="facturación")

    # Generate invoice number (in a real app, use a proper sequence)
    invoice_number = f"INV-{datetime.utcnow().strftime('%Y%m%d')}-{db.query(func.count(Invoice.id)).scalar() + 1}"
    
    # Create invoice
    invoice_data = invoice_in.dict(exclude={"items"}, exclude_unset=True)
    # Mismo bug de serializacion de Enum que en create_product (ver
    # app/api/v1/endpoints/products.py): app.schemas.erp.InvoiceType/
    # InvoiceStatus son Enum(str, Enum) cuyo .dict() emite el .value en
    # minuscula ("invoice"/"draft"), pero la columna Column(Enum(...)) del
    # modelo ERP espera el NOMBRE en mayuscula ("INVOICE"/"DRAFT"). Se
    # convierte explicitamente aqui, usando siempre el valor real del
    # atributo (no el resultado de .dict(), que puede faltar si el campo
    # no fue enviado explicitamente por el cliente y exclude_unset lo omitio).
    invoice_data["invoice_type"] = ModelInvoiceType[invoice_in.invoice_type.name]
    invoice_data["status"] = ModelInvoiceStatus[invoice_in.status.name]
    # Invoice.issue_date/due_date son columnas DateTime (Column(DateTime)),
    # pero el schema las expone como `date` (medianoche exacta, sin hora).
    # Si no se normalizan aqui, dos vias distintas pueden colar una hora
    # "sucia" en la columna: (a) si el cliente no envia issue_date,
    # exclude_unset lo omite de invoice_data y entra en juego el default
    # del MODELO (datetime.utcnow(), que SI lleva hora); (b) si el cliente
    # envia due_date, Pydantic ya lo valida como `date`, pero conviene
    # forzar el mismo tipo exacto que espera la columna en vez de confiar
    # en la coercion implicita de SQLAlchemy/SQLite. En ambos casos, la
    # fila queda persistida con hora antes de que FastAPI intente
    # serializar la respuesta con InvoiceInDB.issue_date: date -- y esa
    # ResponseValidationError ocurre DESPUES del commit, fuera del alcance
    # del try/except+rollback de abajo (que solo protege el flush/refresh
    # previo al commit). Por eso se corrige en el origen, no "atajando" el
    # fallo de serializacion despues del hecho.
    invoice_data["issue_date"] = datetime.combine(invoice_in.issue_date, time.min)
    if invoice_in.due_date is not None:
        invoice_data["due_date"] = datetime.combine(invoice_in.due_date, time.min)
    invoice = Invoice(
        **invoice_data,
        invoice_number=invoice_number,
        company_id=company_id,
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
            # and handle variants properly. Scoped to the invoice's own company
            # so a product from another tenant can't be referenced/mutated here.
            product = db.query(Product).filter(
                Product.id == item.product_id,
                Product.company_id == company_id,
            ).first()
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
    
    # Calculate and update totals. flush + expire "items" fuerza a
    # SQLAlchemy a releer la relación desde BD: sin esto, calculate_invoice_totals
    # podía ver invoice.items vacío (los items se añadieron con db.add(item)
    # suelto, no invoice.items.append(item)) y devolver subtotal/tax/total
    # en 0 pese a que los items sí tenían unit_price/tax_rate reales —
    # rompía la generación de factura PDF de RAFAEL, que exige total > 0.
    db.flush()
    db.expire(invoice, ["items"])
    totals = calculate_invoice_totals(invoice, db)
    for key, value in totals.items():
        setattr(invoice, key, value)

    validate_invoice_logical(
        customer_id=invoice_in.customer_id,
        issue_date=invoice.issue_date,
        subtotal=float(totals["subtotal"]),
        tax_amount=float(totals["tax_amount"]),
        total=float(totals["total"]),
        status_value=str(invoice.status.value if hasattr(invoice.status, "value") else invoice.status),
    )

    # Verificamos que la fila resultante es legible ANTES de confirmar la
    # transaccion (mismo motivo que en create_product): si algo en el
    # insert fuese invalido, hacemos rollback en vez de dejar una factura
    # corrupta persistida mientras el cliente recibe un 500.
    try:
        db.flush()
        db.refresh(invoice)
    except Exception:
        db.rollback()
        raise
    db.commit()
    db.refresh(invoice)

    return {"success": True, "data": invoice}

@router.get("/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(
    invoice_id: int = Path(..., description="ID of the invoice to retrieve"),
    db: Session = Depends(get_db_scoped),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get a specific invoice by ID
    """
    invoice = get_invoice_or_404(db, invoice_id, current_user)
    return {"success": True, "data": invoice}

@router.put("/{invoice_id}", response_model=InvoiceResponse, dependencies=[Depends(thalos_request_guard)])
def update_invoice(
    *,
    invoice_id: int = Path(..., description="ID of the invoice to update"),
    invoice_in: dict = Body(..., description="Invoice fields to update"),
    db: Session = Depends(get_db_scoped),
    current_user: User = Depends(get_current_active_user)
):
    """
    Update an invoice
    """
    invoice = get_invoice_orm_or_404(db, invoice_id, current_user)

    # Lista blanca (misma que InvoiceUpdate): evita mass-assignment de
    # company_id, created_by, totales, etc.
    # `status` NO se puede cambiar por PUT: las transiciones van por
    # /send, /void y /payments (con sus reglas).
    if "status" in invoice_in:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice status cannot be changed via PUT; use /send, /void or /payments",
        )
    allowed = {"customer_id", "due_date", "notes"}
    for field, value in invoice_in.items():
        if field not in allowed:
            continue
        if field == "customer_id" and value is not None:
            # Mismo control de tenant que create_invoice: 404 si el cliente
            # es de otra empresa.
            crm_svc.resolve_customer(db, current_user, value)
        if field == "due_date" and isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except ValueError:
                raise HTTPException(status_code=422, detail="Invalid due_date")
        setattr(invoice, field, value)

    db.commit()
    db.refresh(invoice)

    return {"success": True, "data": InvoiceInDB.model_validate(invoice)}

@router.post("/{invoice_id}/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(thalos_request_guard)])
def create_payment(
    *,
    invoice_id: int = Path(..., description="ID of the invoice to pay"),
    payment_in: PaymentCreate,
    db: Session = Depends(get_db_scoped),
    current_user: User = Depends(get_current_active_user)
):
    """
    Record a payment for an invoice
    """
    invoice = get_invoice_orm_or_404(db, invoice_id, current_user)

    validate_payment_logical(
        invoice_id=invoice_id,
        amount=float(payment_in.amount),
        # BUG PREEXISTENTE (no relacionado con el Enum, hallazgo de esta
        # auditoria): el schema PaymentBase declara el campo como
        # `payment_method`, no `method` -- `payment_in.method` no existe y
        # esto hacia que create_payment lanzara AttributeError en el 100%
        # de las llamadas, antes de llegar siquiera a construir el Payment.
        # Se corrige aqui porque bloqueaba por completo la verificacion en
        # vivo del bug de Enum pedido para este endpoint.
        method=str(payment_in.payment_method.value if hasattr(payment_in.payment_method, "value") else payment_in.payment_method),
        payment_date=payment_in.payment_date or datetime.utcnow().date(),
    )

    # Create payment
    payment_data = payment_in.dict()
    # Mismo bug de serializacion de Enum que en create_product/create_invoice:
    # PaymentMethod/PaymentStatus del schema emiten su .value en minuscula,
    # pero la columna del modelo espera el NOMBRE en mayuscula.
    payment_data["payment_method"] = ModelPaymentMethod[payment_in.payment_method.name]
    payment_data["status"] = ModelPaymentStatus[payment_in.status.name]
    payment = Payment(
        **payment_data,
        invoice_id=invoice_id,
        created_by=current_user.id
    )

    db.add(payment)
    db.flush()
    # La coleccion invoice.payments ya estaba cargada (joinedload) sin este
    # pago: expirarla para que los totales lo incluyan.
    db.expire(invoice, ["payments"])

    # Update invoice status based on payment (payment now visible in totals)
    totals = calculate_invoice_totals(invoice, db)

    # `payment.status` es ahora el Enum del MODELO (ver conversion arriba),
    # no el de schemas.erp -- se compara contra ModelPaymentStatus para que
    # esta comprobacion siga funcionando tras el fix del bug de Enum.
    if payment.status == ModelPaymentStatus.COMPLETED:
        if totals["amount_due"] <= 0:
            invoice.status = ModelInvoiceStatus.PAID
        elif totals["amount_paid"] > 0:
            invoice.status = ModelInvoiceStatus.PARTIALLY_PAID

    # Update invoice amounts
    for key, value in totals.items():
        setattr(invoice, key, value)

    try:
        db.flush()
        db.refresh(payment)
    except Exception:
        db.rollback()
        raise
    db.commit()
    db.refresh(payment)
    try:
        cid = crm_svc.primary_company_id(db, current_user)
        amt = float(payment.amount) if getattr(payment, "amount", None) is not None else None
        emit_payment_registered(
            user_id=current_user.id,
            user_email=getattr(current_user, "email", None),
            company_id=cid,
            customer_id=getattr(invoice, "customer_id", None),
            ticket_id=getattr(invoice, "invoice_number", None),
            tpv_sale_id=None,
            payment_method=str(payment.method) if getattr(payment, "method", None) else None,
            amount=amt,
            service_name="invoice_payment",
            source="INVOICES_MODULE",
            db=db,
        )
        if amt is not None and cid is not None:
            emit_cashflow_updated(
                user_id=current_user.id,
                user_email=getattr(current_user, "email", None),
                company_id=cid,
                amount=amt,
                direction="in",
                source="INVOICES_MODULE",
                customer_id=getattr(invoice, "customer_id", None),
                invoice_id=invoice_id,
                payment_method=str(payment.method) if getattr(payment, "method", None) else None,
                db=db,
            )
    except Exception:
        # No bloquear el flujo de facturación por trazabilidad/evento
        logger.warning("create_payment: fallo al emitir eventos de pago (factura %s)", invoice_id, exc_info=True)
    
    return {"success": True, "data": payment}

@router.get("/{invoice_id}/payments", response_model=List[PaymentInDB])
def list_invoice_payments(
    invoice_id: int = Path(..., description="ID of the invoice"),
    db: Session = Depends(get_db_scoped),
    current_user: User = Depends(get_current_active_user)
):
    """
    List all payments for an invoice
    """
    # Verify invoice exists
    invoice = get_invoice_or_404(db, invoice_id, current_user)
    
    return invoice.payments

@router.post("/{invoice_id}/send", response_model=InvoiceResponse, dependencies=[Depends(thalos_request_guard)])
def send_invoice(
    invoice_id: int = Path(..., description="ID of the invoice to send"),
    db: Session = Depends(get_db_scoped),
    current_user: User = Depends(get_current_active_user)
):
    """
    Marca la factura como enviada (borrador -> enviada).

    IMPORTANTE: este endpoint SOLO cambia el estado en BD. NO envia email ni
    nada a terceros (no hay accion externa, por tanto no pasa por
    zeus_pending_approvals). Si en el futuro envia al cliente, debe pasar por
    aprobacion.
    """
    invoice = get_invoice_orm_or_404(db, invoice_id, current_user)
    
    if invoice.status != ModelInvoiceStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft invoices can be sent"
        )
    
    invoice.status = ModelInvoiceStatus.SENT

    db.commit()
    db.refresh(invoice)

    return {"success": True, "data": InvoiceInDB.model_validate(invoice)}

@router.post("/{invoice_id}/void", response_model=InvoiceResponse, dependencies=[Depends(thalos_request_guard)])
def void_invoice(
    invoice_id: int = Path(..., description="ID of the invoice to void"),
    db: Session = Depends(get_db_scoped),
    current_user: User = Depends(get_current_active_user)
):
    """
    Void an invoice
    """
    invoice = get_invoice_orm_or_404(db, invoice_id, current_user)
    
    if invoice.status == ModelInvoiceStatus.VOID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice is already void"
        )
    
    if invoice.status == ModelInvoiceStatus.PAID:
        # In a real app, you might want to issue a refund
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot void a paid invoice"
        )
    
    # Reverse inventory movements if needed
    if invoice.status in [ModelInvoiceStatus.PAID, ModelInvoiceStatus.PARTIALLY_PAID]:
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
    invoice.status = ModelInvoiceStatus.VOID
    
    db.commit()
    db.refresh(invoice)
    
    return {"success": True, "data": InvoiceInDB.model_validate(invoice)}
