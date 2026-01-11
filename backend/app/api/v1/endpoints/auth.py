from datetime import datetime, timedelta
from typing import Any, Dict, Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Request, Form, Body, Header
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer

from app.core.auth import get_current_active_user, resolve_user_scopes
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.core import security
from app.core.jwt_auth import create_access_token, create_refresh_token as create_jwt_refresh_token, get_current_user
from app.core.auth import authenticate_user, get_user_by_email
from app.core.security import get_password_hash, verify_password
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User, RefreshToken
from app.schemas.token import Token, TokenRefresh, LoginRequest, RegisterRequest, ResetPasswordRequest, NewPasswordRequest
from app.schemas.user import User as UserSchema

# Configurar logging
logger = logging.getLogger(__name__)

router = APIRouter()

async def create_tokens(db: Session, user: User) -> Dict[str, Any]:
    """
    Create access and refresh tokens for user using the new JWT module
    """
    try:
        # Calculate token expiration
        access_token_expires = timedelta(minutes=float(settings.ACCESS_TOKEN_EXPIRE_MINUTES))
        refresh_token_expires = timedelta(days=float(settings.REFRESH_TOKEN_EXPIRE_DAYS))
        
        # Create access token using the new JWT module
        user_scopes = resolve_user_scopes(user)

        access_token = create_access_token(
            user_id=str(user.id),
            email=user.email,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
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
            "full_name": user.full_name,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser,
            "scopes": user_scopes,
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating tokens for user {user.email}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating authentication tokens: {str(e)}"
        )

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
        
        # Verificar si el usuario está activo
        if not user.is_active:
            logger.warning(f"Intento de login de usuario inactivo: {username}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user"
            )
        
        logger.info(f"Login exitoso para usuario: {username}")
        
        # Crear tokens de acceso y actualización
        return await create_tokens(db, user)
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error in login endpoint for user {username}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during login"
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
    
    Este endpoint es compatible con el estándar OAuth2 y se puede utilizar con clientes
    que esperan el flujo de contraseña de OAuth2.
    """
    # Autenticar al usuario
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verificar si el usuario está activo
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    # Usar la misma función create_tokens que en el endpoint /login
    return await create_tokens(db, user)

@router.post(
    "/register", 
    response_model=UserSchema, 
    status_code=status.HTTP_201_CREATED,
    operation_id="auth_register_api_v1",
    summary="Register New User",
    description="Register a new user with email and password"
)
async def register_user(
    user_data: dict = Body(...),
    db: Session = Depends(get_db)
):
    """
    Register a new user
    - email: must be a valid email
    - password: min 8 chars, must contain uppercase, lowercase and number
    - full_name: min 3 chars, max 100
    """
    try:
        # Validate email
        if not user_data.get('email') or '@' not in user_data['email']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format"
            )
            
        # Check if user already exists
        db_user = db.query(User).filter(User.email == user_data['email']).first()
        if db_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Validate password
        password = user_data.get('password', '')
        if len(password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long"
            )
        
        # Create new user
        hashed_password = get_password_hash(password)
        db_user = User(
            email=user_data['email'],
            hashed_password=hashed_password,
            full_name=user_data.get('full_name', ''),
            is_active=True
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post(
    "/reset-password",
    operation_id="auth_reset_password_api_v1",
    summary="Reset Password",
    description="Request a password reset for a user"
)
async def reset_password(
    reset_data: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """Request password reset"""
    user = db.query(User).filter(User.email == reset_data.email).first()
    if user:
        # In a real app, send an email with a reset token
        pass
    return {"msg": "If your email is registered, you will receive a password reset link"}

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
    """Set new password with reset token"""
    # In a real app, validate the reset token
    # For now, just update the password if user exists
    user = db.query(User).filter(User.email == new_password_data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    hashed_password = security.get_password_hash(new_password_data.new_password)
    user.hashed_password = hashed_password
    db.commit()
    return {"msg": "Password updated successfully"}

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
    response_description="Devuelve la información del usuario autenticado"
)
async def read_current_user(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Obtiene la información del usuario actualmente autenticado.
    Requiere un token de acceso válido en el encabezado de autorización.
    """
    try:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No autenticado",
            )
        
        # Devolver en el formato esperado por el frontend
        return {
            "status": "success",
            "data": {
                "id": current_user.id,
                "email": current_user.email,
                "full_name": current_user.full_name,
                "is_active": current_user.is_active,
                "is_superuser": current_user.is_superuser,
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
