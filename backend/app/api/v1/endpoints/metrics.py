"""
Endpoints para métricas y analytics del sistema
"""
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.tenant_context import get_db_scoped
from app.core.auth import get_current_active_user
from app.models.user import User
import services.crm_office_service as crm_svc
from services.chain_log import business_activities, is_success_status

router = APIRouter()

NO_DATA = "Sin datos"


def _avg_response_seconds(rows) -> Optional[float]:
    times = [
        (a.completed_at - a.created_at).total_seconds()
        for a in rows
        if a.completed_at and a.created_at
    ]
    return (sum(times) / len(times)) if times else None


def _success_pct(rows) -> Optional[float]:
    return (len([a for a in rows if is_success_status(a.status)]) / len(rows) * 100) if rows else None


def _real_trends(current: list, previous: list) -> Dict[str, Any]:
    """Tendencias SOLO contra el periodo anterior real del mismo tenant.

    Antes: "ahorro" = exitos x 50 EUR inventados, "tendencia de exito" contra un 96 % fijo y
    "tendencia de respuesta" contra 1 s fijo. Sin base real para un ahorro en euros, se
    devuelve "Sin datos" en lugar de inventarlo.
    """
    out: Dict[str, Any] = {"cost_savings": NO_DATA, "savings_trend": NO_DATA}
    if previous:
        change = (len(current) - len(previous)) / len(previous) * 100
        out["interactions_trend"] = f"{change:+.0f}% vs periodo anterior" if change else "estable"
    else:
        out["interactions_trend"] = NO_DATA
    cur_rt, prev_rt = _avg_response_seconds(current), _avg_response_seconds(previous)
    if cur_rt is not None and prev_rt:
        out["response_trend"] = f"{(cur_rt - prev_rt) / prev_rt * 100:+.0f}% vs periodo anterior"
    else:
        out["response_trend"] = NO_DATA
    cur_ok, prev_ok = _success_pct(current), _success_pct(previous)
    if cur_ok is not None and prev_ok is not None:
        out["success_trend"] = f"{cur_ok - prev_ok:+.1f} pp vs periodo anterior"
    else:
        out["success_trend"] = NO_DATA
    return out


@router.get("/dashboard")
async def get_dashboard_metrics(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db_scoped)
) -> Dict[str, Any]:
    """
    Métricas del dashboard principal
    Devuelve métricas calculadas de actividades reales de agentes,
    aisladas por tenant (company_id). Mismo patrón que
    services/crm_office_service.py: permitido si AgentActivity.company_id
    está entre las empresas del usuario, o si es una actividad legacy sin
    company_id que quedó asociada a este mismo usuario por email.
    """
    try:
        from app.models.agent_activity import AgentActivity
        from sqlalchemy import true

        if getattr(current_user, "is_superuser", False):
            # Bypass explícito: este filtro es independiente de RLS (se
            # aplica a nivel de aplicación sobre `db`, que ya viene con RLS
            # bypasseado por get_db_scoped para superusuarios — ver
            # app/db/tenant_context.py). Sin este check, un superusuario sin
            # empresa asignada en user_companies solo veía las actividades
            # de sistema (company_id NULL) atribuidas a su propio email, no
            # los datos reales de ninguna empresa.
            tenant_filter = true()
        else:
            allowed_company_ids = crm_svc.company_ids_for_user(db, current_user)
            tenant_filter = or_(
                AgentActivity.company_id.in_(allowed_company_ids),
                and_(AgentActivity.company_id.is_(None), AgentActivity.user_email == current_user.email),
            )

        # Calcular rango de fechas
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Consultar actividades del tenant del usuario autenticado
        activities = db.query(AgentActivity).filter(
            AgentActivity.created_at >= start_date,
            AgentActivity.created_at <= end_date,
            tenant_filter,
        ).all()
        activities = business_activities(activities)  # J7: sin trazas chain_*

        # Calcular métricas
        total_interactions = len(activities)
        completed = len([a for a in activities if is_success_status(a.status)])
        failed = len([a for a in activities if a.status == 'failed'])

        success_rate = (completed / total_interactions * 100) if total_interactions > 0 else 0

        # Calcular tiempo promedio de respuesta
        response_times = []
        for activity in activities:
            if activity.completed_at and activity.created_at:
                delta = (activity.completed_at - activity.created_at).total_seconds()
                response_times.append(delta)

        avg_response = sum(response_times) / len(response_times) if response_times else 0

        # Tendencias: comparar con el período anterior real del mismo tenant
        prev_start = start_date - timedelta(days=days)
        prev_activities_query = db.query(AgentActivity).filter(
            AgentActivity.created_at >= prev_start,
            AgentActivity.created_at < start_date,
            tenant_filter,
        )
        prev_activities = business_activities(prev_activities_query.all())  # J7: sin chain_*

        return {
            "success": True,
            "total_interactions": total_interactions,
            "avg_response_time": f"{avg_response:.1f}s" if response_times else NO_DATA,
            "success_rate": f"{success_rate:.1f}%" if total_interactions else NO_DATA,
            **_real_trends(activities, prev_activities),
        }

    except Exception as e:
        import logging

        logging.getLogger(__name__).error("get_dashboard_metrics: %s", e, exc_info=True)
        # Sin falso éxito ni ceros que parezcan medidos.
        return {
            "success": False,
            "error": "No se pudieron calcular las métricas.",
            "total_interactions": None,
            "avg_response_time": NO_DATA,
            "cost_savings": NO_DATA,
            "success_rate": NO_DATA,
            "interactions_trend": NO_DATA,
            "response_trend": NO_DATA,
            "savings_trend": NO_DATA,
            "success_trend": NO_DATA,
        }

@router.get("/performance")
async def get_performance_metrics(
    agent: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Métricas de rendimiento por agente (datos reales de activity_log)."""
    from app.models.agent_activity import AgentActivity
    from datetime import timedelta

    since = datetime.utcnow() - timedelta(days=days)
    q = db.query(AgentActivity).filter(AgentActivity.created_at >= since)
    if agent:
        q = q.filter(AgentActivity.agent_name == agent.upper())
    if not getattr(current_user, "is_superuser", False):
        q = q.filter(AgentActivity.user_email == current_user.email)
    activities = business_activities(q.all())  # J7: sin trazas chain_*
    total = len(activities)
    completed = sum(1 for a in activities if is_success_status(a.status))
    failed = sum(1 for a in activities if a.status == "failed")
    response_times = []
    for a in activities:
        if a.completed_at and a.created_at:
            response_times.append((a.completed_at - a.created_at).total_seconds())
    avg_rt = sum(response_times) / len(response_times) if response_times else 0.0
    success_pct = (completed / total * 100) if total else 0.0
    error_pct = (failed / total * 100) if total else 0.0
    return {
        "success": True,
        "agent": agent or "all",
        "response_times": {
            "avg": f"{avg_rt:.1f}s",
            "samples": len(response_times),
        },
        "success_rate": f"{success_pct:.1f}%",
        "error_rate": f"{error_pct:.1f}%",
        "total_activities": total,
    }


@router.get("/summary")
async def get_dashboard_summary(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Endpoint unificado para dashboard (móvil y desktop)
    Devuelve los mismos datos normalizados independientemente del dispositivo
    Los superusuarios ven todos los módulos sin restricciones de business_profile
    """
    try:
        from app.models.agent_activity import AgentActivity
        
        is_superuser = getattr(current_user, 'is_superuser', False)
        
        # Calcular rango de fechas (UTC para consistencia)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Consultar actividades (sin filtro de usuario para superusuarios)
        activities_query = db.query(AgentActivity).filter(
            AgentActivity.created_at >= start_date,
            AgentActivity.created_at <= end_date
        )
        
        # Siempre filtrar por usuario autenticado (evita mezcla entre cuentas en BD compartida)
        activities_query = activities_query.filter(
            AgentActivity.user_email == current_user.email
        )
        
        activities = business_activities(activities_query.all())  # J7: sin trazas chain_*
        
        # Calcular métricas
        total_interactions = len(activities)
        completed = len([a for a in activities if is_success_status(a.status)])
        failed = len([a for a in activities if a.status == 'failed'])
        
        success_rate = (completed / total_interactions * 100) if total_interactions > 0 else 0
        
        # Calcular tiempo promedio de respuesta
        response_times = []
        for activity in activities:
            if activity.completed_at and activity.created_at:
                delta = (activity.completed_at - activity.created_at).total_seconds()
                response_times.append(delta)
        
        avg_response = sum(response_times) / len(response_times) if response_times else 0
        
        # Calcular tendencias (comparar con período anterior)
        prev_start = start_date - timedelta(days=days)
        prev_activities_query = db.query(AgentActivity).filter(
            AgentActivity.created_at >= prev_start,
            AgentActivity.created_at < start_date
        )
        
        prev_activities_query = prev_activities_query.filter(
            AgentActivity.user_email == current_user.email
        )
        
        prev_activities = business_activities(prev_activities_query.all())  # J7: sin chain_*

        tpv_business_profile = getattr(current_user, 'tpv_business_profile', None) if not is_superuser else None
        control_horario_business_profile = getattr(current_user, 'control_horario_business_profile', None) if not is_superuser else None

        from services.company_module_config import get_company_config_for_user

        company_cfg = get_company_config_for_user(db, current_user)
        available_modules = company_cfg["modules"]

        from services.analytics_service import build_analytics_summary

        analytics = build_analytics_summary(db, current_user, days=days)
        from services.zeus_analytics_real_v1 import backfill_events_from_domain_bus, build_executive_analytics

        backfill_events_from_domain_bus(db)
        executive = build_executive_analytics(db, current_user)
        
        return {
            "success": True,
            "user": {
                "id": current_user.id,
                "email": current_user.email,
                "is_superuser": is_superuser,
                "tpv_business_profile": tpv_business_profile,
                "control_horario_business_profile": control_horario_business_profile,
                "company_type": company_cfg.get("company_type"),
                "company_id": company_cfg.get("company_id"),
            },
            "company_type": company_cfg.get("company_type"),
            "metrics": {
                "total_interactions": total_interactions,
                "avg_response_time": f"{avg_response:.1f}s" if response_times else NO_DATA,
                "success_rate": f"{success_rate:.1f}%" if total_interactions else NO_DATA,
                **_real_trends(activities, prev_activities),
                "total_revenue": analytics["financial"]["total_revenue"],
                "sales_count": analytics["financial"]["sales_count"],
                "avg_ticket": analytics["financial"]["avg_ticket"],
                "active_customers": analytics["customers"]["active_total"],
                "cmr_payments_count": analytics["financial"]["cmr_payments_count"],
                "tpv_sales_count": analytics["financial"]["tpv_sales_count"],
            },
            "analytics": analytics,
            "executive": executive,
            "available_modules": available_modules,
            "timezone": "UTC",
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": days
            }
        }
        
    except Exception as e:
        import logging
        from services.company_module_config import get_company_config_for_user

        logger = logging.getLogger(__name__)
        logger.error(f"❌ Error calculando dashboard summary: {e}", exc_info=True)
        # Devolver valores por defecto si hay error
        return {
            "success": False,
            "error": "No se pudo calcular el resumen del dashboard.",
            "user": {
                "id": current_user.id if current_user else None,
                "email": current_user.email if current_user else None,
                "is_superuser": getattr(current_user, 'is_superuser', False) if current_user else False,
                "tpv_business_profile": getattr(current_user, 'tpv_business_profile', None) if current_user and not getattr(current_user, 'is_superuser', False) else None,
                "control_horario_business_profile": getattr(current_user, 'control_horario_business_profile', None) if current_user and not getattr(current_user, 'is_superuser', False) else None
            },
            "metrics": {
                "total_interactions": 0,
                "avg_response_time": NO_DATA,
                "cost_savings": NO_DATA,
                "success_rate": NO_DATA,
                "interactions_trend": NO_DATA,
                "response_trend": NO_DATA,
                "savings_trend": NO_DATA,
                "success_trend": NO_DATA
            },
            "available_modules": (
                get_company_config_for_user(db, current_user)["modules"]
                if current_user
                else {
                    "dashboard": True,
                    "analytics": False,
                    "tpv": False,
                    "control_horario": False,
                    "crm": False,
                    "payroll": False,
                    "admin": False,
                    "settings": True,
                    "agents": True,
                }
            ),
            "timezone": "UTC",
            "date_range": {
                "start": (datetime.utcnow() - timedelta(days=30)).isoformat(),
                "end": datetime.utcnow().isoformat(),
                "days": 30
            }
        }

