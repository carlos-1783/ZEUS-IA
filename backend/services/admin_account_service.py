"""Operaciones de cuenta para superadmin (desactivar / eliminar con motivo)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.user import User, RefreshToken, PasswordResetToken
from app.models.company import Company, UserCompany
from app.models.agent_activity import AgentActivity
from app.models.document_approval import DocumentApproval
from app.models.customer import Customer, ContactPerson
from app.models.erp import TPVSale, TPVSaleItem, TPVProduct
from app.models.chat_message import ChatMessage
from app.models.time_tracking import (
    TimeTrackingRecord,
    EmployeeSchedule,
    TimeControlEvent,
    TimeControlAlert,
    AttendanceReport,
)
from app.models.automation_readiness import AutomationReadiness

logger = logging.getLogger(__name__)

ALLOWED_DEACTIVATION_REASONS = frozenset(
    {
        "test_account",
        "duplicate",
        "customer_request",
        "non_payment",
        "inactive",
        "fraud",
        "other",
    }
)


def _company_ids_for_user(db: Session, user_id: int) -> List[int]:
    rows = (
        db.query(UserCompany.company_id)
        .filter(UserCompany.user_id == user_id)
        .all()
    )
    return [r[0] for r in rows]


def companies_exclusive_to_user(db: Session, user_id: int) -> List[int]:
    exclusive: List[int] = []
    for cid in _company_ids_for_user(db, user_id):
        others = (
            db.query(UserCompany.user_id)
            .filter(UserCompany.company_id == cid, UserCompany.user_id != user_id)
            .count()
        )
        if others == 0:
            exclusive.append(cid)
    return exclusive


def _purge_user_rows(db: Session, user: User) -> Dict[str, int]:
    uid = user.id
    email = user.email
    counts: Dict[str, int] = {}

    def bump(key: str, n: int) -> None:
        counts[key] = counts.get(key, 0) + n

    n = db.query(AgentActivity).filter(AgentActivity.user_email == email).delete(
        synchronize_session=False
    )
    bump("agent_activities", n)

    n = db.query(DocumentApproval).filter(DocumentApproval.user_id == uid).delete(
        synchronize_session=False
    )
    bump("document_approvals", n)

    sale_ids = [r[0] for r in db.query(TPVSale.id).filter(TPVSale.user_id == uid).all()]
    if sale_ids:
        db.query(TPVSaleItem).filter(TPVSaleItem.tpv_sale_id.in_(sale_ids)).delete(
            synchronize_session=False
        )
        db.query(TPVSale).filter(TPVSale.user_id == uid).delete(synchronize_session=False)
    bump("tpv_sales", len(sale_ids))

    n = db.query(TPVProduct).filter(TPVProduct.user_id == uid).delete(synchronize_session=False)
    bump("tpv_products", n)

    cust_ids = [r[0] for r in db.query(Customer.id).filter(Customer.owner_user_id == uid).all()]
    if cust_ids:
        db.query(ContactPerson).filter(ContactPerson.customer_id.in_(cust_ids)).delete(
            synchronize_session=False
        )
        db.query(Customer).filter(Customer.id.in_(cust_ids)).delete(synchronize_session=False)
    bump("customers_owner", len(cust_ids))

    for model, label in (
        (TimeTrackingRecord, "time_tracking_records"),
        (EmployeeSchedule, "employee_schedules"),
        (TimeControlEvent, "time_control_events"),
        (TimeControlAlert, "time_control_alerts"),
        (AttendanceReport, "attendance_reports"),
    ):
        n = db.query(model).filter(model.user_id == uid).delete(synchronize_session=False)
        bump(label, n)

    n = db.query(AutomationReadiness).filter(AutomationReadiness.company_id == uid).delete(
        synchronize_session=False
    )
    bump("automation_readiness", n)

    n = db.query(RefreshToken).filter(RefreshToken.user_id == uid).delete(synchronize_session=False)
    bump("refresh_tokens", n)

    n = db.query(PasswordResetToken).filter(PasswordResetToken.email == email).delete(
        synchronize_session=False
    )
    bump("password_reset_tokens", n)

    n = db.query(ChatMessage).filter(ChatMessage.user_id == uid).delete(synchronize_session=False)
    bump("chat_messages", n)

    return counts


def set_user_active(
    db: Session,
    user: User,
    *,
    active: bool,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    if user.is_superuser:
        raise ValueError("No se puede desactivar un superusuario")
    user.is_active = bool(active)
    meta_note = reason or ("reactivated" if active else "deactivated")
    logger.info(
        "admin set_user_active user_id=%s email=%s active=%s reason=%s",
        user.id,
        user.email,
        active,
        meta_note,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {
        "success": True,
        "user_id": user.id,
        "email": user.email,
        "status": "active" if user.is_active else "inactive",
        "reason": meta_note,
    }


def delete_user_account(
    db: Session,
    user: User,
    *,
    reason: str,
    actor_email: Optional[str] = None,
) -> Dict[str, Any]:
    """Elimina usuario y empresas exclusivas. No borra superusuarios."""
    if user.is_superuser:
        raise ValueError("No se puede eliminar un superusuario")

    reason_norm = (reason or "other").strip().lower()
    if reason_norm not in ALLOWED_DEACTIVATION_REASONS:
        raise ValueError(f"Motivo inválido. Use: {sorted(ALLOWED_DEACTIVATION_REASONS)}")

    uid = user.id
    email = user.email
    company_ids = companies_exclusive_to_user(db, uid)

    row_counts = _purge_user_rows(db, user)

    n_uc = db.query(UserCompany).filter(UserCompany.user_id == uid).delete(
        synchronize_session=False
    )
    bump_uc = n_uc
    row_counts["user_companies"] = bump_uc

    for cid in company_ids:
        co = db.query(Company).filter(Company.id == cid).first()
        if co:
            db.delete(co)

    db.delete(user)
    db.commit()

    try:
        from services.activity_logger import ActivityLogger

        ActivityLogger.log_activity(
            agent_name="ZEUS",
            action_type="admin_account_deleted",
            action_description=f"Cuenta eliminada por admin ({reason_norm})",
            details={
                "deleted_user_id": uid,
                "deleted_email": email,
                "company_ids": company_ids,
                "actor": actor_email,
                "reason": reason_norm,
                "rows": row_counts,
            },
            user_email=actor_email,
            status="completed",
            priority="high",
            visible_to_client=False,
        )
    except Exception as e:
        logger.warning("No se pudo registrar actividad de borrado: %s", e)

    logger.info(
        "admin delete_user_account ok user_id=%s email=%s companies=%s reason=%s",
        uid,
        email,
        company_ids,
        reason_norm,
    )
    return {
        "success": True,
        "deleted_user_id": uid,
        "deleted_email": email,
        "companies_deleted": company_ids,
        "reason": reason_norm,
        "rows_deleted": row_counts,
    }


def get_user_admin_detail(db: Session, user_id: int) -> Optional[Dict[str, Any]]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    links = (
        db.query(UserCompany, Company)
        .join(Company, Company.id == UserCompany.company_id)
        .filter(UserCompany.user_id == user_id)
        .all()
    )
    companies = [
        {
            "id": co.id,
            "name": co.company_name,
            "slug": co.slug,
            "status": co.status,
            "company_type": co.company_type,
        }
        for _, co in links
    ]
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "company_name": user.company_name,
        "phone": user.phone,
        "plan": user.plan,
        "employees": user.employees,
        "status": "active" if user.is_active else "inactive",
        "is_superuser": user.is_superuser,
        "role": getattr(user, "role", "owner"),
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "companies": companies,
        "can_delete": not user.is_superuser,
    }
