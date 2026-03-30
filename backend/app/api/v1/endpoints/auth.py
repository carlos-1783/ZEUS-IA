import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Request, Form, Body, Header
from fastapi.responses import Response
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer

from app.core.auth import get_current_active_user, resolve_user_scopes
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core import security
from app.core.jwt_auth import create_access_token, create_refresh_token as create_jwt_refresh_token, get_current_user
from app.core.auth import authenticate_user, get_user_by_email
from app.core.security import get_password_hash, verify_password
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User, RefreshToken, PasswordResetToken
from app.schemas.token import Token, TokenRefresh, LoginRequest, RegisterRequest, ResetPasswordRequest, NewPasswordRequest
from services.email_service import email_service
from app.schemas.user import User as UserSchema

# Configurar logging
logger = logging.getLogger(__name__)

router = APIRouter()


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

        access_token = create_access_token(
            user_id=str(user.id),
            email=user.email,
            is_active=is_active,
            is_superuser=is_superuser,
            expires_delta=access_token_expires,
            scopes=user_scopes,
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
    response_model=UserSchema, 
    status_code=status.HTTP_201_CREATED,
    operation_id="auth_register_api_v1",
    summary="Register New User",
    description="Register a new user with email, password, full name and phone; sends welcome email if SMTP/SendGrid/Resend is configured"
)
async def register_user(
    user_data: RegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Registro completo: email, contraseña fuerte, nombre y teléfono.
    Tras crear el usuario se intenta enviar correo de bienvenida (no bloquea el 201 si falla el envío).
    """
    email_norm = str(user_data.email).strip().lower()
    if db.query(User).filter(User.email == email_norm).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        email=email_norm,
        hashed_password=hashed_password,
        full_name=user_data.full_name.strip(),
        phone=user_data.phone,
        is_active=True,
    )
    db.add(db_user)
    try:
        db.commit()
        db.refresh(db_user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    try:
        sent = await _send_register_welcome_email(db_user)
        if not sent.get("success"):
            logger.warning(
                "Registro OK pero email de bienvenida no enviado a %s: %s",
                email_norm,
                sent.get("error"),
            )
    except Exception as e:
        logger.warning("Registro OK pero error enviando bienvenida a %s: %s", email_norm, e)

    return db_user

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
                "created_at": current_user.created_at.isoformat() if current_user.created_at else None
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
