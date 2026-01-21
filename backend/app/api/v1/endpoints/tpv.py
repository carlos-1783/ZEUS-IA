"""
💳 TPV Universal Enterprise API Endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
import logging

from app.db.session import get_db
from app.core.auth import get_current_active_user, get_current_active_superuser
from app.models.user import User
from services.tpv_service import tpv_service, BusinessProfile, PaymentMethod

router = APIRouter()
logger = logging.getLogger(__name__)


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
    cart_items: Optional[List[Dict[str, Any]]] = None  # Carrito del frontend (opcional, si no se envía usa el del servicio)


class GenerateInvoiceRequest(BaseModel):
    ticket_id: str
    customer_data: Dict[str, Any]


class CloseRegisterRequest(BaseModel):
    terminal_id: str
    employee_id: str
    initial_cash: float
    final_cash: float


class SetBusinessProfileRequest(BaseModel):
    business_profile: str


async def _get_tpv_info(current_user: User):
    """Función auxiliar para obtener información del TPV
    Los superusuarios tienen acceso completo sin restricciones de business_profile
    """
    from sqlalchemy.orm import Session
    from app.db.base import SessionLocal
    
    is_superuser = getattr(current_user, 'is_superuser', False)
    
    # Cargar business_profile del usuario si existe
    # Para superusuarios, esto es opcional - tienen acceso completo de todas formas
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.id == current_user.id).first()
        if user:
            # Usar getattr para evitar errores si las columnas no existen aún
            user_data = {
                "id": user.id,
                "tpv_business_profile": getattr(user, 'tpv_business_profile', None),
                "company_name": getattr(user, 'company_name', None)
            }
            # Cargar perfil del usuario (opcional para superusuarios)
            try:
                tpv_service.load_user_profile(user_data)
            except Exception as e:
                logger.warning(f"Error cargando perfil de usuario: {e}")
                # Para superusuarios, no requerir business_profile
                if not tpv_service.business_profile and not is_superuser:
                    from services.tpv_service import BusinessProfile
                    tpv_service.set_business_profile(BusinessProfile.OTROS)
                elif not tpv_service.business_profile and is_superuser:
                    # Superusuarios pueden usar un perfil genérico o ninguno
                    from services.tpv_service import BusinessProfile
                    tpv_service.set_business_profile(BusinessProfile.OTROS)
        else:
            # Si no hay perfil, usar auto-detección o default
            if not tpv_service.business_profile:
                user_data = {
                    "id": current_user.id,
                    "company_name": getattr(current_user, 'company_name', None)
                }
                tpv_service.load_user_profile(user_data)
                # Si aún no hay perfil y no es superusuario, usar default
                if not tpv_service.business_profile and not is_superuser:
                    from services.tpv_service import BusinessProfile
                    tpv_service.set_business_profile(BusinessProfile.OTROS)
                elif not tpv_service.business_profile and is_superuser:
                    # Superusuarios pueden usar perfil genérico
                    from services.tpv_service import BusinessProfile
                    tpv_service.set_business_profile(BusinessProfile.OTROS)
    except Exception as e:
        logger.error(f"Error cargando perfil de usuario: {e}")
        # Usar default si hay error (pero no bloquear superusuarios)
        if not tpv_service.business_profile:
            from services.tpv_service import BusinessProfile
            tpv_service.set_business_profile(BusinessProfile.OTROS)
    finally:
        db.close()
    
    # Obtener configuración actual
    # Superusuarios siempre tienen acceso, incluso sin config
    config = tpv_service.config if tpv_service.business_profile else {}
    
    # Para superusuarios, asegurar que tengan acceso completo
    if is_superuser and not config:
        # Configuración mínima para superusuarios
        config = {
            "tables_enabled": True,
            "services_enabled": True,
            "appointments_enabled": True,
            "products_enabled": True,
            "stock_enabled": True,
            "discounts_enabled": True,
            "requires_employee": False,
            "requires_customer_data": False,
            "superuser_override": True
        }
    
    return {
        "success": True,
        "service": "TPV Universal Enterprise",
        "version": "1.0.0",
        "user": {
            "email": current_user.email,
            "is_superuser": is_superuser,
            "is_active": current_user.is_active
        },
        "endpoints": {
            "status": "/api/v1/tpv/status",
            "products": "/api/v1/tpv/products",
            "cart": "/api/v1/tpv/cart",
            "sale": "/api/v1/tpv/sale",
            "invoice": "/api/v1/tpv/invoice",
            "close_register": "/api/v1/tpv/close-register",
            "detect_business_type": "/api/v1/tpv/detect-business-type"
        },
        "business_profile": tpv_service.business_profile.value if tpv_service.business_profile else None,
        "config": config,
        "products_count": len(tpv_service.products),
        "integrations": {
            "rafael": tpv_service.rafael_integration is not None,
            "justicia": tpv_service.justicia_integration is not None,
            "afrodita": tpv_service.afrodita_integration is not None
        }
    }


@router.get("", include_in_schema=True)
@router.get("/", include_in_schema=True)
async def get_tpv_root(
    current_user: User = Depends(get_current_active_user)
):
    """Endpoint raíz del TPV - Devuelve información básica y endpoints disponibles"""
    return await _get_tpv_info(current_user)


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
    is_superuser = getattr(current_user, 'is_superuser', False)
    is_admin = getattr(current_user, 'is_admin', False) or is_superuser
    
    # Permisos: Solo ADMIN y SUPERUSER pueden crear
    if not (is_admin or is_superuser):
        raise HTTPException(
            status_code=403,
            detail="No tienes permisos para crear productos. Se requiere rol ADMIN o SUPERUSER."
        )
    
    logger.info(f"📦 Creando producto: {request.name} - Precio: €{request.price}")
    logger.info(f"📊 Productos existentes antes de crear: {len(tpv_service.products)}")
    
    product = tpv_service.create_product(
        name=request.name,
        price=request.price,
        category=request.category,
        iva_rate=request.iva_rate,
        stock=request.stock,
        metadata=request.metadata
    )
    
    logger.info(f"✅ Producto creado con ID: {product.get('id')}")
    logger.info(f"📊 Total productos después de crear: {len(tpv_service.products)}")
    logger.info(f"📋 Lista de productos: {[p.get('name') for p in tpv_service.products.values()]}")
    
    return {
        "success": True,
        "product": product,
        "total_products": len(tpv_service.products)
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


@router.put("/products/{product_id}")
async def update_product(
    product_id: str,
    request: ProductCreateRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Actualizar producto en el TPV"""
    is_superuser = getattr(current_user, 'is_superuser', False)
    is_admin = getattr(current_user, 'is_admin', False) or is_superuser
    
    # Permisos: Solo ADMIN y SUPERUSER pueden actualizar
    if not (is_admin or is_superuser):
        raise HTTPException(
            status_code=403,
            detail="No tienes permisos para actualizar productos. Se requiere rol ADMIN o SUPERUSER."
        )
    
    logger.info(f"✏️ Actualizando producto: {product_id}")
    
    result = tpv_service.update_product(
        product_id=product_id,
        name=request.name,
        price=request.price,
        category=request.category,
        iva_rate=request.iva_rate,
        stock=request.stock,
        metadata=request.metadata
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error"))
    
    logger.info(f"✅ Producto actualizado: {product_id}")
    
    return result


@router.delete("/products/{product_id}")
async def delete_product(
    product_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Eliminar producto del TPV"""
    is_superuser = getattr(current_user, 'is_superuser', False)
    
    # Permisos: Solo SUPERUSER puede eliminar
    if not is_superuser:
        raise HTTPException(
            status_code=403,
            detail="No tienes permisos para eliminar productos. Se requiere rol SUPERUSER."
        )
    
    logger.info(f"🗑️ Eliminando producto: {product_id}")
    
    result = tpv_service.delete_product(product_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    logger.info(f"✅ Producto eliminado: {product_id}")
    
    return result


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
    
    # Sincronizar carrito del frontend con el servicio si se envía
    if request.cart_items:
        # Limpiar carrito actual
        tpv_service.current_cart = []
        # Añadir items del frontend al carrito del servicio
        for item in request.cart_items:
            # El frontend envía {product_id, quantity, unit_price, iva_rate}
            # Necesitamos obtener el producto completo del servicio
            product_id = item.get("product_id")
            quantity = item.get("quantity", 1)
            if product_id and product_id in tpv_service.products:
                tpv_service.add_to_cart(product_id, quantity)
            else:
                logger.warning(f"Producto {product_id} no encontrado en servicio, creando item temporal")
                # Crear item temporal si el producto no existe en el servicio
                tpv_service.current_cart.append({
                    "product_id": product_id,
                    "name": f"Producto {product_id}",
                    "price": item.get("unit_price", 0),
                    "price_with_iva": item.get("unit_price", 0) * (1 + item.get("iva_rate", 21) / 100),
                    "quantity": quantity,
                    "subtotal": item.get("unit_price", 0) * quantity,
                    "subtotal_with_iva": item.get("unit_price", 0) * quantity * (1 + item.get("iva_rate", 21) / 100),
                    "iva_rate": item.get("iva_rate", 21),
                    "category": "General"
                })
    
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


@router.post("/set-business-profile")
async def set_business_profile(
    request: SetBusinessProfileRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Establecer business_profile para el usuario actual"""
    try:
        profile = BusinessProfile(request.business_profile)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Business profile inválido. Válidos: {[p.value for p in BusinessProfile]}"
        )
    
    # Actualizar en base de datos (usar setattr para evitar errores si la columna no existe aún)
    user = db.query(User).filter(User.id == current_user.id).first()
    if user:
        try:
            setattr(user, 'tpv_business_profile', profile.value)
            db.commit()
        except Exception as e:
            logger.warning(f"Error actualizando tpv_business_profile (columna puede no existir aún): {e}")
            # Continuar sin error, la migración lo resolverá
            db.rollback()
    
    # Actualizar en servicio TPV
    tpv_service.set_business_profile(profile, current_user.id)
    
    return {
        "success": True,
        "business_profile": profile.value,
        "config": tpv_service.config,
        "message": f"Business profile actualizado a: {profile.value}"
    }


@router.get("/status")
async def get_tpv_status(
    current_user: User = Depends(get_current_active_user)
):
    """Obtener estado del TPV - Los superusuarios ven información completa"""
    is_superuser = getattr(current_user, 'is_superuser', False)
    
    # Cargar perfil del usuario si no está cargado
    if not tpv_service.business_profile:
        from sqlalchemy.orm import Session
        from app.db.base import SessionLocal
        db: Session = SessionLocal()
        try:
            user = db.query(User).filter(User.id == current_user.id).first()
            if user:
                # Usar getattr para evitar errores si las columnas no existen aún
                user_data = {
                    "id": user.id,
                    "tpv_business_profile": getattr(user, 'tpv_business_profile', None),
                    "company_name": getattr(user, 'company_name', None)
                }
                try:
                    tpv_service.load_user_profile(user_data)
                except Exception as e:
                    logger.warning(f"Error cargando perfil de usuario en status: {e}")
                    # Usar default si hay error
                    if not tpv_service.business_profile:
                        from services.tpv_service import BusinessProfile
                        tpv_service.set_business_profile(BusinessProfile.OTROS)
        finally:
            db.close()
    
    # Información básica para todos los usuarios
    status = {
        "success": True,
        "business_profile": tpv_service.business_profile.value if tpv_service.business_profile else None,
        "config": tpv_service.config if tpv_service.business_profile else {},
        "products_count": len(tpv_service.products),
        "cart_items": len(tpv_service.current_cart),
        "integrations": {
            "rafael": tpv_service.rafael_integration is not None,
            "justicia": tpv_service.justicia_integration is not None,
            "afrodita": tpv_service.afrodita_integration is not None
        },
        "user": {
            "email": current_user.email,
            "is_superuser": is_superuser,
            "is_active": current_user.is_active
        }
    }
    
    # Información adicional para superusuarios
    if is_superuser:
        status["admin_info"] = {
            "total_products": len(tpv_service.products),
            "products": list(tpv_service.products.values()) if tpv_service.products else [],
            "categories": list(tpv_service.categories.values()) if tpv_service.categories else [],
            "cart": tpv_service.current_cart.copy(),
            "employees_count": len(tpv_service.employees),
            "terminals_count": len(tpv_service.terminals),
            "pricing_rules_count": len(tpv_service.pricing_rules),
            "inventory_sync_enabled": tpv_service.inventory_sync_enabled,
            "employees": list(tpv_service.employees.values()) if tpv_service.employees else [],
            "terminals": list(tpv_service.terminals.values()) if tpv_service.terminals else []
        }
    
    return status

