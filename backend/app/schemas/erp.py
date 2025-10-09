from datetime import datetime, date
from typing import List, Optional, Dict, Any, Union
from enum import Enum
from pydantic import BaseModel, Field, validator, condecimal
from decimal import Decimal

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
    price: float = Field(..., gt=0, description="Base price")
    cost: Optional[float] = Field(None, ge=0, description="Cost price")
    tax_rate: float = Field(0.0, ge=0, le=100, description="Tax rate in percentage")
    
    # Inventory
    track_inventory: bool = Field(True, description="Whether to track inventory for this product")
    quantity_on_hand: float = Field(0.0, ge=0, description="Current stock level")
    low_stock_threshold: float = Field(0.0, ge=0, description="Threshold for low stock alerts")
    
    # Classification
    category: ProductCategory = Field(ProductCategory.GOODS, description="Product category")
    status: ProductStatus = Field(ProductStatus.ACTIVE, description="Product status")
    
    class Config:
        from_attributes = True

class ProductVariantBase(BaseModel):
    sku: str = Field(..., min_length=1, max_length=50, description="Variant SKU")
    name: str = Field(..., min_length=1, max_length=100, description="Variant name")
    
    # Pricing overrides
    price_override: Optional[float] = Field(None, gt=0, description="Override base price if set")
    cost_override: Optional[float] = Field(None, ge=0, description="Override cost price if set")
    
    # Inventory
    quantity_on_hand: float = Field(0.0, ge=0, description="Current stock level for this variant")
    
    class Config:
        orm_mode = True

class InventoryMovementBase(BaseModel):
    movement_type: InventoryMovementType = Field(..., description="Type of inventory movement")
    product_id: int = Field(..., gt=0, description="Product ID")
    variant_id: Optional[int] = Field(None, gt=0, description="Variant ID if applicable")
    quantity: float = Field(..., description="Quantity moved (positive for in, negative for out)")
    unit_cost: Optional[float] = Field(None, ge=0, description="Unit cost at time of movement")
    reference: Optional[str] = Field(None, max_length=100, description="Reference number")
    notes: Optional[str] = Field(None, description="Additional notes")
    
    @validator('quantity')
    def validate_quantity(cls, v):
        if v == 0:
            raise ValueError("Quantity cannot be zero")
        return v

class InvoiceBase(BaseModel):
    customer_id: Optional[int] = Field(None, gt=0, description="Customer ID")
    invoice_type: InvoiceType = Field(InvoiceType.INVOICE, description="Type of invoice")
    status: InvoiceStatus = Field(InvoiceStatus.DRAFT, description="Invoice status")
    issue_date: date = Field(default_factory=date.today, description="Date the invoice was issued")
    due_date: Optional[date] = Field(None, description="Due date for payment")
    notes: Optional[str] = Field(None, description="Additional notes")
    
    @validator('due_date')
    def validate_due_date(cls, v, values):
        if v and 'issue_date' in values and v < values['issue_date']:
            raise ValueError("Due date cannot be before issue date")
        return v

class InvoiceItemBase(BaseModel):
    product_id: Optional[int] = Field(None, gt=0, description="Product ID if applicable")
    description: str = Field(..., min_length=1, max_length=500, description="Item description")
    quantity: float = Field(1.0, gt=0, description="Quantity")
    unit_price: float = Field(..., gt=0, description="Unit price")
    tax_rate: float = Field(0.0, ge=0, le=100, description="Tax rate in percentage")
    discount: float = Field(0.0, ge=0, description="Discount amount")
    
    @validator('quantity')
    def validate_quantity(cls, v):
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
    payment_date: date = Field(default_factory=date.today, description="Date of payment")

# Create schemas
class ProductCreate(ProductBase):
    variants: Optional[List['ProductVariantCreate']] = Field(
        None, 
        description="List of product variants"
    )

class ProductVariantCreate(ProductVariantBase):
    pass

class InventoryMovementCreate(InventoryMovementBase):
    pass

class InvoiceItemCreate(InvoiceItemBase):
    pass

class InvoiceCreate(InvoiceBase):
    items: List[InvoiceItemCreate] = Field(
        ..., 
        min_items=1, 
        description="List of invoice items"
    )
    
    @validator('items')
    def validate_items(cls, v):
        if not v:
            raise ValueError("At least one item is required")
        return v

class PaymentCreate(PaymentBase):
    pass

# Update schemas
class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    price: Optional[float] = Field(None, gt=0)
    cost: Optional[float] = Field(None, ge=0)
    tax_rate: Optional[float] = Field(None, ge=0, le=100)
    track_inventory: Optional[bool] = None
    quantity_on_hand: Optional[float] = Field(None, ge=0)
    low_stock_threshold: Optional[float] = Field(None, ge=0)
    category: Optional[ProductCategory] = None
    status: Optional[ProductStatus] = None

class ProductVariantUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    price_override: Optional[float] = Field(None, gt=0)
    cost_override: Optional[float] = Field(None, ge=0)
    quantity_on_hand: Optional[float] = Field(None, ge=0)

class InvoiceUpdate(BaseModel):
    customer_id: Optional[int] = Field(None, gt=0)
    status: Optional[InvoiceStatus] = None
    due_date: Optional[date] = None
    notes: Optional[str] = None

# Response schemas
class ProductVariantInDB(ProductVariantBase):
    id: int
    product_id: int
    created_at: datetime
    updated_at: datetime

class ProductInDB(ProductBase):
    id: int
    created_at: datetime
    updated_at: datetime
    variants: List[ProductVariantInDB] = []

class InventoryMovementInDB(InventoryMovementBase):
    id: int
    created_at: datetime
    created_by: Optional[int]

class InvoiceItemInDB(InvoiceItemBase):
    id: int
    invoice_id: int
    product_id: Optional[int]
    subtotal: float
    tax_amount: float
    total: float
    created_at: datetime
    updated_at: datetime

class InvoiceInDB(InvoiceBase):
    id: int
    invoice_number: str
    subtotal: float
    tax_amount: float
    discount_amount: float
    total: float
    amount_paid: float
    amount_due: float
    created_at: datetime
    updated_at: datetime
    created_by: Optional[int]
    items: List[InvoiceItemInDB] = []

class PaymentInDB(PaymentBase):
    id: int
    invoice_id: int
    created_at: datetime
    created_by: Optional[int]

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

# Update forward references
ProductCreate.update_forward_refs()

# Update schema examples for documentation
ProductCreate.Config.schema_extra = {
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

InvoiceCreate.Config.schema_extra = {
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
