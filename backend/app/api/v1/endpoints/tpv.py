"""
💳 TPV Universal Enterprise API Endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, File, UploadFile
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
import logging
from pathlib import Path
from datetime import datetime
import secrets

from app.db.session import get_db
from app.core.auth import get_current_active_user, get_current_active_superuser
from app.core.config import settings
from app.models.user import User
from app.models.erp import TPVProduct
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
    image: Optional[str] = None
    icon: Optional[str] = None
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
        "products_count": db.query(TPVProduct).filter(TPVProduct.user_id == current_user.id).count() if current_user else 0,
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
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Crear producto en el TPV - PERSISTIDO EN BD CON MULTI-TENANCY"""
    is_superuser = getattr(current_user, 'is_superuser', False)
    is_admin = getattr(current_user, 'is_admin', False) or is_superuser
    
    # Permisos: Solo ADMIN y SUPERUSER pueden crear
    if not (is_admin or is_superuser):
        raise HTTPException(
            status_code=403,
            detail="No tienes permisos para crear productos. Se requiere rol ADMIN o SUPERUSER."
        )
    
    logger.info(f"📦 Creando producto: {request.name} - Precio: €{request.price} - Usuario: {current_user.id}")
    
    # Generar ID único
    import time
    base_id = int(time.time() * 1000)
    # Contar productos existentes del usuario para garantizar unicidad
    existing_count = db.query(TPVProduct).filter(TPVProduct.user_id == current_user.id).count()
    product_id = f"PROD_{base_id}_{existing_count:04d}"
    
    # Verificar que el ID no existe (por si acaso)
    while db.query(TPVProduct).filter(
        TPVProduct.product_id == product_id,
        TPVProduct.user_id == current_user.id
    ).first():
        existing_count += 1
        product_id = f"PROD_{base_id}_{existing_count:04d}"
    
    # Calcular precio con IVA
    price_with_iva = request.price * (1 + request.iva_rate / 100)
    
    # Crear producto en BD
    db_product = TPVProduct(
        user_id=current_user.id,  # MULTI-TENANCY: Filtrar por usuario
        product_id=product_id,
        name=request.name,
        category=request.category,
        price=request.price,
        price_with_iva=price_with_iva,
        iva_rate=request.iva_rate,
        stock=request.stock,
        image=request.image,
        icon=request.icon,
        metadata_=request.metadata or {}
    )
    
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    
    # Convertir a formato dict para mantener compatibilidad con API
    product = {
        "id": db_product.product_id,
        "name": db_product.name,
        "price": db_product.price,
        "price_with_iva": db_product.price_with_iva,
        "category": db_product.category,
        "iva_rate": db_product.iva_rate,
        "stock": db_product.stock,
        "image": db_product.image,
        "icon": db_product.icon,
        "metadata": db_product.metadata_ or {},
        "created_at": db_product.created_at.isoformat() if db_product.created_at else datetime.utcnow().isoformat(),
        "updated_at": db_product.updated_at.isoformat() if db_product.updated_at else datetime.utcnow().isoformat()
    }
    
    total_products = db.query(TPVProduct).filter(TPVProduct.user_id == current_user.id).count()
    
    logger.info(f"✅ Producto creado con ID: {product_id} - Usuario: {current_user.id}")
    logger.info(f"📊 Total productos del usuario: {total_products}")
    
    return {
        "success": True,
        "product": product,
        "total_products": total_products
    }


@router.get("/products")
async def list_products(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Listar todos los productos DEL USUARIO ACTUAL - MULTI-TENANCY"""
    # Filtrar SOLO productos del usuario actual
    db_products = db.query(TPVProduct).filter(TPVProduct.user_id == current_user.id).all()
    
    # Convertir a formato dict para mantener compatibilidad con API
    products = []
    for db_product in db_products:
        products.append({
            "id": db_product.product_id,
            "name": db_product.name,
            "price": db_product.price,
            "price_with_iva": db_product.price_with_iva,
            "category": db_product.category,
            "iva_rate": db_product.iva_rate,
            "stock": db_product.stock,
            "image": db_product.image,
            "icon": db_product.icon,
            "metadata": db_product.metadata_ or {},
            "created_at": db_product.created_at.isoformat() if db_product.created_at else None,
            "updated_at": db_product.updated_at.isoformat() if db_product.updated_at else None
        })
    
    logger.info(f"📋 Listando {len(products)} productos para usuario {current_user.id}")
    
    return {
        "success": True,
        "products": products
    }


@router.put("/products/{product_id}")
async def update_product(
    product_id: str,
    request: ProductCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Actualizar producto en el TPV - MULTI-TENANCY: Solo productos del usuario"""
    is_superuser = getattr(current_user, 'is_superuser', False)
    is_admin = getattr(current_user, 'is_admin', False) or is_superuser
    
    # Permisos: Solo ADMIN y SUPERUSER pueden actualizar
    if not (is_admin or is_superuser):
        raise HTTPException(
            status_code=403,
            detail="No tienes permisos para actualizar productos. Se requiere rol ADMIN o SUPERUSER."
        )
    
    logger.info(f"✏️ Actualizando producto: {product_id} - Usuario: {current_user.id}")
    
    # Buscar producto SOLO del usuario actual (multi-tenancy)
    db_product = db.query(TPVProduct).filter(
        TPVProduct.product_id == product_id,
        TPVProduct.user_id == current_user.id
    ).first()
    
    if not db_product:
        raise HTTPException(
            status_code=404,
            detail=f"Producto {product_id} no encontrado o no tienes permisos para modificarlo"
        )
    
    # Calcular precio con IVA
    price_with_iva = request.price * (1 + request.iva_rate / 100)
    
    # Actualizar campos
    db_product.name = request.name
    db_product.price = request.price
    db_product.price_with_iva = price_with_iva
    db_product.category = request.category
    db_product.iva_rate = request.iva_rate
    db_product.stock = request.stock
    db_product.image = request.image
    db_product.icon = request.icon
    db_product.metadata_ = request.metadata or {}
    
    db.commit()
    db.refresh(db_product)
    
    # Convertir a formato dict
    product = {
        "id": db_product.product_id,
        "name": db_product.name,
        "price": db_product.price,
        "price_with_iva": db_product.price_with_iva,
        "category": db_product.category,
        "iva_rate": db_product.iva_rate,
        "stock": db_product.stock,
        "image": db_product.image,
        "icon": db_product.icon,
        "metadata": db_product.metadata_ or {},
        "created_at": db_product.created_at.isoformat() if db_product.created_at else None,
        "updated_at": db_product.updated_at.isoformat() if db_product.updated_at else None
    }
    
    logger.info(f"✅ Producto actualizado: {product_id} - Usuario: {current_user.id}")
    
    return {
        "success": True,
        "product": product
    }


@router.post("/products/upload-image")
async def upload_product_image(
    image: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user)
):
    """Subir imagen de producto"""
    is_superuser = getattr(current_user, 'is_superuser', False)
    is_admin = getattr(current_user, 'is_admin', False) or is_superuser
    
    # Permisos: Solo ADMIN y SUPERUSER pueden subir imágenes
    if not (is_admin or is_superuser):
        raise HTTPException(
            status_code=403,
            detail="No tienes permisos para subir imágenes. Se requiere rol ADMIN o SUPERUSER."
        )
    
    # Validar tipo de archivo
    allowed_types = ["image/png", "image/jpeg", "image/webp"]
    if image.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Formato no soportado. Usa: {', '.join(allowed_types)}"
        )
    
    # Validar tamaño (max 2MB)
    MAX_SIZE = 2 * 1024 * 1024  # 2MB
    contents = await image.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(
            status_code=400,
            detail="La imagen supera el límite de 2MB"
        )
    
    # Crear directorio de productos si no existe
    upload_dir = Path(settings.STATIC_DIR) / "uploads" / "products"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Generar nombre único
    extension = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp"
    }[image.content_type]
    
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    token = secrets.token_urlsafe(6)
    filename = f"product_{timestamp}_{token}{extension}"
    destination = upload_dir / filename
    
    # Guardar archivo
    destination.write_bytes(contents)
    
    # Construir URL pública
    public_url = f"{settings.STATIC_URL.rstrip('/')}/uploads/products/{filename}"
    
    logger.info(f"📸 Imagen de producto subida: {filename}")
    
    return {
        "success": True,
        "url": public_url,
        "filename": filename,
        "content_type": image.content_type,
        "size_bytes": len(contents)
    }


@router.delete("/products/{product_id}")
async def delete_product(
    product_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Eliminar producto del TPV - MULTI-TENANCY: Solo productos del usuario"""
    is_superuser = getattr(current_user, 'is_superuser', False)
    
    # Permisos: Solo SUPERUSER puede eliminar
    if not is_superuser:
        raise HTTPException(
            status_code=403,
            detail="No tienes permisos para eliminar productos. Se requiere rol SUPERUSER."
        )
    
    logger.info(f"🗑️ Eliminando producto: {product_id} - Usuario: {current_user.id}")
    
    # Buscar producto SOLO del usuario actual (multi-tenancy)
    db_product = db.query(TPVProduct).filter(
        TPVProduct.product_id == product_id,
        TPVProduct.user_id == current_user.id
    ).first()
    
    if not db_product:
        raise HTTPException(
            status_code=404,
            detail=f"Producto {product_id} no encontrado o no tienes permisos para eliminarlo"
        )
    
    product_name = db_product.name
    db.delete(db_product)
    db.commit()
    
    remaining_count = db.query(TPVProduct).filter(TPVProduct.user_id == current_user.id).count()
    
    logger.info(f"✅ Producto eliminado: {product_id} ({product_name}) - Usuario: {current_user.id}")
    logger.info(f"📊 Productos restantes del usuario: {remaining_count}")
    
    return {
        "success": True,
        "message": f"Producto '{product_name}' eliminado correctamente",
        "remaining_products": remaining_count
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
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Procesar venta y generar ticket - MULTI-TENANCY: Solo productos del usuario"""
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
            # Buscar producto en BD del usuario actual (multi-tenancy)
            product_id = item.get("product_id")
            quantity = item.get("quantity", 1)
            
            if product_id:
                # Buscar producto en BD del usuario actual
                db_product = db.query(TPVProduct).filter(
                    TPVProduct.product_id == product_id,
                    TPVProduct.user_id == current_user.id
                ).first()
                
                if db_product:
                    # Producto encontrado en BD del usuario
                    tpv_service.current_cart.append({
                        "product_id": db_product.product_id,
                        "name": db_product.name,
                        "price": db_product.price,
                        "price_with_iva": db_product.price_with_iva,
                        "quantity": quantity,
                        "subtotal": db_product.price * quantity,
                        "subtotal_with_iva": db_product.price_with_iva * quantity,
                        "iva_rate": db_product.iva_rate,
                        "category": db_product.category
                    })
                else:
                    # Producto no encontrado - usar datos del frontend como fallback
                    logger.warning(f"Producto {product_id} no encontrado en BD del usuario {current_user.id}, usando datos del frontend")
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
        customer_data=request.customer_data,
        user_id=current_user.id,  # Pasar user_id para persistencia fiscal
        db=db  # Pasar db para persistencia fiscal
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
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
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
        user_products = db.query(TPVProduct).filter(TPVProduct.user_id == current_user.id).all()
        products_list = []
        for db_product in user_products:
            products_list.append({
                "id": db_product.product_id,
                "name": db_product.name,
                "price": db_product.price,
                "price_with_iva": db_product.price_with_iva,
                "category": db_product.category
            })
        status["admin_info"] = {
            "total_products": len(products_list),
            "products": products_list,
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

