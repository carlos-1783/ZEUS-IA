"""Exportación de datos de usuario y claves API personales."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from services import user_settings_service as uss
from services.analytics_service import build_analytics_summary
from services.company_module_config import get_company_config_for_user
import services.crm_office_service as crm_svc

router = APIRouter()


def _user_export_payload(db: Session, user: User) -> Dict[str, Any]:
    settings_row = uss.get_or_create_user_settings(db, user.id)
    company_cfg = get_company_config_for_user(db, user)
    customers = crm_svc.list_customers(db, user)
    analytics = build_analytics_summary(db, user, days=30)

    return {
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "phone": user.phone,
            "role": getattr(user, "role", "owner"),
            "company_name": user.company_name,
            "plan": user.plan,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        "settings": uss.settings_to_api(settings_row),
        "company": {
            "company_id": company_cfg.get("company_id"),
            "company_type": company_cfg.get("company_type"),
            "modules": company_cfg.get("modules"),
        },
        "customers_summary": {
            "total": len(customers),
            "items": [
                {
                    "id": c.id,
                    "name": getattr(c, "name", None) or getattr(c, "full_name", None),
                    "email": c.email,
                }
                for c in customers[:200]
            ],
        },
        "analytics_30d": analytics,
    }


@router.get("/export")
async def export_user_data(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Exporta perfil, ajustes, clientes y métricas del usuario (sin contraseñas)."""
    payload = _user_export_payload(db, current_user)
    filename = f"zeus-export-{datetime.utcnow().strftime('%Y-%m-%d')}.json"
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/api-keys")
async def generate_api_key(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Genera una clave API personal (se muestra una sola vez)."""
    raw = f"zeus_{secrets.token_urlsafe(32)}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    row = uss.get_or_create_user_settings(db, current_user.id)
    if hasattr(row, "api_key_hash"):
        row.api_key_hash = digest
        row.api_key_prefix = raw[:12]
        db.commit()
    return {
        "success": True,
        "api_key": raw,
        "key": raw,
        "prefix": raw[:12],
        "message": "Guarda esta clave; no se volverá a mostrar.",
    }
