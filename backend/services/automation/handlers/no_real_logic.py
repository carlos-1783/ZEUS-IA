"""
Handler explicito para tareas genericas sin logica real.

Fase 2 / Step 2 (sin simulacion): PERSEO, RAFAEL y AFRODITA respondian a "task_assigned"
con entregables fijos (campana "Lanzamiento ZEUS IA", proyeccion de tesoreria con cifras
inventadas, playbook de soporte...) identicos para cualquier empresa, y marcaban la tarea
como completada. Ahora la tarea queda bloqueada y el motivo se dice claramente.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.models.agent_activity import AgentActivity

logger = logging.getLogger(__name__)

HANDLER_NAME = "no_real_logic"


def handle_no_real_logic(activity: AgentActivity) -> Dict[str, Any]:
    agent = (activity.agent_name or "").upper()
    action = activity.action_type or ""
    msg = (
        f"{agent} no tiene logica real para la tarea generica '{action}' "
        f"({(activity.action_description or '')[:160]}). No se ha generado ningun entregable; "
        "pidelo por el chat del agente con una accion concreta."
    )
    logger.info("[AUTOMATION] %s/%s sin logica real: actividad %s no ejecutada", agent, action, activity.id)
    return {
        "status": "blocked_missing_handler",
        "details_update": {"real_execution": False, "executed": False, "reason": "no_real_logic", "message": msg},
        "notes": msg,
        "executed_handler": HANDLER_NAME,
    }
