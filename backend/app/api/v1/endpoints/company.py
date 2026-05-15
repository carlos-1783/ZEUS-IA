"""Configuración de empresa (módulos visibles por company_type)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from services.company_module_config import get_company_config_for_user

router = APIRouter()


@router.get("/config")
def get_company_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    cfg = get_company_config_for_user(db, current_user)
    return {"success": True, **cfg}
