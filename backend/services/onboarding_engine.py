"""
ZEUS_ONBOARDING_ENGINE_WITH_VALIDATION_001
Registro + empresa + TPV según business_type; cuestionario post-registro; validación explícita.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.company import Company, UserCompany
from app.models.erp import TPVProduct
from app.models.tpv_table import TPVTable
from app.models.user import User

logger = logging.getLogger(__name__)

ROCE_ID = "ZEUS_ONBOARDING_ENGINE_WITH_VALIDATION_001"

BUSINESS_TYPE_TO_TPV_PROFILE = {
    "restaurant": "restaurante",
    "retail": "tienda_minorista",
    "services": "otros",
}

BUSINESS_TYPE_TO_SECTOR = {
    "restaurant": "restaurante",
    "retail": "tienda retail",
    "services": "servicios profesionales",
}

BUSINESS_TYPE_TO_CONTROL_HORARIO = {
    "restaurant": "restaurante",
    "retail": "tienda",
    "services": "oficina",
}


def _slugify(value: str) -> str:
    s = (value or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "empresa"


def _unique_company_slug(db: Session, base: str, user_id: int) -> str:
    tail = f"{_slugify(base)}-{user_id}"[:100]
    slug = tail
    n = 2
    while db.query(Company.id).filter(Company.slug == slug).first():
        suf = f"-{n}"
        slug = (tail[: 100 - len(suf)] + suf) if len(tail) + len(suf) > 100 else tail + suf
        n += 1
        if n > 50:
            slug = f"u{user_id}-{n}"[:100]
            break
    return slug


def _seed_tpv_products(
    db: Session,
    user: User,
    company_id: int,
    business_type: str,
) -> int:
    if db.query(TPVProduct).filter(TPVProduct.user_id == user.id).count() > 0:
        return 0
    base = int(datetime.utcnow().timestamp() * 1000)
    templates: List[tuple] = []
    if business_type == "restaurant":
        templates = [
            ("Café", 1.5, 10.0, "Bebidas", "coffee"),
            ("Cerveza", 2.5, 21.0, "Bebidas", "food"),
            ("Tostada", 2.0, 10.0, "Tapas", "food"),
            ("Refresco", 2.2, 21.0, "Bebidas", "food"),
        ]
    elif business_type == "retail":
        templates = [
            ("Artículo ejemplo", 9.99, 21.0, "General", "default"),
            ("Oferta del día", 4.5, 21.0, "Promociones", "default"),
        ]
    else:
        templates = [
            ("Servicio (hora)", 45.0, 21.0, "Servicios", "default"),
        ]
    created = 0
    for i, (name, price, iva, category, icon) in enumerate(templates):
        price_with_iva = round(float(price) * (1 + float(iva) / 100.0), 2)
        db.add(
            TPVProduct(
                user_id=user.id,
                company_id=company_id,
                product_id=f"PROD_ONB_{base}_{i}",
                name=name,
                category=category,
                price=float(price),
                price_with_iva=float(price_with_iva),
                iva_rate=float(iva),
                stock=None,
                image=None,
                icon=icon,
                metadata_={"auto_created": True, "roce_id": ROCE_ID, "business_type": business_type},
            )
        )
        created += 1
    return created


def _seed_tpv_tables(db: Session, company_id: int, business_type: str, count: int = 4) -> int:
    if business_type != "restaurant":
        return 0
    added = 0
    for n in range(1, count + 1):
        if db.query(TPVTable).filter(TPVTable.company_id == company_id, TPVTable.number == n).first():
            continue
        db.add(
            TPVTable(
                company_id=company_id,
                number=n,
                name=f"Mesa {n}",
                status="free",
                order_total=Decimal("0"),
            )
        )
        added += 1
    return added


def _create_owner_employee_and_default_schedules(
    db: Session,
    company: Company,
    user: User,
) -> Dict[str, Any]:
    """Empleado titular en company_employees + turnos L–V en employee_schedules si la tabla existe."""
    from sqlalchemy import inspect

    from app.models.company_employee import CompanyEmployee
    from app.models.time_tracking import EmployeeSchedule

    out: Dict[str, Any] = {
        "company_employee_id": None,
        "employee_code": None,
        "schedules_created": 0,
    }
    code = f"U{user.id}-OWNER"
    emp = (
        db.query(CompanyEmployee)
        .filter(CompanyEmployee.company_id == company.id, CompanyEmployee.employee_code == code)
        .first()
    )
    if not emp:
        emp = CompanyEmployee(
            company_id=company.id,
            user_id=user.id,
            full_name=(user.full_name or user.email or "Titular")[:255],
            role_title="owner",
            employee_code=code,
            phone=getattr(user, "phone", None),
            is_active=True,
            source="onboarding_owner",
        )
        db.add(emp)
        db.flush()
    out["company_employee_id"] = emp.id
    out["employee_code"] = code

    bind = db.get_bind()
    try:
        insp = inspect(bind)
        if not insp.has_table("employee_schedules"):
            logger.warning(
                "employee_schedules no existe en BD; crea tablas (create_tables) para turnos reales."
            )
            return out
    except Exception as e:
        logger.warning("inspect BD para employee_schedules: %s", e)
        return out

    for dow in range(5):
        ex = (
            db.query(EmployeeSchedule)
            .filter(
                EmployeeSchedule.employee_id == code,
                EmployeeSchedule.user_id == user.id,
                EmployeeSchedule.day_of_week == dow,
            )
            .first()
        )
        if ex:
            continue
        db.add(
            EmployeeSchedule(
                employee_id=code,
                user_id=user.id,
                day_of_week=dow,
                start_time="09:00",
                end_time="17:00",
                shift_type="completo",
                is_active=True,
            )
        )
        out["schedules_created"] += 1
    return out


def _apply_roce_automation_seed(
    db: Session,
    company: Company,
    user: User,
    business_type: str,
) -> Dict[str, Any]:
    """
    Empleado + turnos reales (company_employees, employee_schedules) y metadata de activación.
    """
    real = _create_owner_employee_and_default_schedules(db, company, user)
    meta = company.metadata_ if isinstance(company.metadata_, dict) else {}
    meta["onboarding_seed"] = {
        "owner_company_employee_id": real.get("company_employee_id"),
        "employee_code": real.get("employee_code"),
        "default_schedules_created": real.get("schedules_created", 0),
        "employees_base": [
            {
                "kind": "company_employee",
                "company_employee_id": real.get("company_employee_id"),
                "user_id": user.id,
                "employee_code": real.get("employee_code"),
            },
        ],
        "default_shift_template": {
            "label": "Turno sugerido",
            "hours": "09:00-17:00",
            "days": "Lunes a viernes",
        },
        "dashboard_ready": True,
    }
    meta["zeus_activation"] = {
        "tpv_configured": True,
        "modules_hint": ["tpv", "control_horario", "dashboard"],
        "business_type": business_type,
        "roce_id": ROCE_ID,
    }
    company.metadata_ = meta
    db.add(company)

    raw_ch = getattr(user, "control_horario_config", None) or "{}"
    try:
        ch = json.loads(raw_ch) if isinstance(raw_ch, str) else dict(raw_ch or {})
    except Exception:
        ch = {}
    ch["onboarding_default_shift"] = "09:00-17:00"
    ch["dashboard_accessible"] = True
    user.control_horario_config = json.dumps(ch, ensure_ascii=False)
    db.add(user)
    return real


def apply_registration_onboarding(
    db: Session,
    user: User,
    company_name: str,
    business_type: str,
) -> Dict[str, Any]:
    """
    Tras flush del usuario: crea empresa, vínculo, perfil TPV, productos y mesas (restaurante).
    No hace commit. Devuelve {success, company_id, ...} o {success: False, error}.
    """
    out: Dict[str, Any] = {
        "success": False,
        "roce_id": ROCE_ID,
        "company_id": None,
        "tpv_profile": None,
        "products_created": 0,
        "tables_created": 0,
        "owner_employee_id": None,
        "schedules_seeded": 0,
        "error": None,
    }
    try:
        if business_type not in BUSINESS_TYPE_TO_TPV_PROFILE:
            out["error"] = f"business_type inválido: {business_type}"
            return out

        cn = (company_name or "").strip()
        if len(cn) < 1:
            out["error"] = "company_name es obligatorio"
            return out

        link = (
            db.query(UserCompany)
            .filter(UserCompany.user_id == user.id)
            .order_by(UserCompany.id.asc())
            .first()
        )
        if link:
            company = db.query(Company).filter(Company.id == link.company_id).first()
            if not company:
                out["error"] = "Inconsistencia: user_companies sin empresa"
                return out
            company.company_name = cn[:255]
            company.sector = BUSINESS_TYPE_TO_SECTOR.get(business_type)
            meta = company.metadata_ if isinstance(company.metadata_, dict) else {}
            meta.setdefault("source", "registration_onboarding")
            meta["business_type"] = business_type
            meta["roce_id"] = ROCE_ID
            company.metadata_ = meta
            db.add(company)
        else:
            slug = _unique_company_slug(db, cn, user.id)
            company = Company(
                company_name=cn[:255],
                slug=slug,
                pilot_company=False,
                status="active",
                sector=BUSINESS_TYPE_TO_SECTOR.get(business_type),
                country="ES",
                currency="EUR",
                metadata_={
                    "billing_enabled": False,
                    "onboarding_completed": False,
                    "source": "registration_onboarding",
                    "business_type": business_type,
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

        db.flush()
        cid = company.id
        seed_real = _apply_roce_automation_seed(db, company, user, business_type)
        out["owner_employee_id"] = seed_real.get("company_employee_id")
        out["schedules_seeded"] = seed_real.get("schedules_created", 0)
        profile = BUSINESS_TYPE_TO_TPV_PROFILE[business_type]
        user.company_name = cn[:255]
        user.tpv_business_profile = profile
        user.control_horario_business_profile = BUSINESS_TYPE_TO_CONTROL_HORARIO.get(business_type, "oficina")

        try:
            from services.tpv_service import BusinessProfile, create_tpv_service

            svc = create_tpv_service()
            prof = BusinessProfile(profile)
            cfg = dict(svc.get_business_config(prof))
            cfg.setdefault("auto_onboarding", True)
            cfg.setdefault("roce_id", ROCE_ID)
            user.tpv_config = json.dumps(cfg, ensure_ascii=False)
        except Exception as e:
            logger.warning("TPV config automática omitida: %s", e)

        db.add(user)
        out["products_created"] = _seed_tpv_products(db, user, cid, business_type)
        out["tables_created"] = _seed_tpv_tables(db, cid, business_type)
        out["company_id"] = cid
        out["tpv_profile"] = profile
        out["success"] = True
        return out
    except Exception as e:
        logger.exception("apply_registration_onboarding: %s", e)
        out["error"] = str(e)
        return out


def apply_questionnaire_answers(db: Session, user: User, body: Any) -> Dict[str, Any]:
    """Persiste respuestas del cuestionario en metadata de empresa y ajusta TPV si aplica."""
    link = (
        db.query(UserCompany)
        .filter(UserCompany.user_id == user.id)
        .order_by(UserCompany.id.asc())
        .first()
    )
    if not link:
        return {"success": False, "error": "No hay empresa vinculada; completa el registro correctamente."}

    company = db.query(Company).filter(Company.id == link.company_id).first()
    if not company:
        return {"success": False, "error": "Empresa no encontrada."}

    meta = company.metadata_ if isinstance(company.metadata_, dict) else {}
    meta["onboarding_questionnaire"] = {
        "employees_count": body.employees_count,
        "uses_tpv": body.uses_tpv,
        "business_hours": body.business_hours,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    meta["onboarding_questionnaire_completed"] = True
    company.metadata_ = meta
    db.add(company)

    user.employees = body.employees_count

    raw = getattr(user, "tpv_config", None) or "{}"
    try:
        cfg = json.loads(raw) if isinstance(raw, str) else dict(raw or {})
    except Exception:
        cfg = {}
    cfg["tables_enabled"] = bool(body.uses_tpv)
    cfg["products_enabled"] = bool(body.uses_tpv)
    user.tpv_config = json.dumps(cfg, ensure_ascii=False)
    db.add(user)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("apply_questionnaire_answers commit: %s", e)
        return {"success": False, "error": "No se pudo guardar el cuestionario."}

    return {"success": True, "company_id": company.id}


def validate_onboarding_state(db: Session, user_id: int) -> Dict[str, Any]:
    """Comprobaciones explícitas post-registro (tests y diagnóstico)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"ok": False, "checks": {"user_created": False}, "error": "Usuario no existe"}

    link = (
        db.query(UserCompany)
        .filter(UserCompany.user_id == user_id)
        .order_by(UserCompany.id.asc())
        .first()
    )
    co = db.query(Company).filter(Company.id == link.company_id).first() if link else None
    company_ok = bool(co)
    seed = (co.metadata_ or {}).get("onboarding_seed") if co and isinstance(co.metadata_, dict) else {}
    products_n = db.query(TPVProduct).filter(TPVProduct.user_id == user_id).count()
    from app.models.company_employee import CompanyEmployee

    ce_count = (
        db.query(CompanyEmployee).filter(CompanyEmployee.company_id == co.id).count()
        if co
        else 0
    )
    checks = {
        "user_created": True,
        "company_linked": bool(link),
        "company_exists": company_ok,
        "tpv_products": products_n,
        "has_tpv_profile": bool(getattr(user, "tpv_business_profile", None)),
        "dashboard_seed_ready": bool(seed.get("dashboard_ready")),
        "employees_seed_defined": bool(seed.get("employees_base")),
        "company_employees_count": ce_count,
    }
    ok = checks["company_linked"] and checks["company_exists"] and checks["has_tpv_profile"]
    return {"ok": ok, "checks": checks, "error": None if ok else "Validación onboarding incompleta"}


async def send_welcome_notifications(
    *,
    user: User,
    company_name: str,
) -> Dict[str, Any]:
    """Email (si hay proveedor) y WhatsApp (si Twilio). No lanzan excepción hacia el caller."""
    results: Dict[str, Any] = {"email": None, "whatsapp": None}
    try:
        from services.email_service import email_service

        html = f"""<html><body style="font-family: Arial, sans-serif;">
        <h2>ZEUS-IA activado</h2>
        <p>Hola {(user.full_name or user.email or '').strip()},</p>
        <p>Tu espacio para <strong>{company_name}</strong> está listo. Ya puedes entrar al panel.</p>
        </body></html>"""
        results["email"] = await email_service.send_email(
            to_email=user.email,
            subject="Tu cuenta ZEUS-IA está activa",
            content=html,
            content_type="text/html",
        )
    except Exception as e:
        logger.warning("Bienvenida email: %s", e)
        results["email"] = {"success": False, "error": str(e)}

    try:
        from services.whatsapp_service import whatsapp_service

        phone = (getattr(user, "phone", None) or "").strip()
        digits = re.sub(r"\D", "", phone)
        if len(digits) >= 9 and whatsapp_service.is_configured():
            if len(digits) == 9:
                digits = "34" + digits
            to = f"+{digits}" if not phone.startswith("+") else phone
            msg = f"¡Hola! Tu cuenta ZEUS-IA para {company_name} ya está activa. Entra con tu correo registrado."
            results["whatsapp"] = await whatsapp_service.send_message(to, msg)
        else:
            results["whatsapp"] = {"success": False, "skipped": True}
    except Exception as e:
        logger.warning("Bienvenida WhatsApp: %s", e)
        results["whatsapp"] = {"success": False, "error": str(e)}

    return results


def schedule_post_register_bootstrap(
    user_id: int,
    company_name: str,
    business_type: str,
) -> None:
    """
    Ejecuta run_global_autonomous_bootstrap en un hilo daemon (no bloquea la respuesta HTTP).
    skip_self_test=True evita run_chat en el hilo (latencias / API keys).
    """

    sector = BUSINESS_TYPE_TO_SECTOR.get(business_type, "servicios profesionales")

    def run() -> None:
        from app.db.session import SessionLocal
        from services.global_company_bootstrap import run_global_autonomous_bootstrap

        db = SessionLocal()
        try:
            u = db.query(User).filter(User.id == user_id).first()
            if not u:
                logger.warning("post_register_bootstrap: usuario %s no encontrado", user_id)
                return
            out = run_global_autonomous_bootstrap(
                db,
                user=u,
                company_name=company_name,
                sector=sector,
                onboarding_completed=True,
                billing_enabled=False,
                source_event="auth.register.background_bootstrap",
                skip_self_test=True,
            )
            if out.get("error"):
                logger.warning("post_register_bootstrap: %s", out["error"])
        except Exception as e:
            logger.exception("post_register_bootstrap: %s", e)
        finally:
            db.close()

    threading.Thread(target=run, daemon=True, name="zeus-post-register-bootstrap").start()


def ensure_company_owner_employee_and_shifts(
    db: Session, company_id: int, *, commit: bool = True
) -> Dict[str, Any]:
    """
    Para empresas ya existentes (ej. piloto Circo Kanroka): crea titular en company_employees
    y turnos L–V si faltan. Idempotente.
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        return {"success": False, "error": "Empresa no existe"}
    link = (
        db.query(UserCompany)
        .filter(UserCompany.company_id == company_id)
        .order_by(UserCompany.id.asc())
        .first()
    )
    if not link:
        return {"success": False, "error": "Sin usuario vinculado a la empresa"}
    user = db.query(User).filter(User.id == link.user_id).first()
    if not user:
        return {"success": False, "error": "Usuario no encontrado"}
    try:
        info = _create_owner_employee_and_default_schedules(db, company, user)
        if commit:
            db.commit()
        else:
            db.flush()
        return {"success": True, "company_id": company_id, **info}
    except Exception as e:
        db.rollback()
        logger.exception("ensure_company_owner_employee_and_shifts: %s", e)
        return {"success": False, "error": str(e)}


def remediate_existing_company(
    db: Session,
    company_id: int,
    *,
    business_type: str = "restaurant",
    set_pilot_flag: bool = False,
    seed_fiscal: bool = True,
    commit: bool = True,
) -> Dict[str, Any]:
    """
    Repara empresas creadas antes del onboarding completo (ej. El Circo Can Roca):
    sector/metadata, perfil TPV usuario, empleado titular, productos, mesas, fiscal, metadata seed.
    Idempotente en mayor medida.
    """
    from decimal import Decimal as Dec

    from app.models.erp import FiscalProfile, TaxRate

    out: Dict[str, Any] = {"company_id": company_id, "actions": []}
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        return {"success": False, "error": "Empresa no existe"}
    link = (
        db.query(UserCompany)
        .filter(UserCompany.company_id == company_id)
        .order_by(UserCompany.id.asc())
        .first()
    )
    if not link:
        return {"success": False, "error": "Sin usuario vinculado (user_companies)"}
    user = db.query(User).filter(User.id == link.user_id).first()
    if not user:
        return {"success": False, "error": "Usuario no encontrado"}

    if business_type not in BUSINESS_TYPE_TO_TPV_PROFILE:
        business_type = "restaurant"

    try:
        if not company.sector:
            company.sector = BUSINESS_TYPE_TO_SECTOR.get(business_type)
            out["actions"].append("set_sector")

        meta = company.metadata_ if isinstance(company.metadata_, dict) else {}
        meta.setdefault("business_type", business_type)
        meta["remediated_at"] = datetime.now(timezone.utc).isoformat()
        meta["remediation_source"] = ROCE_ID
        company.metadata_ = meta

        if set_pilot_flag:
            company.pilot_company = True
            out["actions"].append("set_pilot_company")

        db.add(company)

        profile = BUSINESS_TYPE_TO_TPV_PROFILE[business_type]
        if company.company_name:
            user.company_name = company.company_name[:255]
        user.tpv_business_profile = profile
        user.control_horario_business_profile = BUSINESS_TYPE_TO_CONTROL_HORARIO.get(business_type, "oficina")
        try:
            from services.tpv_service import BusinessProfile, create_tpv_service

            svc = create_tpv_service()
            prof = BusinessProfile(profile)
            cfg = dict(svc.get_business_config(prof))
            cfg.setdefault("auto_remediated", True)
            user.tpv_config = json.dumps(cfg, ensure_ascii=False)
        except Exception as e:
            logger.warning("remediate_existing_company tpv_config: %s", e)
        db.add(user)

        own = _create_owner_employee_and_default_schedules(db, company, user)
        out["actions"].append(f"owner_employee:{own.get('company_employee_id')}")

        try:
            pc_co = db.query(TPVProduct).filter(TPVProduct.company_id == company_id).count()
        except Exception:
            pc_co = 0
        pc_any = db.query(TPVProduct).filter(TPVProduct.user_id == user.id).count()
        try:
            orphan = (
                db.query(TPVProduct)
                .filter(
                    TPVProduct.user_id == user.id,
                    TPVProduct.company_id.is_(None),
                )
                .count()
            )
        except Exception:
            orphan = 0
        if orphan > 0:
            for row in (
                db.query(TPVProduct)
                .filter(
                    TPVProduct.user_id == user.id,
                    TPVProduct.company_id.is_(None),
                )
                .all()
            ):
                row.company_id = company_id
                db.add(row)
            out["actions"].append(f"backfill_company_id_on_products:{orphan}")
        elif pc_any == 0:
            n = _seed_tpv_products(db, user, company_id, business_type)
            out["actions"].append(f"seed_products:{n}")
        else:
            out["actions"].append(f"products_ok company_rows={pc_co}")

        tn = db.query(TPVTable).filter(TPVTable.company_id == company_id).count()
        if tn == 0 and business_type == "restaurant":
            n = _seed_tpv_tables(db, company_id, business_type, count=4)
            out["actions"].append(f"seed_tables:{n}")
        elif tn == 0:
            out["actions"].append("no_tables_non_restaurant")
        else:
            out["actions"].append("tables_unchanged")

        if seed_fiscal:
            fp = db.query(FiscalProfile).filter(FiscalProfile.user_id == user.id).first()
            if not fp:
                db.add(
                    FiscalProfile(
                        user_id=user.id,
                        vat_regime="general",
                        apply_recargo_equivalencia=False,
                        recargo_rate=None,
                    )
                )
                out["actions"].append("fiscal_profile_created")
            tr_n = db.query(TaxRate).filter(TaxRate.user_id == user.id).count()
            if tr_n == 0:
                db.add(
                    TaxRate(
                        user_id=user.id,
                        name="IVA 21%",
                        rate=Dec("0.2100"),
                        applies_to="onsite",
                    )
                )
                db.add(
                    TaxRate(
                        user_id=user.id,
                        name="IVA 10%",
                        rate=Dec("0.1000"),
                        applies_to="onsite",
                    )
                )
                out["actions"].append("tax_rates_seed")

        seed_info = _apply_roce_automation_seed(db, company, user, business_type)
        out["owner_seed"] = seed_info

        if commit:
            db.commit()
        else:
            db.flush()

        out["success"] = True
        return out
    except Exception as e:
        db.rollback()
        logger.exception("remediate_existing_company: %s", e)
        return {"success": False, "error": str(e), "company_id": company_id}
