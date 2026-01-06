"""
💳 TPV Universal Enterprise API Endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.auth import get_current_active_user
from app.models.user import User
from services.tpv_service import tpv_service, BusinessProfile, PaymentMethod

router = APIRouter()


class BusinessDataRequest(BaseModel):
    name: str
    description: Optional[str] = None
    products: Optional[List[str]] = []


class ProductCreateRequest(BaseModel):
    name: str
    price: float
    category: str
    iva_rate: float = 21.0
    stock: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class AddToCartRequest(BaseModel):
    product_id: str
    quantity: int = 1


class ProcessSaleRequest(BaseModel):
    payment_method: str  # efectivo, tarjeta, bizum, transferencia
    employee_id: Optional[str] = None
    terminal_id: Optional[str] = None
    customer_data: Optional[Dict[str, Any]] = None


class GenerateInvoiceRequest(BaseModel):
    ticket_id: str
    customer_data: Dict[str, Any]


class CloseRegisterRequest(BaseModel):
    terminal_id: str
    employee_id: str
    initial_cash: float
    final_cash: float


@router.post("/detect-business-type")
async def detect_business_type(
    request: BusinessDataRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Detectar automáticamente el tipo de negocio"""
    business_data = {
        "name": request.name,
        "description": request.description or "",
        "products": request.products
    }
    
    profile = tpv_service.auto_detect_business_type(business_data)
    
    return {
        "success": True,
        "business_profile": profile.value,
        "detected_by": "TPV Auto-Detection"
    }


@router.post("/products")
async def create_product(
    request: ProductCreateRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Crear producto en el TPV"""
    product = tpv_service.create_product(
        name=request.name,
        price=request.price,
        category=request.category,
        iva_rate=request.iva_rate,
        stock=request.stock,
        metadata=request.metadata
    )
    
    return {
        "success": True,
        "product": product
    }


@router.get("/products")
async def list_products(
    current_user: User = Depends(get_current_active_user)
):
    """Listar todos los productos"""
    return {
        "success": True,
        "products": list(tpv_service.products.values())
    }


@router.post("/cart/add")
async def add_to_cart(
    request: AddToCartRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Agregar producto al carrito"""
    result = tpv_service.add_to_cart(
        product_id=request.product_id,
        quantity=request.quantity
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result


@router.get("/cart")
async def get_cart(
    current_user: User = Depends(get_current_active_user)
):
    """Obtener estado del carrito"""
    return {
        "success": True,
        "cart": tpv_service.current_cart,
        "total": tpv_service.get_cart_total()
    }


@router.delete("/cart")
async def clear_cart(
    current_user: User = Depends(get_current_active_user)
):
    """Limpiar carrito"""
    tpv_service.current_cart = []
    return {
        "success": True,
        "message": "Carrito limpiado"
    }


@router.post("/sale")
async def process_sale(
    request: ProcessSaleRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Procesar venta y generar ticket"""
    try:
        payment_method = PaymentMethod(request.payment_method.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Método de pago inválido. Válidos: {[m.value for m in PaymentMethod]}"
        )
    
    result = tpv_service.process_sale(
        payment_method=payment_method,
        employee_id=request.employee_id,
        terminal_id=request.terminal_id,
        customer_data=request.customer_data
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result


@router.post("/invoice")
async def generate_invoice(
    request: GenerateInvoiceRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Generar factura desde ticket"""
    result = tpv_service.generate_invoice(
        ticket_id=request.ticket_id,
        customer_data=request.customer_data
    )
    
    return result


@router.post("/close-register")
async def close_register(
    request: CloseRegisterRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Cerrar caja del terminal"""
    result = tpv_service.close_register(
        terminal_id=request.terminal_id,
        employee_id=request.employee_id,
        initial_cash=request.initial_cash,
        final_cash=request.final_cash
    )
    
    return result


@router.get("/status")
async def get_tpv_status(
    current_user: User = Depends(get_current_active_user)
):
    """Obtener estado del TPV"""
    return {
        "success": True,
        "business_profile": tpv_service.business_profile.value if tpv_service.business_profile else None,
        "products_count": len(tpv_service.products),
        "cart_items": len(tpv_service.current_cart),
        "integrations": {
            "rafael": tpv_service.rafael_integration is not None,
            "justicia": tpv_service.justicia_integration is not None,
            "afrodita": tpv_service.afrodita_integration is not None
        }
    }

