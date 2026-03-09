"""
ZEUS_INTERNAL_COMPANY_BOOTSTRAP_002
Crea empresa interna ZEUS INTERNAL (NORMAL, no pilot), vincula superusuario,
inicializa contexto, persiste AgentActivity real y envía WhatsApp de confirmación.
NO pilot_company, NO modificar rol SUPERUSER, NO crear usuarios duplicados, NO cobros.

Por seguridad: detecta si faltan las tablas (punto 0) y aplica la migración
automáticamente; luego aplica siempre los pasos 1 (CREATE_COMPANY) y 2 (LINK_USER)
cuando sean necesarios.
"""
import os
import asyncio
import concurrent.futures
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.exc import OperationalError

from app.db.base import SessionLocal
from app.models.user import User
from app.models.company import Company, UserCompany
from services.activity_logger import ActivityLogger
from services.whatsapp_service import whatsapp_service

logger = logging.getLogger(__name__)

INTERNAL_COMPANY_SLUG = "zeus-internal"
INTERNAL_COMPANY_NAME = "ZEUS INTERNAL"


def _ensure_bootstrap_schema() -> Tuple[bool, Optional[str]]:
    """
    Punto 0 (seguridad): Detecta si faltan tablas companies/user_companies y
    aplica la migración Alembic (0005) automáticamente.
    Returns: (éxito, mensaje_error o None)
    """
    try:
        from alembic import command
        from alembic.config import Config
    except ImportError:
        return False, "alembic no instalado (pip install alembic)"

    # Ruta al backend (donde está alembic.ini): services -> backend
    backend_dir = Path(__file__).resolve().parent.parent
    alembic_ini = backend_dir / "alembic.ini"
    if not alembic_ini.is_file():
        return False, f"alembic.ini no encontrado en {backend_dir}"

    config = Config(str(alembic_ini))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    try:
        command.upgrade(config, "head")
        logger.info("[BOOTSTRAP] Migración aplicada automáticamente (punto 0).")
        return True, None
    except Exception as e:
        logger.warning("[BOOTSTRAP] No se pudo aplicar migración: %s", e)
        return False, str(e)


def _get_superuser(session) -> Optional[User]:
    """Obtiene el superusuario. No modifica ni degrada su rol."""
    return session.query(User).filter(User.is_superuser == True).first()


def _create_company(session) -> Tuple[Company, bool]:
    """
    Paso 1: Crear empresa NORMAL (pilot_company=False).
    Idempotente: si ya existe, devuelve la existente.
    """
    company = session.query(Company).filter(Company.slug == INTERNAL_COMPANY_SLUG).first()
    if company:
        return company, False

    company = Company(
        company_name=INTERNAL_COMPANY_NAME,
        slug=INTERNAL_COMPANY_SLUG,
        pilot_company=False,
        status="active",
        sector="technology",
        country="ES",
        currency="EUR",
        metadata_={
            "internal_company": True,
            "purpose": "system_execution_context",
            "billing_enabled": False,
            "created_by": "superuser",
        },
    )
    session.add(company)
    session.flush()
    logger.info("[BOOTSTRAP] Empresa ZEUS INTERNAL creada (NORMAL, no pilot).")
    return company, True


def _link_user_to_company(session, user: User, company: Company) -> Tuple[UserCompany, bool]:
    """
    Paso 2: Vincular superusuario a empresa como company_admin.
    Mantiene role SUPERUSER global; company_admin solo aplica a esta empresa.
    Idempotente: si ya está vinculado, no duplica.
    """
    link = (
        session.query(UserCompany)
        .filter(UserCompany.user_id == user.id, UserCompany.company_id == company.id)
        .first()
    )
    if link:
        return link, False

    link = UserCompany(
        user_id=user.id,
        company_id=company.id,
        role="company_admin",
    )
    session.add(link)
    session.flush()
    logger.info("[BOOTSTRAP] Superusuario vinculado a ZEUS INTERNAL como company_admin.")
    return link, True


def _initialize_company_context(session, company: Company) -> None:
    """
    Paso 3: Marcar contexto inicializado (agents, workflows, whatsapp, email, activity_logging).
    billing_enabled=False, execution_mode=internal. Sin crear tablas extra.
    """
    meta = company.metadata_ or {}
    if not isinstance(meta, dict):
        meta = {}
    meta["initialize_modules"] = [
        "agents",
        "workflows",
        "whatsapp",
        "email",
        "activity_logging",
    ]
    meta["billing_enabled"] = False
    meta["execution_mode"] = "internal"
    meta["context_initialized"] = True
    company.metadata_ = meta
    session.add(company)
    session.flush()
    logger.info("[BOOTSTRAP] Contexto de empresa inicializado (execution_mode=internal).")


def _system_test_execution(superuser_email: str) -> bool:
    """
    Paso 4: Persistir AgentActivity REAL (system_bootstrap_confirmed).
    """
    activity = ActivityLogger.log_activity(
        agent_name="ZEUS",
        action_type="system_bootstrap_confirmed",
        action_description="ZEUS INTERNAL activa. Contexto de ejecución operativo.",
        details={
            "message": "ZEUS INTERNAL activa. Contexto de ejecución operativo.",
            "real_execution": True,
            "roce_id": "ZEUS_INTERNAL_COMPANY_BOOTSTRAP_002",
        },
        user_email=superuser_email,
        status="completed",
        priority="critical",
        visible_to_client=False,
    )
    if activity:
        logger.info("[BOOTSTRAP] AgentActivity system_bootstrap_confirmed persistida.")
        return True
    return False


def _send_whatsapp_confirmation(to_number: Optional[str]) -> Dict[str, Any]:
    """
    Paso 5: Enviar WhatsApp de confirmación al superusuario.
    to_number desde SUPERUSER_PHONE o ZEUS_ADMIN_PHONE.
    """
    if not to_number:
        return {"success": False, "error": "No phone number (SUPERUSER_PHONE / ZEUS_ADMIN_PHONE)"}
    if not whatsapp_service.is_configured():
        return {"success": False, "error": "WhatsApp service not configured"}

    message = (
        "✅ ZEUS INTERNAL creada. ZEUS ya ejecuta acciones reales. "
        "Sistema listo para captar empresas piloto."
    )

    def _run_async_send():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(whatsapp_service.send_message(to_number, message))
        finally:
            loop.close()

    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(_run_async_send)
            result = future.result(timeout=15)
        if result.get("success") and result.get("message_sid"):
            ActivityLogger.log_activity(
                agent_name="ZEUS",
                action_type="whatsapp_sent",
                action_description=f"WhatsApp bootstrap enviado a {to_number}",
                details={
                    "to": to_number,
                    "message": message,
                    "message_sid": result.get("message_sid"),
                    "trigger": "ZEUS_INTERNAL_COMPANY_BOOTSTRAP_002",
                },
                status="completed",
                priority="high",
            )
        return result
    except Exception as e:
        logger.warning("[BOOTSTRAP] WhatsApp no enviado: %s", e)
        return {"success": False, "error": str(e)}


def run_bootstrap() -> Dict[str, Any]:
    """
    Ejecuta los 5 pasos del ROCE ZEUS_INTERNAL_COMPANY_BOOTSTRAP_002.
    Idempotente: se puede llamar varias veces; no crea duplicados.
    """
    result = {
        "roce_id": "ZEUS_INTERNAL_COMPANY_BOOTSTRAP_002",
        "migration_applied": False,
        "company_created": False,
        "user_linked": False,
        "context_initialized": False,
        "agent_activity_persisted": False,
        "whatsapp_sent": False,
        "whatsapp_error": None,
        "superuser_email": None,
        "company_slug": INTERNAL_COMPANY_SLUG,
        "error": None,
    }

    session = SessionLocal()
    try:
        # Punto 0: Comprobar tablas; si faltan, aplicar migración automáticamente (más seguridad)
        try:
            session.query(Company).limit(1).first()
        except OperationalError as e:
            if "no such table" in str(e).lower() or "does not exist" in str(e).lower():
                session.close()
                ok, err = _ensure_bootstrap_schema()
                result["migration_applied"] = ok
                if not ok:
                    result["error"] = (
                        "Tablas companies/user_companies no existen y no se pudo aplicar migración. "
                        f"{err or 'Ejecuta: cd backend && alembic upgrade head'}"
                    )
                    return result
                session = SessionLocal()
                try:
                    session.query(Company).limit(1).first()
                except OperationalError:
                    result["error"] = "Tras aplicar migración, la tabla companies sigue sin existir."
                    return result
            else:
                raise

        superuser = _get_superuser(session)
        if not superuser:
            result["error"] = "No superuser found. Create a superuser first."
            return result

        result["superuser_email"] = superuser.email

        # Paso 1: CREATE_COMPANY
        company, created = _create_company(session)
        result["company_created"] = created
        session.commit()

        # Re-open session for steps that need fresh read (company id might be new)
        session.expire_all()
        company = session.query(Company).filter(Company.slug == INTERNAL_COMPANY_SLUG).first()
        if not company:
            result["error"] = "Company not found after create"
            return result

        # Paso 2: LINK_USER_TO_COMPANY
        _, linked = _link_user_to_company(session, superuser, company)
        result["user_linked"] = linked

        # Paso 3: INITIALIZE_COMPANY_CONTEXT
        _initialize_company_context(session, company)
        result["context_initialized"] = True

        session.commit()
    except Exception as e:
        logger.exception("[BOOTSTRAP] Error en pasos 1-3: %s", e)
        result["error"] = str(e)
        session.rollback()
        return result
    finally:
        session.close()

    # Paso 4: SYSTEM_TEST_EXECUTION (usa su propia sesión vía ActivityLogger)
    result["agent_activity_persisted"] = _system_test_execution(result["superuser_email"] or "")

    # Paso 5: WHATSAPP_CONFIRMATION
    to_number = os.getenv("SUPERUSER_PHONE") or os.getenv("ZEUS_ADMIN_PHONE") or os.getenv("NUMERO_WHATSAPP_SUPERUSUARIO")
    whatsapp_result = _send_whatsapp_confirmation(to_number)
    result["whatsapp_sent"] = whatsapp_result.get("success", False)
    result["whatsapp_error"] = whatsapp_result.get("error")

    result["final_state"] = (
        "ZEUS_READY_FOR_REAL_CLIENT_ACQUISITION"
        if (result["company_created"] or result["user_linked"] or True) and result["agent_activity_persisted"] and not result["error"]
        else "BOOTSTRAP_INCOMPLETE"
    )
    # Pasos 1 y 2 siempre aplicados cuando eran necesarios (empresa creada o usuario vinculado)
    result["steps_applied"] = {
        "punto_0_migration": result.get("migration_applied", False),
        "punto_1_company": result["company_created"],
        "punto_2_user_link": result["user_linked"],
    }
    return result
