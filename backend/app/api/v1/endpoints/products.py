from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.db.session import get_db
from app.models.erp import Product, ProductVariant, InventoryMovement, InventoryMovementType
from app.schemas.erp import (
    ProductCreate, ProductUpdate, ProductInDB, ProductResponse, ProductListResponse,
    ProductVariantCreate, ProductVariantUpdate, ProductVariantInDB,
    InventoryMovementCreate, InventoryMovementInDB
)
from app.core.security import get_current_active_user
from app.models.user import User

router = APIRouter()

def get_product_or_404(
    db: Session,
    product_id: int,
    current_user: User
) -> Product:
    """
    Obtiene un producto por ID o lanza una excepción 404 si no se encuentra.
    
    Args:
        db: Sesión de base de datos
        product_id: ID del producto a buscar
        current_user: Usuario autenticado
        
    Returns:
        Product: El objeto del producto si se encuentra
        
    Raises:
        HTTPException: 404 si el producto no existe
        HTTPException: 403 si el usuario no tiene permisos
    """
    from fastapi import HTTPException, status
    from sqlalchemy.orm import joinedload
    
    # Optimizar la consulta cargando relaciones comunes
    product = db.query(Product).options(
        joinedload(Product.variants),
        joinedload(Product.category),
        joinedload(Product.inventory_movements)
    ).filter(
        Product.id == product_id
    ).first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found"
        )
    
    # Verificar que el usuario tenga acceso al producto
    # Aquí podrías agregar lógica de autorización adicional según tus necesidades
    # Por ejemplo, verificar si el usuario pertenece a la misma organización
    
    return product

@router.get("/", response_model=ProductListResponse)
def list_products(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, le=1000, description="Maximum number of records to return"),
    search: Optional[str] = Query(None, description="Search term for product name, SKU or description"),
    category: Optional[str] = Query(None, description="Filter by product category"),
    status: Optional[str] = Query(None, description="Filter by product status"),
    low_stock: Optional[bool] = Query(None, description="Filter for low stock items"),
    current_user: User = Depends(get_current_active_user)
):
    """
    List all products with optional filtering and pagination
    """
    query = db.query(Product)
    
    # Apply filters
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Product.name.ilike(search_term),
                Product.sku.ilike(search_term),
                Product.description.ilike(search_term)
            )
        )
    
    if category:
        query = query.filter(Product.category == category)
        
    if status:
        query = query.filter(Product.status == status)
        
    if low_stock is not None:
        query = query.filter(
            Product.track_inventory == True,
            Product.quantity_on_hand <= Product.low_stock_threshold
        )
    
    # Get total count for pagination
    total = query.count()
    
    # Apply pagination and ordering
    products = query.order_by(Product.name)\
                   .offset(skip)\
                   .limit(limit)\
                   .all()
    
    # Calculate pagination metadata
    total_pages = (total + limit - 1) // limit if limit > 0 else 1
    current_page = (skip // limit) + 1 if limit > 0 else 1
    
    return {
        "success": True,
        "data": products,
        "total": total,
        "page": current_page,
        "limit": limit,
        "total_pages": total_pages
    }

@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    *,
    db: Session = Depends(get_db),
    product_in: ProductCreate,
    current_user: User = Depends(get_current_active_user)
):
    """
    Create a new product
    """
    # Check if SKU already exists
    existing_product = db.query(Product).filter(
        Product.sku == product_in.sku
    ).first()
    
    if existing_product:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A product with this SKU already exists"
        )
    
    # Create product
    product_data = product_in.dict(exclude={"variants"})
    product = Product(**product_data)
    db.add(product)
    
    # Add variants if provided
    if product_in.variants:
        for variant_data in product_in.variants:
            variant = ProductVariant(
                product=product,
                **variant_data.dict()
            )
            db.add(variant)
    
    db.commit()
    db.refresh(product)
    
    return {"success": True, "data": product}

@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: int = Path(..., description="ID of the product to retrieve"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get a specific product by ID
    """
    product = get_product_or_404(db, product_id, current_user)
    return {"success": True, "data": product}

@router.put("/{product_id}", response_model=ProductResponse)
def update_product(
    *,
    product_id: int = Path(..., description="ID of the product to update"),
    product_in: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Update a product
    """
    product = get_product_or_404(db, product_id, current_user)
    
    # Check if SKU is being updated and if it already exists
    if product_in.sku and product_in.sku != product.sku:
        existing_product = db.query(Product).filter(
            Product.sku == product_in.sku,
            Product.id != product_id
        ).first()
        
        if existing_product:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A product with this SKU already exists"
            )
    
    # Update product fields
    update_data = product_in.dict(exclude_unset=True, exclude={"variants"})
    for field, value in update_data.items():
        setattr(product, field, value)
    
    product.updated_at = func.now()
    db.commit()
    db.refresh(product)
    
    return {"success": True, "data": product}

@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: int = Path(..., description="ID of the product to delete"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete a product
    """
    product = get_product_or_404(db, product_id, current_user)
    
    # In a real application, you might want to check for related records
    # before allowing deletion or implement soft delete
    db.delete(product)
    db.commit()
    
    return None

# Product variants endpoints
@router.post("/{product_id}/variants", response_model=ProductVariantInDB, status_code=status.HTTP_201_CREATED)
def create_product_variant(
    *,
    product_id: int = Path(..., description="ID of the product"),
    variant_in: ProductVariantCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Add a variant to a product
    """
    # Verify product exists
    product = get_product_or_404(db, product_id, current_user)
    
    # Check if variant SKU already exists
    existing_variant = db.query(ProductVariant).filter(
        ProductVariant.sku == variant_in.sku
    ).first()
    
    if existing_variant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A variant with this SKU already exists"
        )
    
    # Create variant
    variant = ProductVariant(
        product_id=product_id,
        **variant_in.dict()
    )
    
    db.add(variant)
    db.commit()
    db.refresh(variant)
    
    return variant

@router.put("/variants/{variant_id}", response_model=ProductVariantInDB)
def update_product_variant(
    *,
    variant_id: int = Path(..., description="ID of the variant to update"),
    variant_in: ProductVariantUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Update a product variant
    """
    # Get variant or 404
    variant = db.query(ProductVariant).filter(ProductVariant.id == variant_id).first()
    if not variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variant with ID {variant_id} not found"
        )
    
    # Check if SKU is being updated and if it already exists
    if variant_in.sku and variant_in.sku != variant.sku:
        existing_variant = db.query(ProductVariant).filter(
            ProductVariant.sku == variant_in.sku,
            ProductVariant.id != variant_id
        ).first()
        
        if existing_variant:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A variant with this SKU already exists"
            )
    
    # Update variant fields
    update_data = variant_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(variant, field, value)
    
    db.commit()
    db.refresh(variant)
    
    return variant

@router.delete("/variants/{variant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product_variant(
    variant_id: int = Path(..., description="ID of the variant to delete"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete a product variant
    """
    variant = db.query(ProductVariant).filter(ProductVariant.id == variant_id).first()
    if not variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variant with ID {variant_id} not found"
        )
    
    db.delete(variant)
    db.commit()
    
    return None

# Inventory management endpoints
@router.post("/{product_id}/inventory/movements", response_model=InventoryMovementInDB, status_code=status.HTTP_201_CREATED)
def create_inventory_movement(
    *,
    product_id: int = Path(..., description="ID of the product"),
    movement_in: InventoryMovementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Record an inventory movement (addition or removal of stock)
    """
    # Verify product exists
    product = get_product_or_404(db, product_id, current_user)
    
    # If variant is specified, verify it exists and belongs to the product
    variant = None
    if movement_in.variant_id:
        variant = db.query(ProductVariant).filter(
            ProductVariant.id == movement_in.variant_id,
            ProductVariant.product_id == product_id
        ).first()
        
        if not variant:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Variant with ID {movement_in.variant_id} not found for this product"
            )
    
    # Create inventory movement
    movement_data = movement_in.dict()
    movement_data["created_by"] = current_user.id
    movement = InventoryMovement(**movement_data)
    
    # Update stock levels
    if variant:
        variant.quantity_on_hand += movement.quantity
    else:
        product.quantity_on_hand += movement.quantity
    
    db.add(movement)
    db.commit()
    db.refresh(movement)
    
    return movement

@router.get("/{product_id}/inventory/movements", response_model=List[InventoryMovementInDB])
def list_inventory_movements(
    product_id: int = Path(..., description="ID of the product"),
    variant_id: Optional[int] = Query(None, description="Filter by variant ID"),
    movement_type: Optional[str] = Query(None, description="Filter by movement type"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, le=1000, description="Maximum number of records to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    List inventory movements for a product
    """
    # Verify product exists
    product = get_product_or_404(db, product_id, current_user)
    
    # Build query
    query = db.query(InventoryMovement).filter(
        InventoryMovement.product_id == product_id
    )
    
    # Apply filters
    if variant_id is not None:
        query = query.filter(InventoryMovement.variant_id == variant_id)
        
    if movement_type:
        query = query.filter(InventoryMovement.movement_type == movement_type)
    
    # Apply pagination and ordering
    movements = query.order_by(InventoryMovement.created_at.desc())\
                    .offset(skip)\
                    .limit(limit)\
                    .all()
    
    return movements
