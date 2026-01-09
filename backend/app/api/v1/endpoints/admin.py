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
                "setup_price": plan_info["setup_price"]
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

