"""
🤝 AFRODITA Automation Handler
Genera playbooks de soporte y onboarding.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Any

from app.models.agent_activity import AgentActivity
from .. import utils


def _support_schedule() -> Dict[str, Any]:
    start = datetime.utcnow().date()
    return {
        "week_1": {
            "theme": "Activación y primeros pasos",
            "touchpoints": [
                {"day": start.isoformat(), "channel": "WhatsApp", "goal": "Confirmar acceso al dashboard"},
                {"day": (start + timedelta(days=2)).isoformat(), "channel": "Email", "goal": "Enviar manual de uso"},
            ],
        },
        "week_2": {
            "theme": "Escalamiento y optimización",
            "touchpoints": [
                {"day": (start + timedelta(days=7)).isoformat(), "channel": "Video call", "goal": "Revisión de métricas"},
                {"day": (start + timedelta(days=10)).isoformat(), "channel": "WhatsApp", "goal": "Checklist de seguridad"},
            ],
        },
    }


def _onboarding_manual() -> Dict[str, Any]:
    return {
        "modules": [
            {"title": "Bienvenida a ZEUS IA", "content": ["Tour por el dashboard", "Identidad de los agentes"]},
            {"title": "Configuraciones críticas", "content": ["Stripe", "Google Workspace", "Hacienda"]},
            {"title": "Operación diaria", "content": ["Revisar panel de métricas", "Aprobar decisiones HITL"]},
        ],
        "resources": [
            "Video demo 5 minutos",
            "FAQ soporte primario",
            "Plantilla de toma de requisitos para nuevos clientes",
        ],
    }


def _coordination_notes() -> Dict[str, Any]:
    return {
        "meetings": [
            {"frequency": "Semanal", "participants": ["AFRODITA", "RAFAEL", "THALOS"], "objective": "Revisión estado operaciones"},
            {"frequency": "Mensual", "participants": ["ZEUS CORE", "Stakeholders"], "objective": "Roadmap y KPIs"},
        ],
        "alerts": [
            "Escalar incidencias críticas a THALOS en menos de 15 minutos.",
            "Notificar cambios fiscales a RAFAEL inmediatamente.",
        ],
    }


def handle_afrodita_task(activity: AgentActivity) -> Dict[str, Any]:
    agent = activity.agent_name.upper()
    prefix = f"{activity.id}_{activity.action_type}"

    deliverable = {
        "support_schedule": _support_schedule(),
        "onboarding_manual": _onboarding_manual(),
        "coordination_notes": _coordination_notes(),
        "summary": "Playbook de soporte y onboarding generado para las primeras cuatro semanas.",
    }

    json_path = utils.write_json(agent, prefix, deliverable)
    markdown = utils.summarize_markdown(
        "Playbook de Soporte ZEUS IA",
        {
            "Resumen": deliverable["summary"],
            "Agenda de contacto": [
                "Semana 1: activación y envío de manual.",
                "Semana 2: revisión de métricas y checklist.",
            ],
            "Recursos": deliverable["onboarding_manual"]["resources"],
            "Coordinaciones": [
                "Reunión semanal inter-agentes.",
                "Escalamiento inmediato ante incidencias.",
            ],
        },
    )
    markdown_path = utils.write_markdown(agent, prefix, markdown)

    return {
        "status": "completed",
        "details_update": {
            "automation": {
                "deliverables": {"json": json_path, "markdown": markdown_path},
                "summary": deliverable["summary"],
            }
        },
        "metrics_update": {"playbooks_generated": 1},
        "notes": f"Playbook de soporte disponible en {json_path}",
    }

