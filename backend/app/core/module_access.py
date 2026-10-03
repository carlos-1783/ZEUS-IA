"""Control de acceso a verticales/módulos de negocio (dependencia FastAPI real).

Antes de este fichero no existía ningún `require_module` (ni equivalente) en
todo el backend -- confirmado por grep. Cualquier empresa autenticada podía
golpear cualquier endpoint de cualquier vertical, viera o no esa opción en el
menú del frontend. Esta dependencia cierra eso de verdad, con un 403 real
cuando corresponde, consultando `app.core.verticals_registry` (fuente única
de verdad, compartida en espíritu con el frontend vía
`frontend/src/utils/companyModules.ts`).

Uso:
    router = APIRouter(dependencies=[Depends(require_module("insurance"))])

o por endpoint:
    @router.get(...)
    def handler(..., _access: None = Depends(require_module("insurance"))):
        ...
"""

from __future__ import annotations

import logging
from typing import Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.core.verticals_registry import allowed_company_types_for_module
from app.db.base import get_db
from app.models.company import Company, UserCompany
from app.models.user import User

logger = logging.getLogger(__name__)


def _user_has_module_access(db: Session, user: User, module: str) -> bool:
    """Superusuario: bypass total (sigue necesitando auth real, solo salta
    el filtro de módulo). Usuario normal: necesita que AL MENOS una de sus
    empresas tenga un `company_type` listado para `module` en el registro.
    """
    if getattr(user, "is_superuser", False):
        return True

    allowed_types = allowed_company_types_for_module(module)
    if not allowed_types:
        # Registro vacío (o módulo desconocido) = cerrado salvo superusuario.
        return False

    has_access = (
        db.query(UserCompany)
        .join(Company, Company.id == UserCompany.company_id)
        .filter(UserCompany.user_id == user.id)
        .filter(Company.company_type.in_(allowed_types))
        .first()
        is not None
    )
    return has_access


def require_module(module: str) -> Callable:
    """Dependency factory: 403 real si la empresa del usuario autenticado no
    tiene contratado/asignado `module` (y el usuario no es superusuario).
    """

    def dependency(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
    ) -> None:
        if not _user_has_module_access(db, current_user, module):
            logger.warning(
                "module_access_denied module=%s user_id=%s email=%s",
                module, current_user.id, current_user.email,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Tu empresa no tiene acceso al módulo '{module}'",
            )
        return None

    # Marcador introspectable: permite que un test de guardia recorra las
    # rutas de la app y confirme que un router de vertical tiene de verdad
    # `require_module(<ese módulo>)` aplicado, sin depender de levantar una
    # petición HTTP completa por cada router conocido.
    dependency.__module_access__ = module
    return dependency
