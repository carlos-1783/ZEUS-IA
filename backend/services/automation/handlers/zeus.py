"""
⚡ ZEUS CORE Automation Handler
Genera informes de coordinación y seguimiento.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any

from app.models.agent_activity import AgentActivity
from .. import utils


def _coordination_report(activity: AgentActivity) -> Dict[str, Any]:
    now = datetime.utcnow().isoformat()
    details = activity.details or {}
    return {
        "generated_at": now,
        "phase": details.get("phase", "pre-launch"),
        "timeline": details.get("timeline"),
        "reporting": details.get("reporting"),
        "summary": [
            "Plan maestro activo.",
            "Tareas delegadas a agentes secundarios en curso.",
            "No se detectan bloqueos críticos en automatización.",
        ],
    }


def handle_zeus_task(activity: AgentActivity) -> Dict[str, Any]:
    agent = activity.agent_name.upper()
    prefix = f"{activity.id}_{activity.action_type}"

    deliverable = _coordination_report(activity)
    json_path = utils.write_json(agent, prefix, deliverable)
    markdown = utils.summarize_markdown(
        "Informe ZEUS CORE",
        {
            "Resumen": deliverable["summary"],
            "Fase": deliverable.get("phase"),
            "Estado de líneas de trabajo": [
                "Marketing y ventas coordinadas con PERSEO.",
                "Fiscalidad bajo control con RAFAEL.",
                "Seguridad monitorizada por THALOS.",
                "Legal listo con JUSTICIA.",
            ],
        },
    )
    markdown_path = utils.write_markdown(agent, prefix, markdown)

    return {
        "status": "completed",
        "details_update": {
            "automation": {
                "deliverables": {"json": json_path, "markdown": markdown_path},
                "summary": "Informe maestro de coordinación actualizado.",
            }
        },
        "metrics_update": {"coordination_reports": 1},
        "notes": f"Informe de coordinación generado. Archivos en {json_path}",
    }

