"""
Operador TPV desde la sesión autenticada (CompanyEmployee.user_id).
No usar employee_id / teléfono enviados por el cliente para identificar al cobrador.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.company import UserCompany
from app.models.company_employee import CompanyEmployee
from app.models.user import User


def company_ids_for_user(db: Session, user: User):
    rows = db.query(UserCompany.company_id).filter(UserCompany.user_id == user.id).all()
    return [r[0] for r in rows]


def primary_company_id(db: Session, user: User) -> Optional[int]:
    uc = (
        db.query(UserCompany)
        .filter(UserCompany.user_id == user.id)
        .order_by(UserCompany.id.asc())
        .first()
    )
    return uc.company_id if uc else None


def session_company_employee(db: Session, user: User) -> Optional[CompanyEmployee]:
    cids = company_ids_for_user(db, user)
    if not cids:
        return None
    return (
        db.query(CompanyEmployee)
        .filter(
            CompanyEmployee.user_id == user.id,
            CompanyEmployee.company_id.in_(cids),
            CompanyEmployee.is_active.is_(True),
        )
        .order_by(CompanyEmployee.id.asc())
        .first()
    )


def tpv_requires_phone_verification(current_user: User, svc: Any) -> bool:
    profile_raw = str(getattr(current_user, "tpv_business_profile", "") or "").strip().lower()
    if profile_raw in {"bar", "restaurante", "restaurant"}:
        return True
    return str(getattr(svc.business_profile, "value", "")).lower() in {
        "restaurante",
        "bar",
        "restaurant",
    }


def resolve_tpv_operator_employee_code(db: Session, current_user: User, svc: Any) -> str:
    """
    Código de empleado en ticket / cierre: ficha RRHH vinculada a la sesión, o id de usuario.
    """
    ce = session_company_employee(db, current_user)
    role = (getattr(current_user, "role", None) or "owner").strip().lower()
    hosteleria = tpv_requires_phone_verification(current_user, svc)
    req_emp = bool(getattr(svc, "config", None) and svc.config.get("requires_employee"))

    if ce:
        if hosteleria:
            phone = re.sub(r"\D+", "", str(ce.phone or ""))
            if not phone:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El empleado no tiene móvil registrado en RRHH; no se puede cobrar en hostelería.",
                )
        return str(ce.employee_code)

    if role == "employee" and (hosteleria or req_emp):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta debe tener una ficha en RRHH vinculada a este usuario para operar en el TPV.",
        )
    return str(current_user.id)


def tpv_operator_badge_payload(db: Session, current_user: User, svc: Any) -> Dict[str, Any]:
    ce = session_company_employee(db, current_user)
    if ce:
        return {
            "employee_code": ce.employee_code,
            "full_name": ce.full_name,
            "role_title": ce.role_title or "",
            "source": "company_employee",
        }
    role = (getattr(current_user, "role", None) or "owner").strip().lower()
    return {
        "employee_code": None,
        "full_name": current_user.full_name or current_user.email or "",
        "role_title": role,
        "source": "user_session",
    }
