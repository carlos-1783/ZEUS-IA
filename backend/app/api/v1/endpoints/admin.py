"""
🔐 Admin Panel Endpoints
Endpoints para el panel de administración (solo superusuarios)
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from typing import Dict, Any, List
from datetime import datetime, timedelta
from collections import defaultdict

from app.db.session import get_db
from app.core.auth import get_current_active_superuser
from app.models.user import User

router = APIRouter()


# Precios de los planes (deben coincidir con onboarding.py)
PRICING_PLANS = {
    "startup": {"monthly_price": 197, "setup_price": 197},
    "growth": {"monthly_price": 497, "setup_price": 497},
    "business": {"monthly_price": 897, "setup_price": 897},
    "enterprise": {"monthly_price": 1797, "setup_price": 1797}
}


@router.get("/stats")
async def get_admin_stats(
    current_user: User = Depends(get_current_active_superuser),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Obtener estadísticas generales del panel de administración
    """
    try:
        # Contar usuarios totales (clientes)
        total_customers = db.query(User).count()
        
        # Contar usuarios activos (suscripciones activas)
        active_subscriptions = db.query(User).filter(
            User.is_active == True
        ).count()
        
        # Calcular ingresos mensuales (suma de monthly_price de usuarios activos)
        active_users = db.query(User).filter(
            User.is_active == True
        ).all()
        
        monthly_revenue = 0
        total_setup_fees = 0
        revenue_by_plan = defaultdict(lambda: {"count": 0, "monthly_total": 0})
        
        for user in active_users:
            # Manejar casos donde plan puede ser None o string vacío
            plan = getattr(user, 'plan', None)
            if not plan:
                continue
            plan = plan.lower().strip()
            if plan and plan in PRICING_PLANS:
                plan_info = PRICING_PLANS[plan]
                monthly_revenue += plan_info["monthly_price"]
                total_setup_fees += plan_info["setup_price"]
                
                # Agrupar por plan
                plan_name = plan.upper()
                revenue_by_plan[plan_name]["count"] += 1
                revenue_by_plan[plan_name]["monthly_total"] += plan_info["monthly_price"]
        
        # Ingresos totales (setup fees + proyección de 12 meses de suscripciones)
        total_revenue = total_setup_fees + (monthly_revenue * 12)
        
        # Convertir revenue_by_plan a lista
        revenue_by_plan_list = [
            {
                "name": f"ZEUS {plan_name}",
                "count": data["count"],
                "monthly_total": data["monthly_total"]
            }
            for plan_name, data in revenue_by_plan.items()
        ]
        
        return {
            "success": True,
            "stats": {
                "total_customers": total_customers,
                "monthly_revenue": round(monthly_revenue, 2),
                "total_revenue": round(total_revenue, 2),
                "active_subscriptions": active_subscriptions,
                "total_setup_fees": round(total_setup_fees, 2)
            },
            "revenue_by_plan": revenue_by_plan_list,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo estadísticas: {str(e)}"
        )


@router.get("/customers")
async def get_admin_customers(
    current_user: User = Depends(get_current_active_superuser),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Obtener lista de todos los clientes/usuarios
    """
    try:
        users = db.query(User).order_by(User.created_at.desc()).all()
        
        customers = []
        for user in users:
            plan = user.plan and user.plan.lower()
            plan_info = PRICING_PLANS.get(plan, {"monthly_price": 0, "setup_price": 0})
            
            # Calcular próximo pago (30 días desde creación o último update)
            next_payment_date = user.updated_at or user.created_at
            if next_payment_date:
                next_payment = next_payment_date + timedelta(days=30)
            else:
                next_payment = None
            
            customers.append({
                "id": user.id,
                "email": user.email,
                "company_name": getattr(user, 'company_name', 'N/A') or 'N/A',
                "full_name": user.full_name or user.email,
                "plan": plan or 'none',
                "employees": getattr(user, 'employees', 0) or 0,
                "status": "active" if user.is_active else "inactive",
                "is_superuser": user.is_superuser,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "next_payment": next_payment.isoformat() if next_payment else None,
                "monthly_price": plan_info["monthly_price"],
                "setup_price": plan_info["setup_price"],
                "public_site_enabled": getattr(user, "public_site_enabled", False),
                "public_site_slug": getattr(user, "public_site_slug", None) or "",
            })
        
        return {
            "success": True,
            "customers": customers,
            "total": len(customers),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo clientes: {str(e)}"
        )


@router.patch("/customers/{customer_id}")
async def update_admin_customer(
    customer_id: int,
    body: Dict[str, Any],
    current_user: User = Depends(get_current_active_superuser),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Actualizar datos de un cliente (empresa, plan, empleados). Solo superuser.
    """
    user = db.query(User).filter(User.id == customer_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    if user.is_superuser and user.id != current_user.id:
        raise HTTPException(status_code=400, detail="No se puede editar a otro superusuario")
    if "company_name" in body and body["company_name"] is not None:
        user.company_name = str(body["company_name"]).strip() or None
    if "plan" in body and body["plan"] is not None:
        plan = str(body["plan"]).strip().lower()
        user.plan = plan if plan in PRICING_PLANS else None
    if "employees" in body and body["employees"] is not None:
        try:
            user.employees = int(body["employees"]) if body["employees"] != "" else None
        except (TypeError, ValueError):
            pass
    # Web pública por cliente (opción B para todos; si no la necesita, desactivar)
    if "public_site_enabled" in body and body["public_site_enabled"] is not None:
        user.public_site_enabled = bool(body["public_site_enabled"])
    if "public_site_slug" in body and body["public_site_slug"] is not None:
        slug = str(body["public_site_slug"]).strip().lower() if body["public_site_slug"] else None
        if slug:
            existing = db.query(User).filter(User.public_site_slug == slug, User.id != user.id).first()
            if existing:
                raise HTTPException(status_code=400, detail="Ese slug ya está usado por otro cliente")
        user.public_site_slug = slug if slug else None
        if getattr(user, "public_site_enabled", False) and not user.public_site_slug:
            user.public_site_enabled = False  # slug obligatorio si web pública activa
    db.commit()
    db.refresh(user)
    plan = (user.plan or "").lower()
    plan_info = PRICING_PLANS.get(plan, {"monthly_price": 0, "setup_price": 0})
    next_payment_date = user.updated_at or user.created_at
    next_payment = (next_payment_date + timedelta(days=30)) if next_payment_date else None
    return {
        "success": True,
        "customer": {
            "id": user.id,
            "email": user.email,
            "company_name": getattr(user, "company_name", None) or "N/A",
            "full_name": user.full_name or user.email,
            "plan": plan or "none",
            "employees": getattr(user, "employees", 0) or 0,
            "status": "active" if user.is_active else "inactive",
            "next_payment": next_payment.isoformat() if next_payment else None,
            "monthly_price": plan_info["monthly_price"],
            "setup_price": plan_info["setup_price"],
            "public_site_enabled": getattr(user, "public_site_enabled", False),
            "public_site_slug": getattr(user, "public_site_slug", None) or "",
        },
    }


@router.get("/revenue-chart")
async def get_revenue_chart_data(
    months: int = 12,
    current_user: User = Depends(get_current_active_superuser),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Obtener datos de ingresos por mes para el gráfico
    """
    try:
        # Obtener usuarios activos con sus fechas de creación
        active_users = db.query(User).filter(
            User.is_active == True
        ).all()
        
        # Calcular ingresos por mes
        revenue_by_month = defaultdict(lambda: {"revenue": 0, "setup": 0, "subscriptions": 0})
        
        now = datetime.utcnow()
        for user in active_users:
            # Manejar casos donde plan puede ser None o string vacío
            plan = getattr(user, 'plan', None)
            if not plan:
                continue
            plan = plan.lower().strip()
            if plan and plan in PRICING_PLANS:
                plan_info = PRICING_PLANS[plan]
                
                # Mes de creación (setup fee)
                created_month = user.created_at.strftime("%Y-%m") if user.created_at else None
                if created_month:
                    revenue_by_month[created_month]["setup"] += plan_info["setup_price"]
                    revenue_by_month[created_month]["subscriptions"] += 1
                
                # Ingresos mensuales recurrentes (todos los meses desde creación hasta ahora)
                if user.created_at:
                    current_date = user.created_at.replace(day=1)
                    while current_date <= now.replace(day=1):
                        month_key = current_date.strftime("%Y-%m")
                        revenue_by_month[month_key]["revenue"] += plan_info["monthly_price"]
                        current_date = (current_date + timedelta(days=32)).replace(day=1)
        
        # Ordenar por mes y limitar a los últimos N meses
        sorted_months = sorted(revenue_by_month.keys(), reverse=True)[:months]
        sorted_months.reverse()  # Más antiguo primero
        
        chart_data = {
            "labels": sorted_months,
            "datasets": [
                {
                    "label": "Ingresos Mensuales (€)",
                    "data": [revenue_by_month[month]["revenue"] for month in sorted_months],
                    "backgroundColor": "rgba(59, 130, 246, 0.6)",
                    "borderColor": "rgba(59, 130, 246, 1)",
                    "borderWidth": 2
                },
                {
                    "label": "Setup Fees (€)",
                    "data": [revenue_by_month[month]["setup"] for month in sorted_months],
                    "backgroundColor": "rgba(16, 185, 129, 0.6)",
                    "borderColor": "rgba(16, 185, 129, 1)",
                    "borderWidth": 2
                }
            ]
        }
        
        return {
            "success": True,
            "chart_data": chart_data,
            "months": months,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo datos del gráfico: {str(e)}"
        )


@router.patch("/users/{user_id}/role")
async def set_user_role(
    user_id: int,
    body: Dict[str, str],
    current_user: User = Depends(get_current_active_superuser),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Asignar rol a un usuario: owner (dueño, acceso completo) o employee (solo TPV + control horario).
    Solo superusuario.
    """
    role = (body.get("role") or "").strip().lower()
    if role not in ("owner", "employee"):
        raise HTTPException(status_code=400, detail="role debe ser 'owner' o 'employee'")
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    target.role = role
    db.commit()
    db.refresh(target)
    return {"success": True, "user_id": user_id, "role": target.role}


@router.post("/bootstrap-internal-company")
async def bootstrap_internal_company(
    current_user: User = Depends(get_current_active_superuser),
) -> Dict[str, Any]:
    """
    ZEUS_INTERNAL_COMPANY_BOOTSTRAP_002: Crea empresa ZEUS INTERNAL (NORMAL),
    vincula superusuario, inicializa contexto, persiste AgentActivity y envía WhatsApp.
    Solo superusuario. Idempotente.
    """
    try:
        from services.internal_company_bootstrap import run_bootstrap
        result = run_bootstrap()
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Bootstrap error: {str(e)}",
        )

