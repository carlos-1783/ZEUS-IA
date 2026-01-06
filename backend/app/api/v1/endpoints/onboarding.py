"""
🎯 Onboarding Endpoints
Gestión de registro y activación de cuentas después del pago
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash
from services.email_service import email_service
import secrets
import string

router = APIRouter()

# ============================================================================
# PRICING MODEL - AUTHORITATIVE PRICES
# ============================================================================

# Precios oficiales unificados (en euros)
PRICING_PLANS = {
    "startup": {
        "name": "ZEUS STARTUP",
        "setup_price": 197,
        "monthly_price": 197,
        "employee_range": (1, 5),
        "description": "Ideal para autónomos y pequeños estudios"
    },
    "growth": {
        "name": "ZEUS GROWTH",
        "setup_price": 497,
        "monthly_price": 497,
        "employee_range": (6, 25),
        "description": "PYMEs y startups en crecimiento"
    },
    "business": {
        "name": "ZEUS BUSINESS",
        "setup_price": 897,
        "monthly_price": 897,
        "employee_range": (26, 100),
        "description": "Empresas establecidas"
    },
    "enterprise": {
        "name": "ZEUS ENTERPRISE",
        "setup_price": 1797,
        "monthly_price": 1797,
        "employee_range": (101, None),  # None significa sin límite superior
        "description": "Grandes corporaciones"
    }
}

def validate_plan_vs_employees(plan: str, employees: int) -> tuple[bool, Optional[str]]:
    """
    Validar que el plan seleccionado corresponde al número de empleados.
    
    Returns:
        (is_valid, error_message)
    """
    if plan not in PRICING_PLANS:
        return False, f"Plan '{plan}' no válido. Planes válidos: {list(PRICING_PLANS.keys())}"
    
    plan_config = PRICING_PLANS[plan]
    min_employees, max_employees = plan_config["employee_range"]
    
    if employees < min_employees:
        return False, f"El plan '{plan_config['name']}' requiere mínimo {min_employees} empleados. Tienes {employees}."
    
    if max_employees is not None and employees > max_employees:
        return False, f"El plan '{plan_config['name']}' es para máximo {max_employees} empleados. Tienes {employees}. Considera el plan 'enterprise'."
    
    return True, None

# ============================================================================
# MODELS
# ============================================================================

class OnboardingRequest(BaseModel):
    company_name: str
    email: EmailStr
    full_name: str
    employees: int
    plan: str  # startup, growth, business, enterprise
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    payment_intent_id: Optional[str] = None
    email_gestor_fiscal: Optional[EmailStr] = None
    email_asesor_legal: Optional[EmailStr] = None
    autoriza_envio_documentos_a_asesores: Optional[bool] = False

# ============================================================================
# HELPERS
# ============================================================================

def generate_random_password(length: int = 16) -> str:
    """Generar contraseña aleatoria segura"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    return password

def get_db():
    """Dependency para obtener sesión de BD"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/create-account")
async def create_account_after_payment(
    request: OnboardingRequest,
    db: Session = Depends(get_db)
):
    """
    Crear cuenta de usuario después de pago exitoso
    
    Args:
        request: Datos del cliente y pago
        
    Returns:
        Dict con credenciales y detalles de la cuenta
    """
    try:
        # 1. Validar plan vs número de empleados
        is_valid, error_msg = validate_plan_vs_employees(request.plan, request.employees)
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail=error_msg
            )
        
        # 2. Verificar que el email no exista
        existing_user = db.query(User).filter(User.email == request.email).first()
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="Ya existe una cuenta con este email"
            )
        
        # 3. Generar contraseña temporal
        temp_password = generate_random_password()
        
        # 4. Crear usuario
        new_user = User(
            email=request.email,
            full_name=request.full_name,
            hashed_password=get_password_hash(temp_password),
            is_active=True,
            is_superuser=False,
            company_name=request.company_name,
            employees=request.employees,
            plan=request.plan,
            email_gestor_fiscal=request.email_gestor_fiscal,
            email_asesor_legal=request.email_asesor_legal,
            autoriza_envio_documentos_a_asesores=request.autoriza_envio_documentos_a_asesores or False
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        # 5. Guardar metadata del plan (podríamos crear tabla separada después)
        # Por ahora lo guardamos en logs
        plan_config = PRICING_PLANS[request.plan]
        account_metadata = {
            "user_id": new_user.id,
            "company_name": request.company_name,
            "employees": request.employees,
            "plan": request.plan,
            "plan_name": plan_config["name"],
            "setup_price": plan_config["setup_price"],
            "monthly_price": plan_config["monthly_price"],
            "stripe_customer_id": request.stripe_customer_id,
            "stripe_subscription_id": request.stripe_subscription_id,
            "payment_intent_id": request.payment_intent_id,
            "created_at": datetime.utcnow().isoformat(),
            "status": "active"
        }
        
        print(f"[ONBOARDING] Nueva cuenta creada: {account_metadata}")
        
        # 6. Enviar email de bienvenida
        email_sent = await send_welcome_email(
            email=request.email,
            company_name=request.company_name,
            full_name=request.full_name,
            temp_password=temp_password,
            plan=request.plan
        )
        
        return {
            "success": True,
            "user_id": new_user.id,
            "email": request.email,
            "company_name": request.company_name,
            "plan": request.plan,
            "credentials": {
                "email": request.email,
                "password": temp_password
            },
            "email_sent": email_sent,
            "message": "Cuenta creada exitosamente. Revisa tu email para las credenciales."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error al crear cuenta: {str(e)}"
        )

async def send_welcome_email(
    email: str,
    company_name: str,
    full_name: str,
    temp_password: str,
    plan: str
) -> bool:
    """Enviar email de bienvenida con credenciales"""
    
    plan_names = {
        "startup": "ZEUS STARTUP",
        "growth": "ZEUS GROWTH",
        "business": "ZEUS BUSINESS",
        "enterprise": "ZEUS ENTERPRISE"
    }
    
    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; }}
            .header {{ background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%); padding: 30px; text-align: center; }}
            .header h1 {{ color: white; margin: 0; font-size: 32px; }}
            .content {{ padding: 40px 30px; background: #f9fafb; }}
            .credentials-box {{ background: #1a1f2e; color: white; padding: 20px; border-radius: 10px; margin: 20px 0; }}
            .cta-button {{ display: inline-block; background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%); color: white; padding: 16px 32px; text-decoration: none; border-radius: 8px; font-weight: bold; }}
            .footer {{ padding: 20px; text-align: center; background: #e5e7eb; font-size: 12px; color: #6b7280; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>⚡ Bienvenido a ZEUS-IA</h1>
        </div>
        
        <div class="content">
            <h2>¡Hola {full_name}!</h2>
            
            <p>Gracias por unirte a ZEUS-IA. Tu cuenta para <strong>{company_name}</strong> ha sido creada exitosamente.</p>
            
            <p>Has adquirido el plan <strong>{plan_names.get(plan, plan)}</strong>.</p>
            
            <h3>🔐 Tus credenciales de acceso:</h3>
            
            <div class="credentials-box">
                <p><strong>URL:</strong> https://zeus-ia-production-16d8.up.railway.app/dashboard</p>
                <p><strong>Email:</strong> {email}</p>
                <p><strong>Contraseña temporal:</strong> {temp_password}</p>
            </div>
            
            <p>⚠️ <strong>IMPORTANTE:</strong> Te recomendamos cambiar esta contraseña temporal en tu primer acceso desde Configuración.</p>
            
            <h3>🚀 Próximos pasos:</h3>
            <ol>
                <li>Accede al dashboard con tus credenciales</li>
                <li>Explora los 5 agentes IA disponibles</li>
                <li>Configura tus integraciones (WhatsApp, Email, etc.)</li>
                <li>¡Empieza a automatizar tu empresa!</li>
            </ol>
            
            <p style="text-align: center; margin-top: 30px;">
                <a href="https://zeus-ia-production-16d8.up.railway.app/dashboard" class="cta-button">
                    Acceder al Dashboard →
                </a>
            </p>
            
            <p style="margin-top: 30px;">Si tienes alguna pregunta, responde a este email y nuestro equipo te ayudará.</p>
            
            <p>¡Bienvenido al Olimpo! ⚡</p>
            <p><em>El equipo de ZEUS-IA</em></p>
        </div>
        
        <div class="footer">
            <p>Este email fue enviado por ZEUS-IA</p>
            <p>© 2025 ZEUS-IA. Todos los derechos reservados.</p>
        </div>
    </body>
    </html>
    """
    
    if email_service.is_configured():
        result = await email_service.send_email(
            to_email=email,
            subject=f"🎉 Bienvenido a ZEUS-IA - Tus credenciales de acceso",
            content=html_content,
            content_type="text/html"
        )
        return result.get("success", False)
    else:
        # Si no está configurado SendGrid, mostrar en consola
        print("\n" + "="*80)
        print("📧 EMAIL DE BIENVENIDA (SendGrid no configurado)")
        print("="*80)
        print(f"Para: {email}")
        print(f"Empresa: {company_name}")
        print(f"Contraseña temporal: {temp_password}")
        print("="*80 + "\n")
        return True

@router.get("/verify-payment/{payment_intent_id}")
async def verify_payment_status(payment_intent_id: str):
    """
    Verificar estado de un pago
    
    Args:
        payment_intent_id: ID del Payment Intent de Stripe
        
    Returns:
        Dict con estado del pago
    """
    try:
        from services.stripe_service import stripe_service
        
        if not stripe_service.is_configured():
            raise HTTPException(
                status_code=400,
                detail="Stripe no está configurado"
            )
        
        import stripe
        
        payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        
        return {
            "success": True,
            "payment_intent_id": payment_intent_id,
            "status": payment_intent.status,
            "amount": payment_intent.amount / 100,
            "currency": payment_intent.currency,
            "customer_email": payment_intent.receipt_email,
            "created": payment_intent.created
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al verificar pago: {str(e)}"
        )

@router.post("/complete-onboarding")
async def complete_onboarding(
    email: EmailStr,
    db: Session = Depends(get_db)
):
    """
    Completar onboarding (cambiar contraseña, configurar preferencias, etc.)
    """
    try:
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            raise HTTPException(
                status_code=404,
                detail="Usuario no encontrado"
            )
        
        # Aquí podríamos añadir más configuraciones
        
        return {
            "success": True,
            "message": "Onboarding completado",
            "user_id": user.id,
            "email": user.email
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al completar onboarding: {str(e)}"
        )

@router.get("/status/{email}")
async def get_onboarding_status(
    email: EmailStr,
    db: Session = Depends(get_db)
):
    """Obtener estado del onboarding de un usuario"""
    try:
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            return {
                "exists": False,
                "onboarding_complete": False
            }
        
        return {
            "exists": True,
            "user_id": user.id,
            "email": user.email,
            "is_active": user.is_active,
            "onboarding_complete": True  # Podríamos añadir campo en BD
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al verificar estado: {str(e)}"
        )

