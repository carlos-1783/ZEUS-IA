from datetime import datetime, date
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Enums for schemas (matching the model enums)
class ProductCategory(str, Enum):
    GOODS = "goods"
    SERVICES = "services"
    DIGITAL = "digital"
    SUBSCRIPTION = "subscription"

class ProductStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DISCONTINUED = "discontinued"

class InventoryMovementType(str, Enum):
    PURCHASE = "purchase"
    SALE = "sale"
    ADJUSTMENT = "adjustment"
    RETURN = "return"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"

class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    PARTIALLY_PAID = "partially_paid"
    VOID = "void"
    OVERDUE = "overdue"

class InvoiceType(str, Enum):
    INVOICE = "invoice"
    CREDIT_NOTE = "credit_note"
    PROFORMA = "proforma"
    ESTIMATE = "estimate"

class PaymentMethod(str, Enum):
    CASH = "cash"
    CREDIT_CARD = "credit_card"
    BANK_TRANSFER = "bank_transfer"
    CHECK = "check"
    OTHER = "other"

class PaymentStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"

# Base schemas
class ProductBase(BaseModel):
    sku: str = Field(..., min_length=1, max_length=50, description="Unique stock keeping unit")
    name: str = Field(..., min_length=1, max_length=200, description="Product name")
    description: Optional[str] = Field(None, description="Product description")
    
    # Pricing
    # ge=0 (no gt=0): un producto a 0 EUR es legitimo (invitacion, muestra, cortesia), igual que
    # la linea de factura a 0 EUR. Un precio negativo sigue rechazandose (422).
    price: float = Field(..., ge=0, description="Base price")
    cost: Optional[float] = Field(None, ge=0, description="Cost price")
    tax_rate: float = Field(0.0, ge=0, le=100, description="Tax rate in percentage")
    
    # Inventory
    track_inventory: bool = Field(True, description="Whether to track inventory for this product")
    quantity_on_hand: float = Field(0.0, ge=0, description="Current stock level")
    low_stock_threshold: float = Field(0.0, ge=0, description="Threshold for low stock alerts")
    
    # Classification
    category: ProductCategory = Field(ProductCategory.GOODS, description="Product category")
    status: ProductStatus = Field(ProductStatus.ACTIVE, description="Product status")
    
    model_config = ConfigDict(from_attributes=True)

class ProductVariantBase(BaseModel):
    sku: str = Field(..., min_length=1, max_length=50, description="Variant SKU")
    name: str = Field(..., min_length=1, max_length=100, description="Variant name")
    
    # Pricing overrides
    # ge=0, mismo criterio que ProductBase.price: una variante a 0 EUR es legitima. None = usa el
    # precio base (no es lo mismo que 0).
    price_override: Optional[float] = Field(None, ge=0, description="Override base price if set")
    cost_override: Optional[float] = Field(None, ge=0, description="Override cost price if set")
    
    # Inventory
    quantity_on_hand: float = Field(0.0, ge=0, description="Current stock level for this variant")
    
    model_config = ConfigDict(from_attributes=True)

class InventoryMovementBase(BaseModel):
    movement_type: InventoryMovementType = Field(..., description="Type of inventory movement")
    product_id: int = Field(..., gt=0, description="Product ID")
    variant_id: Optional[int] = Field(None, gt=0, description="Variant ID if applicable")
    quantity: float = Field(..., description="Quantity moved (positive for in, negative for out)")
    unit_cost: Optional[float] = Field(None, ge=0, description="Unit cost at time of movement")
    reference: Optional[str] = Field(None, max_length=100, description="Reference number")
    notes: Optional[str] = Field(None, description="Additional notes")
    
    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, v: float) -> float:
        if v == 0:
            raise ValueError("Quantity cannot be zero")
        return v

class InvoiceBase(BaseModel):
    customer_id: Optional[int] = Field(None, gt=0, description="Customer ID")
    invoice_type: InvoiceType = Field(InvoiceType.INVOICE, description="Type of invoice")
    status: InvoiceStatus = Field(InvoiceStatus.DRAFT, description="Invoice status")
    # NOTA (Bloque 2 multi-tenant-bd + envio-gestoria, fix duplicado
    # descubierto en ambas ramas de forma independiente): tipado como
    # datetime (no date) porque la columna real en BD es DateTime
    # (app/models/erp.py Invoice.issue_date/due_date) con default
    # datetime.utcnow(). Con `date`, Pydantic v2 rechaza la respuesta
    # (ResponseValidationError: date_from_datetime_inexact) en cuanto la
    # hora no es exactamente medianoche — rompía SIEMPRE la creación de
    # facturas.
    issue_date: datetime = Field(default_factory=datetime.utcnow, description="Date the invoice was issued")
    due_date: Optional[datetime] = Field(None, description="Due date for payment")
    notes: Optional[str] = Field(None, description="Additional notes")

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode='after')
    def validate_due_date(self) -> 'InvoiceBase':
        if self.due_date and self.due_date < self.issue_date:
            raise ValueError("Due date cannot be before issue date")
        return self

class InvoiceItemBase(BaseModel):
    product_id: Optional[int] = Field(None, gt=0, description="Product ID if applicable")
    description: str = Field(..., min_length=1, max_length=500, description="Item description")
    quantity: float = Field(1.0, gt=0, description="Quantity")
    # ge=0 (no gt=0): una linea a 0 EUR es legitima (invitacion, cortesia). El TPV ya la
    # persiste asi (services/tpv_service.py, InvoiceItem.unit_price = 0).
    unit_price: float = Field(..., ge=0, description="Unit price")
    tax_rate: float = Field(0.0, ge=0, le=100, description="Tax rate in percentage")
    discount: float = Field(0.0, ge=0, description="Discount amount")

    model_config = ConfigDict(from_attributes=True)

    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Quantity must be greater than zero")
        return v

class PaymentBase(BaseModel):
    amount: float = Field(..., gt=0, description="Payment amount")
    payment_method: PaymentMethod = Field(..., description="Payment method")
    status: PaymentStatus = Field(PaymentStatus.COMPLETED, description="Payment status")
    transaction_id: Optional[str] = Field(None, max_length=100, description="Transaction ID")
    reference: Optional[str] = Field(None, max_length=100, description="Reference number")
    notes: Optional[str] = Field(None, description="Additional notes")
    payment_date: datetime = Field(default_factory=datetime.utcnow, description="Date of payment")

    model_config = ConfigDict(from_attributes=True)

# Create schemas
class ProductVariantCreate(ProductVariantBase):
    pass

class ProductCreate(ProductBase):
    variants: Optional[List['ProductVariantCreate']] = Field(
        None, 
        description="List of product variants"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sku": "PROD-001",
                "name": "Premium Widget",
                "description": "High-quality widget for all your needs",
                "price": 99.99,
                "cost": 49.99,
                "tax_rate": 13.0,
                "track_inventory": True,
                "quantity_on_hand": 100,
                "low_stock_threshold": 10,
                "category": "goods",
                "status": "active",
                "variants": [
                    {
                        "sku": "PROD-001-RED",
                        "name": "Red",
                        "price_override": 109.99,
                        "quantity_on_hand": 50
                    }
                ]
            }
        }
    )

class InventoryMovementCreate(InventoryMovementBase):
    pass

class InvoiceItemCreate(InvoiceItemBase):
    pass

class InvoiceCreate(InvoiceBase):
    items: List[InvoiceItemCreate] = Field(
        ..., 
        min_length=1, 
        description="List of invoice items"
    )
    
    @field_validator('items')
    @classmethod
    def validate_items(cls, v: List[InvoiceItemCreate]) -> List[InvoiceItemCreate]:
        if not v:
            raise ValueError("At least one item is required")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "customer_id": 1,
                "invoice_type": "invoice",
                "status": "draft",
                "issue_date": "2025-07-02",
                "due_date": "2025-08-02",
                "notes": "Thank you for your business!",
                "items": [
                    {
                        "product_id": 1,
                        "description": "Premium Widget",
                        "quantity": 2,
                        "unit_price": 99.99,
                        "tax_rate": 13.0,
                        "discount": 0.0
                    }
                ]
            }
        }
    )

class PaymentCreate(PaymentBase):
    pass

# Update schemas
class ProductUpdate(BaseModel):
    # JARVIS J5d-resto (punto 1): faltaba por completo este campo, pese a
    # que update_product (app/api/v1/endpoints/products.py) ya intentaba
    # leer `product_in.sku` para comprobar duplicados -- al no existir en
    # el schema, Pydantic lanzaba AttributeError y CUALQUIER PUT a
    # /products/{id} que llegase a esa linea devolvia 500 (bug preexistente,
    # no introducido por este cambio, pero bloqueaba verificar el fix del
    # punto 1 en el camino de actualizacion).
    sku: Optional[str] = Field(None, min_length=1, max_length=50)
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    price: Optional[float] = Field(None, ge=0)  # ge=0: ver ProductBase.price
    cost: Optional[float] = Field(None, ge=0)
    tax_rate: Optional[float] = Field(None, ge=0, le=100)
    track_inventory: Optional[bool] = None
    quantity_on_hand: Optional[float] = Field(None, ge=0)
    low_stock_threshold: Optional[float] = Field(None, ge=0)
    category: Optional[ProductCategory] = None
    status: Optional[ProductStatus] = None

class ProductVariantUpdate(BaseModel):
    # Mismo bug preexistente que ProductUpdate.sku (ver nota arriba):
    # update_product_variant ya leia `variant_in.sku` sin que el campo
    # existiera en el schema.
    sku: Optional[str] = Field(None, min_length=1, max_length=50)
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    price_override: Optional[float] = Field(None, ge=0)  # ge=0: ver ProductVariantBase
    cost_override: Optional[float] = Field(None, ge=0)
    quantity_on_hand: Optional[float] = Field(None, ge=0)

class InvoiceUpdate(BaseModel):
    customer_id: Optional[int] = Field(None, gt=0)
    status: Optional[InvoiceStatus] = None
    due_date: Optional[date] = None
    notes: Optional[str] = None

# Response schemas
# Respuestas de producto / variante / movimiento: mismo criterio que InvoiceInDB (ver abajo).
# Describen lo que YA esta guardado; no heredan de ProductBase/ProductVariantBase/
# InventoryMovementBase, que son de ENTRADA (price gt/ge, min_length, quantity != 0,
# max_length...). Antes, una sola fila antigua o creada por otro flujo que no cumpliera una regla
# de entrada (p. ej. un producto a 0 EUR, un tax_rate NULL, un movimiento con quantity 0) hacia
# fallar la serializacion y GET /products/ devolvia 500 para TODA la empresa. Lo que sea NULL en
# BD sale como null: nunca se rellena con 0, "" ni fechas inventadas. Mismos campos que antes.
class ProductVariantInDB(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: Optional[int] = None
    sku: Optional[str] = None
    name: Optional[str] = None
    price_override: Optional[float] = None
    cost_override: Optional[float] = None
    quantity_on_hand: Optional[float] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class ProductInDB(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sku: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    cost: Optional[float] = None
    tax_rate: Optional[float] = None
    track_inventory: Optional[bool] = None
    quantity_on_hand: Optional[float] = None
    low_stock_threshold: Optional[float] = None
    category: Optional[ProductCategory] = None
    status: Optional[ProductStatus] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    variants: List[ProductVariantInDB] = []

class InventoryMovementInDB(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    movement_type: Optional[InventoryMovementType] = None
    product_id: Optional[int] = None
    variant_id: Optional[int] = None
    quantity: Optional[float] = None
    unit_cost: Optional[float] = None
    reference: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    created_by: Optional[int] = None

# Respuestas de factura: describen lo que YA esta guardado, no validan reglas de negocio.
# No heredan de InvoiceBase/InvoiceItemBase (que son de ENTRADA: gt/ge/le, longitudes y el
# validador due_date >= issue_date). Si una regla de entrada se aplicaba aqui, una sola fila
# antigua o generada por otro flujo (p. ej. una linea a 0 EUR del TPV, un NULL de una fila
# legacy, un due_date anterior a issue_date) hacia fallar la serializacion y GET /invoices/
# devolvia 500 para TODA la empresa. Lo que sea NULL en BD sale como null: nunca se rellena.
class InvoiceItemInDB(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    invoice_id: int
    product_id: Optional[int] = None
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    tax_rate: Optional[float] = None
    discount: Optional[float] = None
    subtotal: Optional[float] = None
    tax_amount: Optional[float] = None
    total: Optional[float] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class InvoiceInDB(BaseModel):
    # NOTA (Bloque 2 multi-tenant-bd): sin from_attributes=True, model_validate()
    # sobre un objeto ORM falla (ValidationError: "Input should be a valid
    # dictionary or instance of InvoiceInDB") — rompía GET /invoices/{id} para
    # CUALQUIER usuario, propio o ajeno (bug preexistente, no relacionado con
    # RLS: detectado al verificar acceso a una factura propia contra Postgres real).
    model_config = ConfigDict(from_attributes=True)
    id: int
    invoice_number: str
    customer_id: Optional[int] = None
    invoice_type: Optional[InvoiceType] = None
    status: Optional[InvoiceStatus] = None
    issue_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    notes: Optional[str] = None
    subtotal: Optional[float] = None
    tax_amount: Optional[float] = None
    discount_amount: Optional[float] = None
    total: Optional[float] = None
    amount_paid: Optional[float] = None
    amount_due: Optional[float] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None
    items: List[InvoiceItemInDB] = []

# Respuesta de pago: mismo criterio que InvoiceInDB. No hereda de PaymentBase (ENTRADA: amount gt=0,
# transaction_id/reference max_length=100, status/payment_date obligatorios). Un pago antiguo con
# NULL (status, payment_date, created_at son NULL-ables en BD), con importe 0 o con un
# transaction_id largo hacia fallar GET /invoices/{id}/payments con 500. PaymentCreate sigue estricto.
class PaymentInDB(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    invoice_id: int
    amount: Optional[float] = None
    payment_method: Optional[PaymentMethod] = None
    status: Optional[PaymentStatus] = None
    transaction_id: Optional[str] = None
    reference: Optional[str] = None
    notes: Optional[str] = None
    payment_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    created_by: Optional[int] = None

# Response models for API endpoints
class ProductResponse(BaseModel):
    success: bool = True
    data: ProductInDB

class ProductListResponse(BaseModel):
    success: bool = True
    data: List[ProductInDB]
    total: int
    page: int
    limit: int
    total_pages: int

class InvoiceResponse(BaseModel):
    success: bool = True
    data: InvoiceInDB

class InvoiceListResponse(BaseModel):
    success: bool = True
    data: List[InvoiceInDB]
    total: int
    page: int
    limit: int
    total_pages: int

class PaymentResponse(BaseModel):
    success: bool = True
    data: PaymentInDB

ProductCreate.model_rebuild()
