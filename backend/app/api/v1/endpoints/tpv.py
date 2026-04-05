"""
💳 TPV Universal Enterprise API Endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from decimal import Decimal
from sqlalchemy import func
from sqlalchemy.orm import Session
import logging
from pathlib import Path
from datetime import datetime, date, timedelta, timezone
import secrets
import uuid

from app.db.session import get_db
from app.core.auth import get_current_active_user, get_current_active_superuser
from app.core.config import settings
from app.models.user import User
from app.models.company import UserCompany
from app.models.erp import TPVProduct, FiscalProfile, TPVSale, TPVSaleItem
from app.models.reservation import Reservation
from app.models.tpv_comanda_share import TPVComandaShare
from app.models.tpv_table import TPVTable
from services.tpv_service import BusinessProfile, PaymentMethod, TPVService, create_tpv_service
from services.global_company_bootstrap import ensure_user_company_link_for_operations

router = APIRouter()
logger = logging.getLogger(__name__)


def _tpv_service_for_user(db: Session, current_user: User):
    """Instancia TPV por petición + perfil desde BD (sin estado de carrito compartido)."""
    svc = create_tpv_service()
    is_superuser = getattr(current_user, "is_superuser", False)
    user = db.query(User).filter(User.id == current_user.id).first()
    if user:
        user_data = {
            "id": user.id,
            "tpv_business_profile": getattr(user, "tpv_business_profile", None),
            "company_name": getattr(user, "company_name", None),
        }
        try:
            svc.load_user_profile(user_data)
        except Exception as e:
            logger.warning("Error cargando perfil de usuario TPV: %s", e)
            if not svc.business_profile:
                svc.set_business_profile(BusinessProfile.OTROS, user.id)
    else:
        user_data = {
            "id": current_user.id,
            "company_name": getattr(current_user, "company_name", None),
        }
        try:
            svc.load_user_profile(user_data)
        except Exception as e:
            logger.warning("Error cargando perfil TPV: %s", e)
        if not svc.business_profile and not is_superuser:
            svc.set_business_profile(BusinessProfile.OTROS, current_user.id)
        elif not svc.business_profile and is_superuser:
            svc.set_business_profile(BusinessProfile.OTROS, current_user.id)
    if not svc.business_profile:
        svc.set_business_profile(BusinessProfile.OTROS, current_user.id)
    return svc


def _users_share_company(db: Session, user_a_id: int, user_b_id: int) -> bool:
    """True si ambos usuarios están vinculados a la misma empresa (user_companies)."""
    if user_a_id == user_b_id:
        return True
    ca = {r[0] for r in db.query(UserCompany.company_id).filter(UserCompany.user_id == user_a_id).all()}
    cb = {r[0] for r in db.query(UserCompany.company_id).filter(UserCompany.user_id == user_b_id).all()}
    return bool(ca & cb)


def _company_ids_for_user(db: Session, user: User) -> List[int]:
    rows = db.query(UserCompany.company_id).filter(UserCompany.user_id == user.id).all()
    return [r[0] for r in rows]


def _primary_company_id(db: Session, user: User) -> Optional[int]:
    uc = (
        db.query(UserCompany)
        .filter(UserCompany.user_id == user.id)
        .order_by(UserCompany.id.asc())
        .first()
    )
    return uc.company_id if uc else None


def _can_manage_tpv_tables(user: User) -> bool:
    """Crear/borrar mesas: dueño o superusuario; no empleado estándar."""
    if getattr(user, "is_superuser", False):
        return True
    role = (getattr(user, "role", None) or "owner").strip().lower()
    return role != "employee"


def _tpv_table_row_allowed(db: Session, user: User, row: TPVTable) -> bool:
    return row.company_id in _company_ids_for_user(db, user)


def _tpv_table_to_api_dict(row: TPVTable) -> Dict[str, Any]:
    return {
        "id": row.id,
        "company_id": row.company_id,
        "number": row.number,
        "name": row.name,
        "status": row.status,
        "order_total": float(row.order_total or 0),
        "cart_snapshot": row.cart_snapshot,
    }


def _can_view_comanda_share(db: Session, viewer: User, row: TPVComandaShare) -> bool:
    if getattr(viewer, "is_superuser", False):
        return True
    if viewer.id == row.owner_user_id:
        return True
    role = (getattr(viewer, "role", None) or "owner").strip().lower()
    # Empleado: acceso con enlace secreto + cuenta empleado (evita depender solo de user_companies).
    if role == "employee":
        return True
    return _users_share_company(db, row.owner_user_id, viewer.id)


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


class ComandaShareUpsertRequest(BaseModel):
    """Snapshot JSON: tableCarts, tables, cart, products, tablesMode, selectedTable, etc."""
    share_id: Optional[str] = None
    payload: Dict[str, Any]


class TPVTableCreateBody(BaseModel):
    number: Optional[int] = None
    name: Optional[str] = None


class TPVTablePatchBody(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    order_total: Optional[float] = None
    cart_snapshot: Optional[List[Any]] = None


class AddToCartRequest(BaseModel):
    product_id: str
    quantity: int = 1


class ProcessSaleRequest(BaseModel):
    payment_method: str  # efectivo, tarjeta, bizum, transferencia
    employee_id: Optional[str] = None
    terminal_id: Optional[str] = None
    customer_data: Optional[Dict[str, Any]] = None
    cart_items: Optional[List[Dict[str, Any]]] = None  # Carrito del frontend (opcional)
    consumption_type: Optional[str] = None  # onsite | takeaway (ZEUS_TPV_FULL_FISCAL_INFRASTRUCTURE_ES_003)


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


class FiscalProfileCreate(BaseModel):
    """ZEUS_TPV_FULL_FISCAL_INFRASTRUCTURE_ES_003"""
    vat_regime: str = "general"  # general | recargo_equivalencia | exento
    apply_recargo_equivalencia: bool = False
    recargo_rate: Optional[float] = None  # e.g. 5.2 for 5.2%


async def _get_tpv_info(db: Session, current_user: User):
    """Información del TPV; perfil y conteos por usuario (sin carrito en servidor)."""
    is_superuser = getattr(current_user, "is_superuser", False)
    svc = _tpv_service_for_user(db, current_user)
    config = svc.config if svc.business_profile else {}
    if is_superuser and not config:
        config = {
            "tables_enabled": True,
            "services_enabled": True,
            "appointments_enabled": True,
            "products_enabled": True,
            "stock_enabled": True,
            "discounts_enabled": True,
            "requires_employee": False,
            "requires_customer_data": False,
            "superuser_override": True,
        }
    products_count = (
        db.query(TPVProduct).filter(TPVProduct.user_id == current_user.id).count()
        if current_user
        else 0
    )
    company_ids = _company_ids_for_user(db, current_user)
    return {
        "success": True,
        "service": "TPV Universal Enterprise",
        "version": "1.0.0",
        "user": {
            "email": current_user.email,
            "is_superuser": is_superuser,
            "is_active": current_user.is_active,
        },
        "endpoints": {
            "status": "/api/v1/tpv/status",
            "products": "/api/v1/tpv/products",
            "cart": "/api/v1/tpv/cart",
            "sale": "/api/v1/tpv/sale",
            "invoice": "/api/v1/tpv/invoice",
            "close_register": "/api/v1/tpv/close-register",
            "detect_business_type": "/api/v1/tpv/detect-business-type",
        },
        "business_profile": svc.business_profile.value if svc.business_profile else None,
        "config": config,
        "products_count": products_count,
        "company_ids": company_ids,
        "integrations": {
            "rafael": svc.rafael_integration is not None,
            "justicia": svc.justicia_integration is not None,
            "afrodita": svc.afrodita_integration is not None,
        },
    }


@router.get("", include_in_schema=True)
@router.get("/", include_in_schema=True)
async def get_tpv_root(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Endpoint raíz del TPV - Devuelve información básica y endpoints disponibles"""
    return await _get_tpv_info(db, current_user)


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
    
    svc = create_tpv_service()
    profile = svc.auto_detect_business_type(business_data)

    return {
        "success": True,
        "business_profile": profile.value,
        "detected_by": "TPV Auto-Detection",
    }


@router.post("/products")
async def create_product(
    request: ProductCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Crear producto en el TPV - PERSISTIDO EN BD CON MULTI-TENANCY"""
    is_superuser = getattr(current_user, 'is_superuser', False)
    
    # Permisos: Todos los usuarios autenticados pueden crear productos
    # (No restringir por rol, solo requiere autenticación)
    
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


@router.post("/comanda-share")
async def upsert_comanda_share(
    body: ComandaShareUpsertRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Publicar o actualizar instantánea de comanda (mesas + carritos) para compartir entre dispositivos.
    - Crear share nuevo: solo dueño/superusuario.
    - Actualizar share existente: dueño o cualquier usuario con acceso al share (p.ej. empleado con enlace).
    """
    now = datetime.now(timezone.utc)
    ttl = timedelta(days=7)

    if body.share_id:
        row = db.query(TPVComandaShare).filter(TPVComandaShare.id == body.share_id.strip()).first()
        if not row:
            raise HTTPException(status_code=404, detail="Sesión de comanda no encontrada")
        if not _can_view_comanda_share(db, current_user, row):
            raise HTTPException(status_code=403, detail="No tienes acceso para actualizar esta comanda")
        row.payload = body.payload
        row.updated_at = now
        if row.expires_at is None:
            row.expires_at = now + ttl
        db.commit()
        return {"success": True, "share_id": row.id}

    role = (getattr(current_user, "role", None) or "owner").strip().lower()
    if role == "employee" and not getattr(current_user, "is_superuser", False):
        raise HTTPException(status_code=403, detail="Solo el dueño puede crear una nueva comanda compartida")

    sid = str(uuid.uuid4())
    row = TPVComandaShare(
        id=sid,
        owner_user_id=current_user.id,
        payload=body.payload,
        expires_at=now + ttl,
    )
    db.add(row)
    db.commit()
    return {"success": True, "share_id": sid}


@router.get("/comanda-share/{share_id}")
async def get_comanda_share(
    share_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Obtener instantánea si el usuario es dueño o empleado de la misma empresa."""
    row = db.query(TPVComandaShare).filter(TPVComandaShare.id == share_id.strip()).first()
    if not row:
        raise HTTPException(status_code=404, detail="Comanda no encontrada")

    if row.expires_at:
        exp = row.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < datetime.now(timezone.utc):
            raise HTTPException(status_code=410, detail="Enlace de comanda caducado")

    if not _can_view_comanda_share(db, current_user, row):
        raise HTTPException(
            status_code=403,
            detail="No tienes acceso a esta comanda. Debes estar vinculado a la misma empresa que el dueño.",
        )

    return {
        "success": True,
        "share_id": row.id,
        "owner_user_id": row.owner_user_id,
        "payload": row.payload,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get("/tables")
async def list_tpv_tables(
    company_id: Optional[int] = Query(
        None,
        description="Opcional: filtrar por empresa. Debe ser una empresa vinculada al usuario (user_companies).",
    ),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Listar mesas persistidas en BD (tpv_tables), scoped por empresa del usuario.
    Sin company_id: todas las empresas vinculadas. Con company_id: solo si el usuario pertenece a esa empresa.
    Equivale a GET /api/tables?company_id= con prefijo API v1: /api/v1/tpv/tables?company_id=
    """
    # Dueños sin fila user_companies (registro antiguo) reciben empresa mínima para poder usar TPV.
    ensure_user_company_link_for_operations(db, current_user)
    cids = _company_ids_for_user(db, current_user)
    if not cids:
        return {"success": True, "tables": []}
    if company_id is not None:
        if company_id not in cids:
            raise HTTPException(
                status_code=403,
                detail="No tienes acceso a la empresa indicada o no existe en tu cuenta.",
            )
        filter_ids = [company_id]
    else:
        filter_ids = list(cids)
    rows = (
        db.query(TPVTable)
        .filter(TPVTable.company_id.in_(filter_ids))
        .order_by(TPVTable.company_id.asc(), TPVTable.number.asc())
        .all()
    )
    return {"success": True, "tables": [_tpv_table_to_api_dict(r) for r in rows]}


@router.post("/tables")
async def create_tpv_table(
    body: TPVTableCreateBody,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if not _can_manage_tpv_tables(current_user):
        raise HTTPException(status_code=403, detail="Solo el dueño puede crear mesas")
    ensure_user_company_link_for_operations(db, current_user)
    cid = _primary_company_id(db, current_user)
    if not cid:
        raise HTTPException(
            status_code=400,
            detail="No hay empresa vinculada a tu cuenta. Completa el registro o contacta con soporte.",
        )
    number = body.number
    if number is None:
        mx = db.query(func.max(TPVTable.number)).filter(TPVTable.company_id == cid).scalar()
        number = int(mx or 0) + 1
    exists = (
        db.query(TPVTable)
        .filter(TPVTable.company_id == cid, TPVTable.number == number)
        .first()
    )
    if exists:
        raise HTTPException(status_code=409, detail="Ya existe una mesa con ese número en tu local")
    name = (body.name or "").strip() or f"Mesa {number}"
    row = TPVTable(
        company_id=cid,
        number=number,
        name=name,
        status="free",
        order_total=Decimal("0"),
        cart_snapshot=None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info(f"🪑 Mesa TPV creada id={row.id} company={cid} number={number} user={current_user.id}")
    return {"success": True, "table": _tpv_table_to_api_dict(row)}


@router.patch("/tables/{table_id}")
async def patch_tpv_table(
    table_id: int,
    body: TPVTablePatchBody,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    row = db.query(TPVTable).filter(TPVTable.id == table_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Mesa no encontrada")
    if not _tpv_table_row_allowed(db, current_user, row):
        raise HTTPException(status_code=403, detail="No tienes acceso a esta mesa")
    if body.name is not None:
        row.name = body.name.strip() or row.name
    if body.status is not None:
        row.status = body.status.strip() or row.status
    if body.order_total is not None:
        row.order_total = Decimal(str(body.order_total))
    if body.cart_snapshot is not None:
        row.cart_snapshot = body.cart_snapshot
    db.commit()
    db.refresh(row)
    return {"success": True, "table": _tpv_table_to_api_dict(row)}


@router.delete("/tables/{table_id}")
async def delete_tpv_table(
    table_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if not _can_manage_tpv_tables(current_user):
        raise HTTPException(status_code=403, detail="Solo el dueño puede eliminar mesas")
    row = db.query(TPVTable).filter(TPVTable.id == table_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Mesa no encontrada")
    if not _tpv_table_row_allowed(db, current_user, row):
        raise HTTPException(status_code=403, detail="No tienes acceso a esta mesa")
    db.delete(row)
    db.commit()
    return {"success": True, "deleted_id": table_id}


@router.put("/products/{product_id}")
async def update_product(
    product_id: str,
    request: ProductCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Actualizar producto en el TPV - MULTI-TENANCY: Solo productos del usuario"""
    is_superuser = getattr(current_user, 'is_superuser', False)
    
    # Permisos: Todos los usuarios autenticados pueden actualizar sus propios productos
    
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
    
    # Permisos: Todos los usuarios autenticados pueden subir imágenes
    
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
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Valida producto del usuario y devuelve línea + total de esa línea (no persiste carrito en servidor)."""
    ensure_user_company_link_for_operations(db, current_user)
    db_product = (
        db.query(TPVProduct)
        .filter(
            TPVProduct.product_id == request.product_id,
            TPVProduct.user_id == current_user.id,
        )
        .first()
    )
    if not db_product:
        raise HTTPException(
            status_code=400,
            detail=f"Producto {request.product_id} no encontrado",
        )
    try:
        line = TPVService.cart_line_from_product_row(db_product, request.quantity)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "success": True,
        "cart_item": line,
        "cart_total": TPVService.compute_cart_total([line]),
        "server_side_cart": False,
    }


@router.get("/cart")
async def get_cart(
    current_user: User = Depends(get_current_active_user),
):
    """El carrito vive en el cliente; el servidor no almacena líneas entre peticiones."""
    return {
        "success": True,
        "cart": [],
        "total": {"subtotal": 0.0, "iva": 0.0, "total": 0.0, "items_count": 0},
        "server_side_cart": False,
        "message": "Carrito en cliente; envíe cart_items en POST /api/v1/tpv/sale.",
    }


@router.delete("/cart")
async def clear_cart(
    current_user: User = Depends(get_current_active_user),
):
    """No-op compatible: el carrito no está en el servidor."""
    return {
        "success": True,
        "message": "Carrito gestionado en cliente; nada que limpiar en servidor.",
        "server_side_cart": False,
    }


@router.post("/sale")
async def process_sale(
    request: ProcessSaleRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Procesar venta: cart_items obligatorio; persistencia fiscal en BD o error 5xx."""
    try:
        payment_method = PaymentMethod(request.payment_method.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Método de pago inválido. Válidos: {[m.value for m in PaymentMethod]}",
        )

    ensure_user_company_link_for_operations(db, current_user)
    if not request.cart_items:
        raise HTTPException(
            status_code=400,
            detail="cart_items es obligatorio y no puede estar vacío",
        )

    cart_lines: List[Dict[str, Any]] = []
    for item in request.cart_items:
        product_id = item.get("product_id")
        quantity = item.get("quantity", 1)
        if not product_id:
            raise HTTPException(status_code=400, detail="Cada línea debe incluir product_id")
        db_product = (
            db.query(TPVProduct)
            .filter(
                TPVProduct.product_id == product_id,
                TPVProduct.user_id == current_user.id,
            )
            .first()
        )
        if not db_product:
            raise HTTPException(
                status_code=400,
                detail=f"Producto {product_id} no encontrado o no pertenece a su cuenta",
            )
        try:
            cart_lines.append(
                TPVService.cart_line_from_product_row(db_product, quantity)
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    svc = _tpv_service_for_user(db, current_user)
    company_ids = _company_ids_for_user(db, current_user)
    logger.info(
        "TPV venta intento user_id=%s email=%s company_ids=%s lineas=%s",
        current_user.id,
        getattr(current_user, "email", None),
        company_ids,
        len(cart_lines),
    )
    try:
        result = svc.process_sale(
            payment_method=payment_method,
            cart_lines=cart_lines,
            employee_id=request.employee_id,
            terminal_id=request.terminal_id,
            customer_data=request.customer_data,
            user_id=current_user.id,
            db=db,
            consumption_type=request.consumption_type,
        )
    except Exception:
        logger.exception(
            "TPV venta fallo (persistencia u error interno) user_id=%s",
            current_user.id,
        )
        raise HTTPException(
            status_code=500,
            detail="No se pudo registrar la venta en base de datos. Inténtelo de nuevo o contacte con soporte.",
        )

    if not result.get("success"):
        logger.warning(
            "TPV venta rechazada validación user_id=%s detalle=%s",
            current_user.id,
            result.get("error"),
        )
        raise HTTPException(status_code=400, detail=result.get("error"))

    logger.info(
        "TPV venta ok user_id=%s ticket_id=%s fiscal_snapshot_id=%s",
        current_user.id,
        result.get("ticket_id"),
        (result.get("ticket") or {}).get("fiscal_snapshot_id"),
    )
    return result


@router.post("/invoice")
async def generate_invoice(
    request: GenerateInvoiceRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Generar factura desde ticket"""
    svc = _tpv_service_for_user(db, current_user)
    result = svc.generate_invoice(
        ticket_id=request.ticket_id,
        customer_data=request.customer_data,
    )
    return result


@router.post("/close-register")
async def close_register(
    request: CloseRegisterRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Cerrar caja del terminal"""
    svc = _tpv_service_for_user(db, current_user)
    result = svc.close_register(
        terminal_id=request.terminal_id,
        employee_id=request.employee_id,
        initial_cash=request.initial_cash,
        final_cash=request.final_cash,
    )
    return result


# ----- ZEUS_TPV_FULL_FISCAL_INFRASTRUCTURE_ES_003: perfil fiscal y exportación modelo 303 -----

@router.get("/fiscal-profile")
async def get_fiscal_profile(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Obtener perfil fiscal del usuario (régimen IVA, recargo equivalencia)."""
    profile = db.query(FiscalProfile).filter(FiscalProfile.user_id == current_user.id).first()
    if not profile:
        return {"profile": None}
    return {
        "profile": {
            "id": profile.id,
            "vat_regime": profile.vat_regime,
            "apply_recargo_equivalencia": profile.apply_recargo_equivalencia,
            "recargo_rate": float(profile.recargo_rate) if profile.recargo_rate is not None else None,
        }
    }


@router.post("/fiscal-profile")
async def set_fiscal_profile(
    request: FiscalProfileCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Crear o actualizar perfil fiscal (régimen IVA y recargo de equivalencia)."""
    profile = db.query(FiscalProfile).filter(FiscalProfile.user_id == current_user.id).first()
    recargo = request.recargo_rate
    if request.apply_recargo_equivalencia and recargo is None:
        recargo = 5.2  # 5.2% típico recargo equivalencia
    if profile:
        profile.vat_regime = request.vat_regime
        profile.apply_recargo_equivalencia = request.apply_recargo_equivalencia
        profile.recargo_rate = recargo
    else:
        profile = FiscalProfile(
            user_id=current_user.id,
            vat_regime=request.vat_regime,
            apply_recargo_equivalencia=request.apply_recargo_equivalencia,
            recargo_rate=recargo,
        )
        db.add(profile)
    db.commit()
    db.refresh(profile)
    return {
        "success": True,
        "profile": {
            "id": profile.id,
            "vat_regime": profile.vat_regime,
            "apply_recargo_equivalencia": profile.apply_recargo_equivalencia,
            "recargo_rate": float(profile.recargo_rate) if profile.recargo_rate is not None else None,
        },
    }


@router.get("/fiscal/quarterly-vat")
async def get_quarterly_vat(
    year: int,
    quarter: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Exportación trimestral para modelo 303 (AEAT).
    Agrupa por tipo de IVA (4%, 10%, 21%) y recargo. Ventas históricas protegidas (solo lectura).
    """
    from datetime import date, datetime as dt
    start_month = (quarter - 1) * 3 + 1
    end_month = quarter * 3
    start_d = date(year, start_month, 1)
    if end_month == 12:
        end_d = date(year + 1, 1, 1)
    else:
        end_d = date(year, end_month + 1, 1)
    # Comparar con inicio/fin de día para DateTime(timezone=True)
    start_ts = dt.combine(start_d, dt.min.time())
    end_ts = dt.combine(end_d, dt.min.time())
    sales = (
        db.query(TPVSale)
        .filter(
            TPVSale.user_id == current_user.id,
            TPVSale.sale_date >= start_ts,
            TPVSale.sale_date < end_ts,
        )
        .all()
    )
    base_4 = base_10 = base_21 = iva_4 = iva_10 = iva_21 = recargo_total = grand_total = 0.0
    for s in sales:
        for item in s.items:
            rate_pct = float(item.tax_rate_snapshot or 0) * 100
            base = float(item.base_amount or 0)
            iva = float(item.tax_amount or 0)
            if rate_pct <= 5:
                base_4 += base
                iva_4 += iva
            elif rate_pct <= 15:
                base_10 += base
                iva_10 += iva
            else:
                base_21 += base
                iva_21 += iva
            recargo_total += float(item.recargo_amount or 0)
        grand_total += float(s.total or 0)
    return {
        "period": f"{year}-Q{quarter}",
        "base_4": round(base_4, 2),
        "iva_4": round(iva_4, 2),
        "base_10": round(base_10, 2),
        "iva_10": round(iva_10, 2),
        "base_21": round(base_21, 2),
        "iva_21": round(iva_21, 2),
        "recargo_total": round(recargo_total, 2),
        "grand_total": round(grand_total, 2),
        "modelo_303_ready": True,
    }


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
    
    svc = _tpv_service_for_user(db, current_user)

    return {
        "success": True,
        "business_profile": profile.value,
        "config": svc.config,
        "message": f"Business profile actualizado a: {profile.value}",
    }


@router.get("/status")
async def get_tpv_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Obtener estado del TPV - Los superusuarios ven información completa"""
    is_superuser = getattr(current_user, "is_superuser", False)
    svc = _tpv_service_for_user(db, current_user)
    products_count = (
        db.query(TPVProduct).filter(TPVProduct.user_id == current_user.id).count()
    )
    company_ids = _company_ids_for_user(db, current_user)

    status = {
        "success": True,
        "business_profile": svc.business_profile.value if svc.business_profile else None,
        "config": svc.config if svc.business_profile else {},
        "products_count": products_count,
        "cart_items": 0,
        "server_side_cart": False,
        "company_ids": company_ids,
        "integrations": {
            "rafael": svc.rafael_integration is not None,
            "justicia": svc.justicia_integration is not None,
            "afrodita": svc.afrodita_integration is not None,
        },
        "user": {
            "email": current_user.email,
            "is_superuser": is_superuser,
            "is_active": current_user.is_active,
        },
    }

    if is_superuser:
        user_products = (
            db.query(TPVProduct).filter(TPVProduct.user_id == current_user.id).all()
        )
        products_list = [
            {
                "id": db_product.product_id,
                "name": db_product.name,
                "price": db_product.price,
                "price_with_iva": db_product.price_with_iva,
                "category": db_product.category,
            }
            for db_product in user_products
        ]
        status["admin_info"] = {
            "total_products": len(products_list),
            "products": products_list,
            "categories": list(svc.categories.values()) if svc.categories else [],
            "cart": [],
            "server_side_cart": False,
            "employees_count": len(svc.employees),
            "terminals_count": len(svc.terminals),
            "pricing_rules_count": len(svc.pricing_rules),
            "inventory_sync_enabled": svc.inventory_sync_enabled,
            "employees": list(svc.employees.values()) if svc.employees else [],
            "terminals": list(svc.terminals.values()) if svc.terminals else [],
        }

    return status


# ----- Reservas del día + Abrir como mesa -----

@router.get("/reservations")
async def get_reservations(
    date_param: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Lista reservas del día (o de la fecha indicada) para el negocio del usuario."""
    if date_param:
        try:
            day = date.fromisoformat(date_param)
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha inválido (YYYY-MM-DD)")
    else:
        day = date.today()
    rows = (
        db.query(Reservation)
        .filter(Reservation.user_id == current_user.id, Reservation.reservation_date == day)
        .order_by(Reservation.reservation_time, Reservation.id)
        .all()
    )
    return {
        "date": day.isoformat(),
        "reservations": [
            {
                "id": r.id,
                "guest_name": r.guest_name,
                "guest_phone": r.guest_phone,
                "guest_email": r.guest_email,
                "reservation_time": r.reservation_time,
                "num_guests": r.num_guests,
                "notes": r.notes,
                "status": r.status,
                "table_id": r.table_id,
                "table_name": r.table_name,
                "source": r.source,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


class SeatReservationRequest(BaseModel):
    table_id: Optional[str] = None
    table_name: Optional[str] = None


@router.patch("/reservations/{reservation_id}/seat")
async def seat_reservation(
    reservation_id: int,
    body: SeatReservationRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Marca la reserva como sentada y asigna mesa (abrir como mesa en TPV)."""
    r = db.query(Reservation).filter(
        Reservation.id == reservation_id,
        Reservation.user_id == current_user.id,
    ).first()
    if not r:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
    r.status = "seated"
    if body.table_id is not None:
        r.table_id = body.table_id
    if body.table_name is not None:
        r.table_name = body.table_name
    db.commit()
    db.refresh(r)
    return {"success": True, "reservation": {"id": r.id, "status": r.status, "table_id": r.table_id, "table_name": r.table_name}}


# ----- ZEUS_TPV_GLOBAL_AUDIT_001 -----

@router.get("/audit")
async def get_tpv_global_audit(
    current_user: User = Depends(get_current_active_superuser),
    db: Session = Depends(get_db),
    save_file: bool = False,
):
    """
    Ejecuta la auditoría global TPV (ROCE ZEUS_TPV_GLOBAL_AUDIT_001).
    Solo superusuarios. Modo ANALYZE_FIRST: no modifica datos, solo genera informe.
    """
    from services.tpv_global_audit import run_tpv_global_audit, save_audit_report_to_file

    report = run_tpv_global_audit(db)
    if save_file:
        try:
            path = save_audit_report_to_file(report)
            report["_report_file"] = str(path)
        except Exception as e:
            logger.warning("No se pudo guardar informe de auditoría en archivo: %s", e)
    return report

