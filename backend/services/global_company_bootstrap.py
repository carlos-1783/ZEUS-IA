"""
ZEUS_GLOBAL_AUTONOMOUS_COMPANY_BOOTSTRAP_001
Bootstrap autónomo para cualquier empresa nueva tras onboarding/pago.
Reglas clave:
- No sobrescribir datos existentes.
- Registrar todas las acciones en AgentActivity.
- Activar modo autónomo solo si onboarding_completed=True.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.company import Company, UserCompany
from app.models.erp import TPVProduct
from app.models.user import User
from services.activity_logger import ActivityLogger
from services.unified_agent_runtime import run_chat


ROCE_ID = "ZEUS_GLOBAL_AUTONOMOUS_COMPANY_BOOTSTRAP_001"
logger = logging.getLogger(__name__)


def _slugify(value: str) -> str:
    s = (value or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "empresa"


def _infer_business_type(sector: Optional[str]) -> str:
    text = (sector or "").lower()
    hospitality_markers = ("bar", "restaurant", "restaurante", "cafeteria", "cafetería")
    if any(m in text for m in hospitality_markers):
        return "hospitality"
    return "generic"


def _ensure_company(db: Session, user: User, company_name: str, sector: Optional[str], billing_enabled: bool) -> Company:
    # Reutilizar relación existente si ya tiene una company vinculada
    existing_link = (
        db.query(UserCompany)
        .filter(UserCompany.user_id == user.id)
        .order_by(UserCompany.id.asc())
        .first()
    )
    if existing_link:
        company = db.query(Company).filter(Company.id == existing_link.company_id).first()
        if company:
            if not company.company_name and company_name:
                company.company_name = company_name
            if not company.sector and sector:
                company.sector = sector
            meta = company.metadata_ or {}
            if not isinstance(meta, dict):
                meta = {}
            if "billing_enabled" not in meta:
                meta["billing_enabled"] = bool(billing_enabled)
            if "onboarding_completed" not in meta:
                meta["onboarding_completed"] = True
            company.metadata_ = meta
            db.add(company)
            return company

    # Crear Company para cliente nuevo
    base_slug = _slugify(company_name or user.company_name or user.email)
    slug = f"{base_slug}-{user.id}"
    company = Company(
        company_name=company_name or user.company_name or user.email,
        slug=slug,
        pilot_company=False,
        status="active",
        sector=sector or None,
        country="ES",
        currency="EUR",
        metadata_={
            "billing_enabled": bool(billing_enabled),
            "onboarding_completed": True,
            "execution_mode": "tpv + ai_agents",
            "source": "auto_bootstrap",
            "roce_id": ROCE_ID,
        },
    )
    db.add(company)
    db.flush()

    db.add(
        UserCompany(
            user_id=user.id,
            company_id=company.id,
            role="company_admin",
        )
    )
    return company


def ensure_user_company_link_for_operations(db: Session, user: User) -> Optional[int]:
    """
    Garantiza que exista al menos una fila en user_companies para usuarios que operan
    como dueño (TPV mesas multi-tenant, etc.). Sin esto, POST /tpv/tables devuelve 400.

    - Idempotente: si ya hay vínculo, devuelve ese company_id.
    - No aplica a empleados estándar (deben ser invitados/vinculados por el dueño).
    - Registro previo a onboarding: crea empresa mínima (sin flujo de pago ROCE).
    """
    link = (
        db.query(UserCompany)
        .filter(UserCompany.user_id == user.id)
        .order_by(UserCompany.id.asc())
        .first()
    )
    if link:
        return link.company_id

    role = (getattr(user, "role", None) or "owner").strip().lower()
    if role == "employee" and not getattr(user, "is_superuser", False):
        return None

    label = (
        (getattr(user, "company_name", None) or "").strip()
        or (getattr(user, "full_name", None) or "").strip()
        or (getattr(user, "email", None) or "").split("@")[0].strip()
        or "Mi negocio"
    )
    tail = _slugify(label or user.email or "negocio")[:72]
    # Slug único y <=100 chars: id de usuario primero por si hay que truncar el tail
    slug = f"u{user.id}-{tail}" if tail else f"u{user.id}"
    if len(slug) > 100:
        slug = slug[:100]
    company = Company(
        company_name=label[:255],
        slug=slug,
        pilot_company=False,
        status="active",
        sector=None,
        country="ES",
        currency="EUR",
        metadata_={
            "billing_enabled": False,
            "onboarding_completed": False,
            "source": "user_default_company",
            "note": "Creada automáticamente para multi-tenant (TPV mesas); completar datos en onboarding si aplica.",
        },
    )
    db.add(company)
    db.flush()
    db.add(
        UserCompany(
            user_id=user.id,
            company_id=company.id,
            role="company_admin",
        )
    )
    db.commit()
    db.refresh(company)
    logger.info(
        "Empresa por defecto para operaciones: user_id=%s email=%s company_id=%s",
        user.id,
        getattr(user, "email", None),
        company.id,
    )
    return company.id


def _ensure_hospitality_products(db: Session, user: User) -> int:
    existing = db.query(TPVProduct).filter(TPVProduct.user_id == user.id).count()
    if existing > 0:
        return 0

    templates = [
        ("Café", 1.5, 10.0, "Bebidas", "coffee"),
        ("Cerveza", 2.5, 21.0, "Bebidas", "food"),
        ("Tostada", 2.0, 10.0, "Tapas", "food"),
        ("Refresco", 2.2, 21.0, "Bebidas", "food"),
    ]
    created = 0
    base = int(datetime.utcnow().timestamp() * 1000)
    for i, (name, price, iva, category, icon) in enumerate(templates):
        price_with_iva = round(float(price) * (1 + float(iva) / 100.0), 2)
        db.add(
            TPVProduct(
                user_id=user.id,
                product_id=f"PROD_AUTO_{base}_{i}",
                name=name,
                category=category,
                price=float(price),
                price_with_iva=float(price_with_iva),
                iva_rate=float(iva),
                stock=None,
                image=None,
                icon=icon,
                metadata_={"auto_created": True, "roce_id": ROCE_ID},
            )
        )
        created += 1
    return created


def _ensure_tpv_config(user: User, business_type: str) -> None:
    if getattr(user, "tpv_business_profile", None):
        return
    user.tpv_business_profile = "bar" if business_type == "hospitality" else "otros"

    config = {}
    raw = getattr(user, "tpv_config", None)
    if raw:
        try:
            config = json.loads(raw) if isinstance(raw, str) else dict(raw)
        except Exception:
            config = {}

    # No sobrescribir claves existentes
    defaults = {
        "vat_mode": "per_product",
        "allow_multiple_vat": True,
        "default_vat": 0.10,
        "currency": "EUR",
        "compact_ui": True,
        "auto_bootstrap": True,
        "roce_id": ROCE_ID,
    }
    for k, v in defaults.items():
        config.setdefault(k, v)
    user.tpv_config = json.dumps(config, ensure_ascii=False)


def _activate_core_workflows(user: User, business_type: str) -> None:
    # Se crean actividades ejecutables por handlers existentes.
    ActivityLogger.log_activity(
        agent_name="ZEUS",
        action_type="coordination",
        action_description="Auto-bootstrap: activar workflows core",
        details={
            "workflow_trigger": "company_created_or_onboarding_completed",
            "business_type": business_type,
            "roce_id": ROCE_ID,
            "workflows": ["incoming_message", "new_order", "error_detected", "any_action"],
        },
        user_email=user.email,
        status="in_progress",
        priority="critical",
    )
    ActivityLogger.log_activity(
        agent_name="THALOS",
        action_type="task_assigned",
        action_description="Auto-bootstrap: self_healing_or_notify configurado",
        details={"roce_id": ROCE_ID, "notify_only_critical": True},
        user_email=user.email,
        status="in_progress",
        priority="high",
    )


def run_global_autonomous_bootstrap(
    db: Session,
    *,
    user: User,
    company_name: Optional[str],
    sector: Optional[str],
    onboarding_completed: bool,
    billing_enabled: bool,
    source_event: str,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "roce_id": ROCE_ID,
        "source_event": source_event,
        "user_id": user.id,
        "user_email": user.email,
        "company_id": None,
        "business_type": None,
        "products_created": 0,
        "autonomous_mode_enabled": False,
        "self_test_ok": False,
        "error": None,
    }

    try:
        if not onboarding_completed:
            ActivityLogger.log_activity(
                agent_name="ZEUS",
                action_type="bootstrap_skipped",
                action_description="Auto-bootstrap omitido: onboarding no completado",
                details={"roce_id": ROCE_ID, "source_event": source_event},
                user_email=user.email,
                status="completed",
                priority="high",
            )
            return result

        business_type = _infer_business_type(sector)
        result["business_type"] = business_type

        company = _ensure_company(
            db,
            user=user,
            company_name=(company_name or user.company_name or "").strip(),
            sector=sector,
            billing_enabled=billing_enabled,
        )
        result["company_id"] = company.id

        _ensure_tpv_config(user, business_type)
        db.add(user)

        if business_type == "hospitality":
            result["products_created"] = _ensure_hospitality_products(db, user)

        # Activar modo autónomo en metadata de company
        meta = company.metadata_ or {}
        if not isinstance(meta, dict):
            meta = {}
        meta["onboarding_completed"] = True
        meta["execution_mode"] = "full_autonomous"
        meta["self_correction"] = True
        meta["notify_only_critical"] = True
        meta["roce_id"] = ROCE_ID
        # Regla: no activar facturación si billing_enabled=false
        meta["billing_enabled"] = bool(meta.get("billing_enabled", billing_enabled))
        company.metadata_ = meta
        result["autonomous_mode_enabled"] = True

        db.add(company)
        _activate_core_workflows(user, business_type)
        db.commit()

        # Self test de respuesta automática
        chat = run_chat(
            agent_name="ZEUS CORE",
            thread_id="auto_bootstrap_selftest",
            message="Hola",
            company_id=user.email,
            context={"source": "auto_bootstrap", "company_id": user.email},
        )
        result["self_test_ok"] = bool(chat.get("success"))

        ActivityLogger.log_activity(
            agent_name="ZEUS",
            action_type="global_company_bootstrap_completed",
            action_description="Bootstrap autónomo completado para nueva empresa",
            details={
                "roce_id": ROCE_ID,
                "company_id": company.id,
                "business_type": business_type,
                "products_created": result["products_created"],
                "self_test_ok": result["self_test_ok"],
            },
            user_email=user.email,
            status="completed",
            priority="critical",
        )
        return result

    except Exception as e:
        db.rollback()
        result["error"] = str(e)
        ActivityLogger.log_activity(
            agent_name="ZEUS",
            action_type="global_company_bootstrap_error",
            action_description=f"Error bootstrap autónomo: {e}",
            details={"roce_id": ROCE_ID, "error": str(e), "source_event": source_event},
            user_email=user.email,
            status="failed",
            priority="critical",
        )
        return result
