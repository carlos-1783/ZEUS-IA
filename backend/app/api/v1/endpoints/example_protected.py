"""
Ejemplo de endpoints protegidos con autenticación JWT.
Muestra cómo proteger rutas y verificar permisos.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from app.api.dependencies import ActiveUser, AdminUser, get_current_active_user
from app.schemas.token import TokenData
from app.schemas.user import User as UserSchema

router = APIRouter()

@router.get("/me", response_model=UserSchema)
async def read_users_me(current_user: TokenData = Depends(get_current_active_user)):
    """
    Obtiene la información del usuario actualmente autenticado.
    
    Permisos requeridos: Cualquier usuario autenticado
    """
    # En una aplicación real, aquí buscarías los datos del usuario en la base de datos
    # usando current_user.user_id o current_user.sub
    return {
        "id": current_user.user_id,
        "email": current_user.sub,  # Usamos el subject como email
        "is_active": True,
        "is_superuser": "admin" in (current_user.scopes or []),
        "scopes": current_user.scopes or []
    }

@router.get("/admin", dependencies=[Depends(AdminUser)])
async def admin_only_endpoint():
    """
    Endpoint solo accesible para administradores.
    
    Permisos requeridos: Rol de administrador
    """
    return {"message": "¡Bienvenido administrador!"}

@router.get("/items/")
async def read_items(
    current_user: TokenData = Depends(get_current_active_user)
):
    """
    Ejemplo de endpoint protegido que devuelve una lista de elementos.
    
    Permisos requeridos: Cualquier usuario autenticado
    """
    # Lógica de negocio aquí...
    return [{"item_id": 1, "owner": current_user.sub, "data": "Datos protegidos"}]

@router.get("/items/{item_id}")
async def read_item(
    item_id: int,
    current_user: TokenData = Depends(get_current_active_user)
):
    """
    Obtiene un ítem específico por ID.
    
    Permisos requeridos: Usuario autenticado (dueño del ítem o admin)
    """
    # En una aplicación real, verificarías si el usuario es dueño del ítem o es admin
    if item_id == 1 and "admin" not in (current_user.scopes or []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permiso para acceder a este recurso"
        )
    
    return {"item_id": item_id, "owner": current_user.sub}
