import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import logging
import json

from fastapi import APIRouter, Depends, HTTPException, status, Request, Form, Body, Header
from fastapi.responses import Response
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer

from app.core.auth import get_current_active_user, resolve_user_scopes
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import inspect

from app.core import security
from app.core.jwt_auth import create_access_token, create_refresh_token as create_jwt_refresh_token, get_current_user
from app.core.auth import authenticate_user, get_user_by_email
from app.core.security import get_password_hash, verify_password
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User, RefreshToken, PasswordResetToken
from app.models.company_employee import CompanyEmployee
from app.models.company import UserCompany
from app.schemas.token import (
    Token,
    TokenRefresh,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    NewPasswordRequest,
    OnboardingQuestionnaireRequest,
    OnboardingProfileRequest,
)
from services.email_service import email_service
from services.activity_logger import ActivityLogger
from app.schemas.user import User as UserSchema, RegisterResponse, OnboardingSuccessResponse

# Configurar logging
logger = logging.getLogger(__name__)

router = APIRouter()

REGISTER_EMAIL_TAKEN = "email_already_registered"
REGISTER_DUPLICATE_DATA = "duplicate_data"


def _register_http_400(detail_es: str, *, code: str = REGISTER_DUPLICATE_DATA) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"message": detail_es, "code": code},
    )


def _integrity_error_to_register_detail(exc: IntegrityError) -> HTTPException:
    raw = str(getattr(exc, "orig", None) or exc).lower()
    if "email" in raw or "users_email" in raw or "ix_users_email" in raw:
        logger.warning("register IntegrityError: email duplicado")
        return _register_http_400(
            "Este correo ya está registrado. Inicia sesión o usa otro email.",
            code=REGISTER_EMAIL_TAKEN,
        )
    if "slug" in raw or "companies_slug" in raw:
        logger.warning("register IntegrityError: slug empresa duplicado")
        return _register_http_400(
            "Ya existe una empresa con un nombre similar. Prueba otro nombre comercial.",
        )
    logger.warning("register IntegrityError: %s", raw[:200])
    return _register_http_400(
        "No se pudo completar el registro por datos duplicados. Revisa el email o el nombre del negocio.",
    )


async def _send_register_welcome_email(user: User) -> Dict[str, Any]:
    """Email de bienvenida tras registro (SendGrid o Resend). No lanza: el registro ya está guardado."""
    display = (user.full_name or user.email or "Usuario").strip()
    html = f"""<html><body style="font-family: Arial, sans-serif; max-width: 560px;">
    <h2 style="color: #1e293b;">Cuenta creada correctamente</h2>
    <p>Hola {display},</p>
    <p>Ya puedes iniciar sesión en <strong>ZEUS-IA</strong> con tu correo y la contraseña que elegiste.</p>
    <p>Si no has sido tú quien se registró, ignora este mensaje.</p>
    <p style="margin-top: 24px; font-size: 12px; color: #64748b;">Este correo lo envía ZEUS-IA.</p>
    </body></html>"""
    return await email_service.send_email(
        to_email=user.email,
        subject="Bienvenido a ZEUS-IA",
        content=html,
        content_type="text/html",
    )


async def create_tokens(db: Session, user: User) -> Dict[str, Any]:
    """
    Create access and refresh tokens for user using the new JWT module
    """
    try:
        # Calculate token expiration
        access_token_expires = timedelta(minutes=float(settings.ACCESS_TOKEN_EXPIRE_MINUTES))
        refresh_token_expires = timedelta(days=float(settings.REFRESH_TOKEN_EXPIRE_DAYS))
        
        # Create access token using the new JWT module (getattr por si el modelo tiene columnas no migradas en BD)
        user_scopes = resolve_user_scopes(user)
        is_active = getattr(user, "is_active", True)
        is_superuser = getattr(user, "is_superuser", False)
        user_role = getattr(user, "role", None) or "owner"

        access_token = create_access_token(
            user_id=str(user.id),
            email=user.email,
            is_active=is_active,
            is_superuser=is_superuser,
            expires_delta=access_token_expires,
            scopes=user_scopes,
            role=str(user_role),
        )
        
        # Create refresh token and store it in the database
        refresh_token = create_jwt_refresh_token()
        
        # Store refresh token in database
        db_refresh_token = RefreshToken(
            token=refresh_token,
            user_id=user.id,
            expires_at=datetime.utcnow() + refresh_token_expires,
            is_active=True
        )
        db.add(db_refresh_token)
        db.commit()
        db.refresh(db_refresh_token)

        jornada: Dict[str, Any] = {}
        try:
            from services.employee_work_session_service import begin_work_session_on_login

            jornada = begin_work_session_on_login(db, user)
        except Exception as e:
            logger.exception("begin_work_session_on_login: %s", e)
            jornada = {"error": str(e)}
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": int(access_token_expires.total_seconds()),
            "user_id": user.id,
            "email": user.email,
            "full_name": getattr(user, "full_name", None),
            "is_active": is_active,
            "is_superuser": is_superuser,
            "scopes": user_scopes,
            "jornada": jornada,
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating tokens for user {user.email}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating authentication tokens: {str(e)}"
        )

# ZEUS_LOCAL_CORS_FIX_001: Preflight OPTIONS sin autenticaci?n para que CORS pase en local
@router.options("/login", include_in_schema=False)
async def login_preflight() -> Response:
    """Responde 200 a OPTIONS para preflight CORS (no ejecuta auth)."""
    return Response(status_code=200)


@router.post(
    "/login",
    response_model=Token,
    operation_id="auth_login_api_v1",
    summary="Login with email and password",
    description="Login with email and password to get an access token and refresh token"
)
async def login(
    username: str = Form(...),
    password: str = Form(...),
    grant_type: str = Form(default="password"),
    db: Session = Depends(get_db)
):
    """
    OAuth2 compatible token login, get an access token and refresh token for future requests.
    Accepts form data with username (email) and password.
    """
    logger.info(f"Intento de login para usuario: {username}")
    
    try:
        # Autenticar al usuario
        user = authenticate_user(db, username, password)
        if not user:
            logger.warning(f"Login fallido para usuario: {username} - Credenciales incorrectas")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Verificar si el usuario est? activo
        if not user.is_active:
            logger.warning(f"Intento de login de usuario inactivo: {username}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user"
            )
        
        logger.info(f"Login exitoso para usuario: {username}")
        
        # Crear tokens de acceso y actualizaci?n
        return await create_tokens(db, user)
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        error_msg = str(e).lower()
        # Incluir errores de esquema (columnas faltantes) típicos en Railway/Postgres
        is_db_error = any(keyword in error_msg for keyword in [
            "connection", "conexi", "timeout", "operationalerror", "programmingerror",
            "database", "base de datos", "connection timeout",
            "column", "does not exist", "undefined column", "relation", "no existe"
        ])
        
        if is_db_error:
            logger.error(f"Error DB durante login para {username}: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database temporarily unavailable or schema outdated. Try again or contact support."
            )
        else:
            logger.error(f"Error in login endpoint for user {username}: {type(e).__name__}: {str(e)}", exc_info=True)
            detail = "Internal server error during login"
            if getattr(settings, "DEBUG", False):
                detail = f"{detail}: {type(e).__name__}: {str(e)}"
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=detail
            )

# Mantener compatibilidad con OAuth2
@router.post(
    "/token", 
    response_model=Token,
    operation_id="auth_token_api_v1",
    summary="OAuth2 Token",
    description="OAuth2 compatible token login, get an access token and refresh token"
)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    OAuth2 compatible token login.
    
    Este endpoint es compatible con el est?ndar OAuth2 y se puede utilizar con clientes
    que esperan el flujo de contrase?a de OAuth2.
    """
    # Autenticar al usuario
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verificar si el usuario est? activo
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    # Usar la misma funci?n create_tokens que en el endpoint /login
    return await create_tokens(db, user)

@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="auth_register_api_v1",
    summary="Register New User",
    description="Registro con titular, teléfono, empresa y tipo de negocio; activa TPV y empresa en una transacción; email si hay proveedor configurado",
)
async def register_user(
    user_data: RegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Registro ZEUS_ONBOARDING_ENGINE: usuario + empresa + perfil TPV en la misma transacción.
    Si falla la creación de empresa, se revierte el usuario (no registro silencioso incompleto).
    """
    from services.onboarding_engine import (
        apply_registration_onboarding,
        send_welcome_notifications,
        validate_onboarding_state,
        schedule_post_register_bootstrap,
    )
    email_norm = str(user_data.email).strip().lower()
    if db.query(User).filter(User.email == email_norm).first():
        logger.warning("register 400: email ya existe (%s)", email_norm)
        raise _register_http_400(
            "Este correo ya está registrado. Inicia sesión o usa otro email.",
            code=REGISTER_EMAIL_TAKEN,
        )

    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        email=email_norm,
        hashed_password=hashed_password,
        full_name=user_data.full_name.strip(),
        phone=user_data.phone,
        company_name=user_data.company_name.strip(),
        is_active=True,
    )
    db.add(db_user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise _integrity_error_to_register_detail(exc) from exc

    outcome = apply_registration_onboarding(
        db,
        db_user,
        user_data.company_name.strip(),
        user_data.business_type,
    )
    if not outcome.get("success"):
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=outcome.get("error") or "No se pudo crear la empresa. Revisa los datos e inténtalo de nuevo.",
        )

    try:
        db.commit()
        db.refresh(db_user)
    except IntegrityError as exc:
        db.rollback()
        raise _integrity_error_to_register_detail(exc) from exc
    except Exception as e:
        db.rollback()
        logger.exception("register commit failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error guardando el registro. Inténtalo de nuevo.",
        )

    user_id_saved = int(db_user.id)
    company_id_raw = outcome.get("company_id")
    company_id_saved = int(company_id_raw) if company_id_raw is not None else None
    company_name_saved = user_data.company_name.strip()
    business_type_saved = user_data.business_type
    email_saved = str(db_user.email)

    # Todo post-commit en segundo plano: la respuesta HTTP solo confirma el alta en BD.
    import asyncio
    import threading

    def _post_register_side_effects() -> None:
        from app.db.session import SessionLocal

        try:
            schedule_post_register_bootstrap(
                user_id_saved,
                company_name_saved,
                business_type_saved,
            )
        except Exception as exc:
            logger.warning("post_register_bootstrap: %s", exc)

        db_bg = SessionLocal()
        try:
            try:
                validation = validate_onboarding_state(db_bg, user_id_saved)
                if not validation.get("ok"):
                    logger.warning(
                        "Validación onboarding post-registro user_id=%s checks=%s",
                        user_id_saved,
                        validation.get("checks"),
                    )
            except Exception as exc:
                logger.warning("validate_onboarding_state post-registro: %s", exc)

            user_bg = db_bg.query(User).filter(User.id == user_id_saved).first()
            if user_bg:
                try:
                    asyncio.run(
                        send_welcome_notifications(
                            user=user_bg,
                            company_name=company_name_saved,
                        )
                    )
                except Exception as exc:
                    logger.warning("Notificaciones bienvenida (bg): %s", exc)

            try:
                from services.event_bus import emit_user_registered

                emit_user_registered(
                    user_id=user_id_saved,
                    user_email=email_saved,
                    company_name=company_name_saved,
                    db=None,
                )
            except Exception:
                logger.exception("emit_user_registered (bg)")
        finally:
            db_bg.close()

    threading.Thread(target=_post_register_side_effects, daemon=True).start()

    logger.info(
        "register ok user_id=%s company_id=%s email=%s",
        user_id_saved,
        company_id_saved,
        email_norm,
    )
    try:
        return RegisterResponse(
            success=True,
            user_id=user_id_saved,
            company_id=company_id_saved,
            email=email_saved,
            message="Cuenta y empresa creadas correctamente",
        )
    except Exception as exc:
        logger.exception("register response build failed (user already saved): %s", exc)
        existing = db.query(User).filter(User.email == email_norm).first()
        if existing:
            return RegisterResponse(
                success=True,
                user_id=int(existing.id),
                company_id=company_id_saved,
                email=str(existing.email),
                message="Cuenta y empresa creadas correctamente",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cuenta creada pero hubo un error al confirmar. Inicia sesión con tu correo.",
        ) from exc


@router.post(
    "/onboarding/questionnaire",
    response_model=OnboardingSuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Cuestionario post-registro",
    description="Guarda empleados, uso TPV y horario; requiere sesión.",
)
async def onboarding_questionnaire(
    body: OnboardingQuestionnaireRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    try:
        from app.models.company import Company, UserCompany

        # Ruta principal (motor onboarding). Si falla por diferencias de esquema/datos, aplicar fallback robusto.
        from services.onboarding_engine import apply_questionnaire_answers

        result = apply_questionnaire_answers(db, current_user, body)
        if result.get("success"):
            return OnboardingSuccessResponse(
                success=True,
                company_id=result.get("company_id"),
                message="Cuestionario guardado correctamente",
            )
        logger.warning("onboarding_questionnaire apply_questionnaire_answers=%s", result)
        # Forzar fallback si el motor devuelve success=False sin lanzar excepción.
        raise RuntimeError(result.get("error") or "apply_questionnaire_answers returned success=False")
    except Exception as e:
        logger.exception("onboarding_questionnaire primary path failed: %s", e)

        # Fallback compatible producción: guardar metadata mínima + tpv_config sin romper por columnas faltantes.
        link = (
            db.query(UserCompany)
            .filter(UserCompany.user_id == current_user.id)
            .order_by(UserCompany.id.asc())
            .first()
        )
        if not link:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Usuario sin empresa vinculada")
        company = db.query(Company).filter(Company.id == link.company_id).first()
        if not company:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no encontrada")

        meta = company.metadata_ if isinstance(company.metadata_, dict) else {}
        meta["onboarding_questionnaire"] = {
            "employees_count": body.employees_count,
            "uses_tpv": body.uses_tpv,
            "business_hours": body.business_hours,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "fallback_mode": True,
        }
        meta["onboarding_questionnaire_completed"] = True
        company.metadata_ = meta
        db.add(company)

        # Intento best-effort de persistir empleados/tpv_config.
        try:
            setattr(current_user, "employees", body.employees_count)
        except Exception:
            logger.warning("onboarding_questionnaire: no se pudo setear user.employees (schema antiguo)")
        try:
            raw = getattr(current_user, "tpv_config", None) or "{}"
            cfg = json.loads(raw) if isinstance(raw, str) else dict(raw or {})
            cfg["tables_enabled"] = bool(body.uses_tpv)
            cfg["products_enabled"] = bool(body.uses_tpv)
            current_user.tpv_config = json.dumps(cfg, ensure_ascii=False)
        except Exception:
            logger.warning("onboarding_questionnaire: no se pudo actualizar tpv_config")
        db.add(current_user)

        try:
            db.commit()
        except Exception as commit_err:
            db.rollback()
            logger.exception("onboarding_questionnaire fallback commit failed: %s", commit_err)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pudo guardar el cuestionario en este entorno. Revisa migraciones de BD.",
            )

        return OnboardingSuccessResponse(
            success=True,
            company_id=company.id,
            message="Cuestionario guardado (modo compatible)",
            fallback_mode=True,
        )
    except HTTPException:
        raise
    except Exception as fatal_err:
        logger.exception("onboarding_questionnaire fatal: %s", fatal_err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo guardar el cuestionario. Revisa configuración de la empresa.",
        )


@router.get(
    "/onboarding/status",
    summary="Estado onboarding",
    description="Validación explícita de empresa, TPV y cuestionario.",
)
def onboarding_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    from app.models.company import Company, UserCompany

    questionnaire_completed = False
    operational_profile_completed = False
    link = (
        db.query(UserCompany)
        .filter(UserCompany.user_id == current_user.id)
        .order_by(UserCompany.id.asc())
        .first()
    )
    co = db.query(Company).filter(Company.id == link.company_id).first() if link else None
    if co and isinstance(co.metadata_, dict):
        questionnaire_completed = bool(co.metadata_.get("onboarding_questionnaire_completed"))
        operational_profile_completed = bool(
            co.metadata_.get("onboarding_operational_profile_completed")
        )

    user_onboarding_backup = False
    try:
        import json as _json

        raw_cfg = getattr(current_user, "tpv_config", None) or "{}"
        cfg = _json.loads(raw_cfg) if isinstance(raw_cfg, str) else dict(raw_cfg or {})
        user_onboarding_backup = bool(cfg.get("onboarding_setup_completed"))
    except Exception:
        user_onboarding_backup = False

    setup_completed = (
        questionnaire_completed or operational_profile_completed or user_onboarding_backup
    )

    try:
        from services.onboarding_engine import validate_onboarding_state

        v = validate_onboarding_state(db, current_user.id)
    except Exception as e:
        logger.exception("onboarding_status validate_onboarding_state failed: %s", e)
        v = {
            "ok": bool(link and co),
            "checks": {
                "user_created": True,
                "company_linked": bool(link),
                "company_exists": bool(co),
                "has_tpv_profile": bool(getattr(current_user, "tpv_business_profile", None)),
            },
            "error": None if (link and co) else "Validación onboarding incompleta",
            "fallback_mode": True,
        }

    return {
        "validation": v,
        "questionnaire_completed": questionnaire_completed,
        "operational_profile_completed": operational_profile_completed,
        "setup_completed": setup_completed,
        "user_onboarding_backup": user_onboarding_backup,
        "email_gestor_fiscal": getattr(current_user, "email_gestor_fiscal", None),
        "autoriza_envio_documentos_a_asesores": bool(
            getattr(current_user, "autoriza_envio_documentos_a_asesores", False)
        ),
        "rafael_email_ready": bool(
            getattr(current_user, "email_gestor_fiscal", None)
            and getattr(current_user, "autoriza_envio_documentos_a_asesores", False)
        ),
    }


def _seed_onboarding_employees(
    db: Session,
    *,
    company_id: int,
    user_id: int,
    employees_rows: list,
) -> tuple[int, int, list[str]]:
    """Importa empleados en savepoints; no hace rollback de la sesión principal."""
    from app.models.company_employee import CompanyEmployee
    from app.models.time_tracking import EmployeeSchedule

    warnings: list[str] = []
    seeded = 0
    schedules_seeded = 0
    if not employees_rows:
        return seeded, schedules_seeded, warnings

    try:
        bind = db.get_bind()
        insp = inspect(bind)
        if not insp.has_table("company_employees"):
            return 0, 0, ["Plantilla de empleados guardada en perfil (tabla RRHH pendiente en BD)."]
        ce_columns = {c["name"] for c in insp.get_columns("company_employees")}
        has_source_col = "source" in ce_columns
        has_schedules = insp.has_table("employee_schedules")
    except Exception as exc:
        return 0, 0, [f"Importación de empleados omitida: {exc}"]

    for idx, row in enumerate(employees_rows, start=1):
        full_name = str(getattr(row, "full_name", "") or "").strip()
        phone = str(getattr(row, "phone", "") or "").strip() or None
        role_title = str(getattr(row, "role_title", "") or "").strip() or "employee"
        if not full_name:
            continue
        employee_code = f"ONB-{idx:03d}"
        try:
            with db.begin_nested():
                ce = (
                    db.query(CompanyEmployee)
                    .filter(
                        CompanyEmployee.company_id == company_id,
                        CompanyEmployee.employee_code == employee_code,
                    )
                    .first()
                )
                if not ce:
                    ce_kwargs = dict(
                        company_id=company_id,
                        user_id=None,
                        full_name=full_name[:255],
                        role_title=role_title[:100],
                        employee_code=employee_code,
                        phone=phone[:32] if phone else None,
                        is_active=True,
                    )
                    if has_source_col:
                        ce_kwargs["source"] = "onboarding_profile"
                    ce = CompanyEmployee(**ce_kwargs)
                else:
                    ce.full_name = full_name[:255]
                    ce.phone = phone[:32] if phone else None
                    ce.role_title = role_title[:100]
                    ce.is_active = True
                    if has_source_col:
                        ce.source = ce.source or "onboarding_profile"
                db.add(ce)
                db.flush()
                seeded += 1

                if has_schedules:
                    for dow in range(5):
                        ex = (
                            db.query(EmployeeSchedule)
                            .filter(
                                EmployeeSchedule.employee_id == employee_code,
                                EmployeeSchedule.day_of_week == dow,
                            )
                            .first()
                        )
                        if ex:
                            continue
                        db.add(
                            EmployeeSchedule(
                                employee_id=employee_code,
                                user_id=user_id,
                                day_of_week=dow,
                                start_time="09:00",
                                end_time="17:00",
                                shift_type="completo",
                                is_active=True,
                            )
                        )
                        schedules_seeded += 1
        except Exception as row_err:
            warnings.append(f"No se importó el empleado {full_name}: {row_err}")
            logger.warning("onboarding_profile employee row skipped: %s", row_err)

    return seeded, schedules_seeded, warnings


@router.post(
    "/onboarding/profile",
    response_model=OnboardingSuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Perfil operativo post-registro",
    description="Guarda canales sociales y datos operativos base en metadata de la empresa.",
)
def onboarding_profile(
    body: OnboardingProfileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    try:
        return _onboarding_profile_impl(body, db, current_user)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("onboarding_profile uncaught: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo guardar la configuración. Reintenta; si persiste, contacta soporte.",
        ) from exc


def _onboarding_profile_impl(
    body: OnboardingProfileRequest,
    db: Session,
    current_user: User,
) -> OnboardingSuccessResponse:
    from app.models.company import Company, UserCompany

    warnings: list[str] = []
    user_id = int(current_user.id)
    user_email = str(current_user.email or "")

    link = (
        db.query(UserCompany)
        .filter(UserCompany.user_id == current_user.id)
        .order_by(UserCompany.id.asc())
        .first()
    )
    if not link:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario sin empresa vinculada. Completa el registro antes de configurar el perfil.",
        )
    company = db.query(Company).filter(Company.id == link.company_id).first()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no encontrada")

    meta = company.metadata_ if isinstance(company.metadata_, dict) else {}
    op = meta.get("operational_profile") if isinstance(meta.get("operational_profile"), dict) else {}

    channels = body.social_channels or []
    channels_norm = []
    for c in channels:
        s = str(c).strip().lower()
        if s and s not in channels_norm:
            channels_norm.append(s)
    op["social_channels"] = channels_norm
    links_raw = body.social_links or {}
    links_norm: Dict[str, str] = {}
    for ch in channels_norm:
        v = str(links_raw.get(ch) or "").strip()
        if not v:
            continue
        if not (v.startswith("http://") or v.startswith("https://")):
            v = f"https://{v}"
        links_norm[ch] = v
    op["social_links"] = links_norm
    op["whatsapp_number"] = (body.whatsapp_number or "").strip() or None
    op["control_horario_policy"] = (body.control_horario_policy or "").strip() or None
    if body.email_gestor_fiscal:
        op["email_gestor_fiscal"] = str(body.email_gestor_fiscal).strip().lower()
    op["updated_at"] = datetime.now(timezone.utc).isoformat()

    q = meta.get("onboarding_questionnaire") if isinstance(meta.get("onboarding_questionnaire"), dict) else {}
    if body.employees_count is not None:
        q["employees_count"] = int(body.employees_count)
        current_user.employees = int(body.employees_count)
    if body.uses_tpv is not None:
        q["uses_tpv"] = bool(body.uses_tpv)
    if body.business_hours is not None:
        q["business_hours"] = str(body.business_hours).strip()
    q["completed_at"] = datetime.now(timezone.utc).isoformat()
    q["saved_via"] = "onboarding_profile"
    meta["onboarding_questionnaire"] = q
    meta["onboarding_questionnaire_completed"] = True
    meta["operational_profile"] = op
    meta["onboarding_operational_profile_completed"] = True

    if body.email_gestor_fiscal:
        current_user.email_gestor_fiscal = str(body.email_gestor_fiscal).strip().lower()
    if body.autoriza_envio_documentos_a_asesores is not None:
        current_user.autoriza_envio_documentos_a_asesores = bool(
            body.autoriza_envio_documentos_a_asesores
        )
    elif body.email_gestor_fiscal and not getattr(
        current_user, "autoriza_envio_documentos_a_asesores", None
    ):
        current_user.autoriza_envio_documentos_a_asesores = True

    import json as _json

    try:
        raw_cfg = getattr(current_user, "tpv_config", None) or "{}"
        cfg = _json.loads(raw_cfg) if isinstance(raw_cfg, str) else dict(raw_cfg or {})
    except Exception:
        cfg = {}
    cfg["onboarding_setup_completed"] = True
    cfg["onboarding_setup_completed_at"] = datetime.now(timezone.utc).isoformat()
    current_user.tpv_config = _json.dumps(cfg, ensure_ascii=False)
    db.add(current_user)

    from app.db.metadata_utils import set_company_metadata

    set_company_metadata(company, meta)
    db.add(company)

    try:
        db.commit()
        db.refresh(company)
        db.refresh(current_user)
    except Exception as commit_err:
        db.rollback()
        logger.exception("onboarding_profile metadata commit failed: %s", commit_err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo guardar la configuración de la empresa.",
        )

    company_id = int(company.id)
    seeded, schedules_seeded, emp_warnings = _seed_onboarding_employees(
        db,
        company_id=company_id,
        user_id=user_id,
        employees_rows=body.employees or [],
    )
    warnings.extend(emp_warnings)

    if seeded:
        try:
            with db.begin_nested():
                co2 = db.query(Company).filter(Company.id == company_id).first()
                if co2:
                    m2 = co2.metadata_ if isinstance(co2.metadata_, dict) else {}
                    q2 = (
                        m2.get("onboarding_questionnaire")
                        if isinstance(m2.get("onboarding_questionnaire"), dict)
                        else {}
                    )
                    q2["employees_seeded"] = seeded
                    q2["employee_schedules_seeded"] = schedules_seeded
                    m2["onboarding_questionnaire"] = q2
                    from app.db.metadata_utils import set_company_metadata

                    set_company_metadata(co2, m2)
                    db.add(co2)
            db.commit()
        except Exception as emp_meta_err:
            warnings.append(f"Empleados guardados; metadata secundaria no actualizada: {emp_meta_err}")
            logger.warning("onboarding_profile employee metadata: %s", emp_meta_err)

    try:
        ActivityLogger.log_activity(
            agent_name="ZEUS",
            action_type="onboarding_profile_completed",
            action_description="Perfil operativo de onboarding completado",
            details={"company_id": company_id, "warnings": warnings},
            user_email=user_email,
            status="completed",
        )
    except Exception:
        logger.debug("ActivityLogger onboarding_profile_completed omitido")

    logger.info(
        "onboarding_profile ok user_id=%s company_id=%s warnings=%s",
        user_id,
        company_id,
        len(warnings),
    )
    return OnboardingSuccessResponse(
        success=True,
        company_id=company_id,
        message="Configuración guardada correctamente",
        fallback_mode=bool(warnings),
        warnings=warnings,
    )


# Tiempo de validez del token de reset (1 hora)
RESET_TOKEN_EXPIRE_MINUTES = 60


@router.post(
    "/reset-password",
    operation_id="auth_reset_password_api_v1",
    summary="Reset Password",
    description="Request a password reset for a user"
)
async def reset_password(
    reset_data: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    """Request password reset: genera token, lo guarda y opcionalmente env?a email. Si no hay email configurado, devuelve reset_link."""
    user = db.query(User).filter(User.email == reset_data.email).first()
    if not user:
        # No revelar si el email existe o no
        return {"msg": "Si tu correo est? registrado, recibir?s un enlace para restablecer la contrase?a."}

    # Invalidar tokens previos para este email
    db.query(PasswordResetToken).filter(PasswordResetToken.email == reset_data.email).delete()

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
    db.add(PasswordResetToken(email=reset_data.email, token=token, expires_at=expires_at))
    db.commit()

    reset_link = f"{settings.FRONTEND_URL}/auth/reset-password/{token}"

    # TODO: Si tienes email configurado (SMTP), enviar correo con reset_link aqu?.
    # if settings.SMTP_HOST: send_reset_email(reset_data.email, reset_link)

    return {
        "msg": "Si tu correo est? registrado, recibir?s un enlace para restablecer la contrase?a.",
        "reset_link": reset_link,  # Para desarrollo / cuando no hay email; en producci?n puede omitirse
    }


@router.post(
    "/new-password",
    operation_id="auth_set_new_password_api_v1",
    summary="Set New Password",
    description="Set a new password using a reset token"
)
async def set_new_password(
    new_password_data: NewPasswordRequest,
    db: Session = Depends(get_db)
):
    """Set new password with reset token. Valida token, actualiza contrase?a y borra el token."""
    now = datetime.now(timezone.utc)
    row = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token == new_password_data.token,
            PasswordResetToken.expires_at > now,
        )
        .first()
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inv?lido o expirado. Solicita de nuevo el restablecimiento de contrase?a.",
        )

    user = db.query(User).filter(User.email == row.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    
    user.hashed_password = security.get_password_hash(new_password_data.new_password)
    db.delete(row)
    db.commit()
    return {"msg": "Contrase?a actualizada correctamente."}

@router.post(
    "/refresh", 
    response_model=Token,
    operation_id="auth_refresh_token_api_v1",
    summary="Refresh Access Token",
    description="Get a new access token using a refresh token"
)
async def refresh_token(
    refresh_token: str = Body(..., embed=True),
    db: Session = Depends(get_db)
):
    """
    Refresh access token using a valid refresh token.
    """
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refresh token is required"
        )
    
    # Get the token from database
    db_token = db.query(RefreshToken).filter(
        RefreshToken.token == refresh_token,
        RefreshToken.is_active == True,
        RefreshToken.expires_at > datetime.utcnow()
    ).first()
    
    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    
    # Get the user
    user = db.query(User).filter(User.id == db_token.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Invalidate the used refresh token
    db_token.is_active = False
    db_token.updated_at = datetime.utcnow()
    db.commit()
    
    # Create new tokens
    return await create_tokens(db, user)

@router.post(
    "/logout",
    operation_id="auth_logout_api_v1",
    summary="Logout User",
    description="Invalidate a refresh token to log out the user"
)
async def logout(
    refresh_token: str = Body(..., embed=True),
    db: Session = Depends(get_db)
):
    """
    Invalidate a refresh token (logout).
    """
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refresh token is required"
        )
    
    # Get the token from database and invalidate it
    db_token = db.query(RefreshToken).filter(
        RefreshToken.token == refresh_token,
        RefreshToken.is_active == True
    ).first()
    
    if db_token:
        user = db.query(User).filter(User.id == db_token.user_id).first()
        if user:
            try:
                from services.employee_work_session_service import end_work_session_on_logout

                end_work_session_on_logout(db, user)
            except Exception:
                logger.exception("end_work_session_on_logout")
        db_token.is_active = False
        db_token.updated_at = datetime.utcnow()
        db.commit()
    
    return {"message": "Successfully logged out"}
    

@router.get(
    "/me", 
    operation_id="auth_me_api_v1",
    summary="Get Current User",
    description="Get the currently authenticated user's information",
    response_description="Devuelve la informaci?n del usuario autenticado"
)
async def read_current_user(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Obtiene la informaci?n del usuario actualmente autenticado.
    Requiere un token de acceso v?lido en el encabezado de autorizaci?n.
    """
    try:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No autenticado",
            )
        
        # role: owner = due?o (n?minas, todo); employee = solo TPV + control horario
        role = getattr(current_user, "role", None) or "owner"

        company_ids = [
            r[0]
            for r in db.query(UserCompany.company_id)
            .filter(UserCompany.user_id == current_user.id)
            .all()
        ]
        ce = None
        if company_ids:
            ce = (
                db.query(CompanyEmployee)
                .filter(
                    CompanyEmployee.user_id == current_user.id,
                    CompanyEmployee.company_id.in_(company_ids),
                    CompanyEmployee.is_active.is_(True),
                )
                .order_by(CompanyEmployee.id.asc())
                .first()
            )

        from services.employee_work_session_service import get_jornada_status

        jornada = get_jornada_status(db, current_user)

        from services.company_module_config import get_company_config_for_user

        company_cfg = get_company_config_for_user(db, current_user)

        # Devolver en el formato esperado por el frontend
        return {
            "status": "success",
            "data": {
                "id": current_user.id,
                "email": current_user.email,
                "full_name": current_user.full_name,
                "is_active": current_user.is_active,
                "is_superuser": current_user.is_superuser,
                "role": role,
                "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
                "company_id": company_cfg.get("company_id"),
                "company_name": company_cfg.get("company_name"),
                "company_type": company_cfg.get("company_type"),
                "modules": company_cfg.get("modules"),
                "company_employee": None
                if not ce
                else {
                    "employee_code": ce.employee_code,
                    "full_name": ce.full_name,
                    "role_title": ce.role_title,
                },
                "jornada": jornada,
            }
        }
    except Exception as e:
        logger.error(f"Error en endpoint /me: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor"
        )

@router.get(
    "/test-token",
    response_model=UserSchema,
    summary="Test token",
    response_description="User information if token is valid",
)
async def test_token(current_user: User = Depends(get_current_active_user)):
    """
    Test if the current access token is valid and return user information.
    """
    return current_user

@router.post(
    "/debug/verify-token",
    operation_id="auth_debug_verify_token_api_v1",
    summary="[DEBUG] Verify Token",
    description="Debug endpoint to verify a JWT token and return detailed information. WARNING: For debugging only!"
)
async def debug_verify_token(
    token: str = Body(..., embed=True),
    db: Session = Depends(get_db)
):
    """
    Debug endpoint to verify a JWT token and return detailed information.
    This helps diagnose issues with token verification.
    
    WARNING: This is for debugging purposes only and should be disabled in production.
    """
    import logging
    from datetime import datetime
    
    logger = logging.getLogger(__name__)
    result = {
        "token_received": token[:10] + "..." if token else "None",
        "token_length": len(token) if token else 0,
        "verification_attempted": False,
        "verification_successful": False,
        "token_decoded": False,
        "token_expired": False,
        "token_invalid": False,
        "token_claims": {},
        "verification_error": None,
        "current_time_utc": datetime.utcnow().isoformat(),
        "server_timezone": str(datetime.now().astimezone().tzinfo),
    }
    
    if not token:
        result["verification_error"] = "No token provided"
        return result
    
    try:
        # Clean the token
        clean_token = token.replace('Bearer ', '', 1).strip()
        result["token_cleaned"] = clean_token[:10] + "..."
        
        # Try to decode without verification first to see the claims
        try:
            unverified_claims = jwt.get_unverified_claims(clean_token)
            result["unverified_claims"] = unverified_claims
            result["token_decoded"] = True
            
            # Check if token is expired
            if "exp" in unverified_claims:
                exp_timestamp = unverified_claims["exp"]
                current_timestamp = int(datetime.utcnow().timestamp())
                result["token_expired"] = exp_timestamp < current_timestamp
        except Exception as e:
            result["unverified_claims_error"] = str(e)
        
        # Now try to verify the token
        try:
            from app.core.jwt_auth import decode_jwt_token
            payload = decode_jwt_token(clean_token)
            result["token_claims"] = payload
            result["verification_successful"] = True
            
            # Get user info if available
            if "sub" in payload:
                user = get_user_by_email(db, payload["sub"])
                if user:
                    result["user"] = {
                        "id": user.id,
                        "email": user.email,
                        "is_active": user.is_active,
                        "is_superuser": user.is_superuser
                    }
            
        except jwt.ExpiredSignatureError as e:
            result["token_expired"] = True
            result["verification_error"] = "Token has expired"
        except jwt.InvalidTokenError as e:
            result["token_invalid"] = True
            result["verification_error"] = f"Invalid token: {str(e)}"
        except Exception as e:
            result["verification_error"] = f"Verification failed: {str(e)}"
        
        result["verification_attempted"] = True
        
    except Exception as e:
        result["error"] = f"Error processing token: {str(e)}"
    
    return result

@router.get(
    "/protected-test",
    operation_id="auth_protected_test_api_v1",
    summary="Protected Test Endpoint",
    description="A test endpoint that requires authentication"
)
async def protected_test_endpoint(current_user: User = Depends(get_current_active_user)):
    """
    A protected endpoint that returns test data.
    Requires a valid access token in the Authorization header.
    """
    return {
        "message": "This is a protected endpoint",
        "user_id": current_user.id,
        "email": current_user.email,
        "is_active": current_user.is_active,
        "is_superuser": current_user.is_superuser,
        "scopes": current_user.scopes or [],
        "permissions": ["read:data", "write:data"]  # Example permissions
    }
