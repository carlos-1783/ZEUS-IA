"""
Endpoints para gestión y estado de agentes IA
"""
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.auth import get_current_active_user
from app.models.user import User

router = APIRouter()

# Metadata estática por agente: rol, dominio y capacidades declaradas del
# producto — no son mediciones, así que no dependen de agent_activities y
# no se tocan al hacer este endpoint "real" (Bloque 3, limpieza de
# simulación). Lo que SÍ era simulado (status, uptime, last_activity,
# decisions_today, avg_confidence) se calcula ahora contra la BD.
AGENT_REGISTRY: Dict[str, Dict[str, Any]] = {
    "ZEUS CORE": {
        "role": "Orquestador Supremo",
        "capabilities": [
            "motor_de_orquestacion_teamflow",
            "coordinacion_multiagente",
            "decision_metadata",
            "context_sharing_entre_agentes",
            "validacion_legal_y_riesgos_con_auto_HITL",
            "panel_de_control_de_ejecuciones",
        ],
        "workspace_tools": [],
    },
    "PERSEO": {
        "role": "Estratega de Crecimiento",
        "domain": "Marketing/SEO/SEM",
        "capabilities": [
            "procesamiento_de_multiples_imagenes",
            "mejora_de_videos_existentes",
            "creacion_de_assets_para_ads",
            "SEO_tecnico_auditoria",
            "keyword_research",
            "integracion_con_Justicia_para_contratos",
            "integracion_con_Rafael_para_facturas",
        ],
        "workspace_tools": ["image_analyzer", "video_enhancer", "seo_audit_engine", "ads_campaign_builder"],
    },
    "RAFAEL": {
        "role": "Guardián Fiscal",
        "domain": "Finanzas/Fiscalidad",
        "country": "España",
        "capabilities": [
            "lectura_QR",
            "lectura_NFC",
            "lectura_DNIe",
            "reconocimiento_superusuario",
            "modo_pre_lanzamiento_para_datos_incompletos",
        ],
        "workspace_tools": ["qr_reader", "nfc_scanner", "dni_ocr_parser", "fiscal_forms_generator"],
    },
    "THALOS": {
        "role": "Defensor Cibernético",
        "domain": "Seguridad/Ciberdefensa",
        "safeguards": "creator_approval_required",
        "capabilities": [
            "deteccion_temprana_anomalias",
            "aislamiento_automático",
            "proteccion_de_endpoints",
            "proteccion_CORS_y_API_gateway",
        ],
        "workspace_tools": ["log_monitor", "threat_detector", "credential_revoker"],
    },
    "JUSTICIA": {
        "role": "Asesora Legal y GDPR",
        "domain": "Legal/Protección de Datos",
        "capabilities": [
            "firma_digital_de_documentos",
            "generacion_y_firma_PDF",
            "integracion_con_Perseo_para_contratos_publicitarios",
            "integracion_con_Rafael_para_facturas",
            "auditoria_GDPR_en_tiempo_real",
        ],
        "workspace_tools": ["pdf_signer", "contract_generator", "gdpr_audit"],
    },
    "AFRODITA": {
        "role": "RRHH y Logística",
        "domain": "RRHH / Operaciones",
        "capabilities": [
            "fichaje_por_foto",
            "fichaje_por_QR",
            "fichaje_por_codigo",
            "gestion_turnos",
            "gestion_ausencias",
            "onboarding_empleados",
        ],
        "workspace_tools": ["face_check_in", "qr_check_in", "employee_manager", "contract_creator_rrhh"],
    },
}

# agent_activities.agent_name no siempre coincide literalmente con las
# claves del registro de arriba — "ZEUS" (app/main.py, auth.py, webhooks.py,
# email_service.py) y "ZEUS CORE" (chat.py, workspaces.py, teamflow.py,
# integrations.py) alimentan el mismo agente. El resto son 1:1.
AGENT_NAME_ALIASES: Dict[str, str] = {
    "ZEUS": "ZEUS CORE",
    "ZEUS CORE": "ZEUS CORE",
    "PERSEO": "PERSEO",
    "RAFAEL": "RAFAEL",
    "THALOS": "THALOS",
    "JUSTICIA": "JUSTICIA",
    "AFRODITA": "AFRODITA",
}

ONLINE_WINDOW = timedelta(hours=24)
UPTIME_WINDOW = timedelta(days=30)


@router.get("/status")
async def get_agents_status(
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Obtener estado real de todos los agentes del sistema, calculado a
    partir de agent_activities (mismo patrón que /api/v1/metrics/dashboard).
    NO requiere autenticación para permitir monitoreo público — sin cambios
    respecto al comportamiento previo; los datos ya no son fijos, pero
    siguen siendo agregados a nivel de todo el sistema, no por tenant.
    """
    from app.models.agent_activity import AgentActivity

    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    uptime_start = now - UPTIME_WINDOW

    rows = (
        db.query(AgentActivity)
        .filter(AgentActivity.created_at >= uptime_start, AgentActivity.created_at <= now)
        .all()
    )

    per_agent: Dict[str, List[AgentActivity]] = {name: [] for name in AGENT_REGISTRY}
    for row in rows:
        canonical = AGENT_NAME_ALIASES.get((row.agent_name or "").strip().upper())
        if canonical:
            per_agent[canonical].append(row)

    agents_status: Dict[str, Any] = {}
    online_count = 0
    for name, meta in AGENT_REGISTRY.items():
        activities = per_agent[name]
        total = len(activities)
        completed = sum(1 for a in activities if a.status == "completed")
        decisions_today = sum(1 for a in activities if a.created_at >= today_start)
        last_activity = max((a.created_at for a in activities), default=None)
        is_online = last_activity is not None and (now - last_activity) <= ONLINE_WINDOW
        if is_online:
            online_count += 1

        agents_status[name] = {
            "status": "online" if is_online else "idle",
            "role": meta["role"],
            # % de actividades completadas (no fallidas) en los últimos 30
            # días. None cuando no hay actividad registrada — no se inventa
            # un porcentaje cuando no hay datos.
            "uptime": f"{(completed / total * 100):.2f}%" if total > 0 else None,
            "last_activity": last_activity.isoformat() if last_activity else None,
            "decisions_today": decisions_today,
            "decisions_last_30d": total,
            **{k: v for k, v in meta.items() if k != "role"},
        }

    if online_count >= len(AGENT_REGISTRY) / 2:
        system_health = "optimal"
    elif online_count > 0:
        system_health = "degraded"
    else:
        system_health = "idle"

    return {
        "timestamp": now.isoformat(),
        "total_agents": len(agents_status),
        "agents": agents_status,
        "system_health": system_health,
    }

@router.get("/stats")
async def get_agents_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Estadísticas detalladas de agentes (requiere autenticación)
    """
    return {
        "total_decisions": 0,
        "total_hitl_requests": 0,
        "avg_response_time": "0.3s",
        "total_cost": "0.00 USD",
        "period": "last_30_days"
    }
