"""Segmentación de módulos visibles por company_type (sin eliminar rutas)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.company import Company, UserCompany
from app.models.user import User

COMPANY_TYPE_BAR = "bar_restaurant"
COMPANY_TYPE_OFFICE = "office"
VALID_COMPANY_TYPES = (COMPANY_TYPE_BAR, COMPANY_TYPE_OFFICE)

# Módulos permitidos por tipo (claves alineadas con el menú frontend)
MODULES_BY_COMPANY_TYPE: Dict[str, List[str]] = {
    COMPANY_TYPE_BAR: ["tpv", "control_horario", "payroll"],
    COMPANY_TYPE_OFFICE: ["crm", "analytics", "clients", "payments"],
}

# Siempre visibles para dueño (no empleado)
BASE_OWNER_MODULES = ["dashboard", "settings", "agents"]

BUSINESS_TYPE_TO_COMPANY_TYPE = {
    "restaurant": COMPANY_TYPE_BAR,
    "retail": COMPANY_TYPE_BAR,
    "services": COMPANY_TYPE_OFFICE,
}


def business_type_to_company_type(business_type: Optional[str]) -> str:
    bt = (business_type or "").strip().lower()
    return BUSINESS_TYPE_TO_COMPANY_TYPE.get(bt, COMPANY_TYPE_BAR)


def infer_company_type(company: Company) -> str:
    ct = (getattr(company, "company_type", None) or "").strip().lower()
    if ct in VALID_COMPANY_TYPES:
        return ct
    meta = company.metadata_ if isinstance(company.metadata_, dict) else {}
    bt = meta.get("business_type")
    if bt:
        return business_type_to_company_type(str(bt))
    sector = (company.sector or "").lower()
    if "servicio" in sector or "oficina" in sector or "profesional" in sector:
        return COMPANY_TYPE_OFFICE
    return COMPANY_TYPE_BAR


def get_primary_company(db: Session, user: User) -> Optional[Company]:
    link = (
        db.query(UserCompany)
        .filter(UserCompany.user_id == user.id)
        .order_by(UserCompany.id.asc())
        .first()
    )
    if not link:
        return None
    return db.query(Company).filter(Company.id == link.company_id).first()


def modules_for_company_type(company_type: str, *, is_superuser: bool = False) -> Dict[str, bool]:
    """Mapa de módulos para el frontend (compat con available_modules existente)."""
    if is_superuser:
        return {
            "dashboard": True,
            "analytics": True,
            "tpv": True,
            "control_horario": True,
            "crm": True,
            "payroll": True,
            "clients": True,
            "payments": True,
            "admin": True,
            "settings": True,
            "agents": True,
        }

    ct = company_type if company_type in VALID_COMPANY_TYPES else COMPANY_TYPE_BAR
    allowed = set(MODULES_BY_COMPANY_TYPE.get(ct, []))

    # clients / payments → misma UI CRM oficina
    crm_visible = "crm" in allowed or "clients" in allowed or "payments" in allowed

    return {
        "dashboard": True,
        "analytics": "analytics" in allowed,
        "tpv": "tpv" in allowed,
        "control_horario": "control_horario" in allowed,
        "crm": crm_visible,
        "payroll": "payroll" in allowed,
        "clients": "clients" in allowed,
        "payments": "payments" in allowed,
        "admin": False,
        "settings": True,
        "agents": True,
    }


def get_company_config_for_user(db: Session, user: User) -> Dict[str, Any]:
    is_superuser = bool(getattr(user, "is_superuser", False))
    if is_superuser:
        return {
            "company_id": None,
            "company_name": "ZEUS Platform",
            "company_type": "platform",
            "modules": modules_for_company_type(COMPANY_TYPE_OFFICE, is_superuser=True),
            "module_list": list(MODULES_BY_COMPANY_TYPE.get(COMPANY_TYPE_OFFICE, [])),
        }

    company = get_primary_company(db, user)
    if not company:
        ct = COMPANY_TYPE_BAR
        company_id = None
        company_name = None
    else:
        ct = infer_company_type(company)
        company_id = company.id
        company_name = company.company_name
        if not company.company_type:
            company.company_type = ct

    is_superuser = bool(getattr(user, "is_superuser", False))
    modules = modules_for_company_type(ct, is_superuser=is_superuser)

    return {
        "company_id": company_id,
        "company_name": company_name,
        "company_type": ct,
        "modules": modules,
        "module_list": MODULES_BY_COMPANY_TYPE.get(ct, []),
    }
