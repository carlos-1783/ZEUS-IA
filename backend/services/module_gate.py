"""J9a: control por modulos activos para ZEUS (acciones del orquestador y agentes destino).

REGISTRO ELEGIDO: `services.company_module_config` (MODULES_BY_COMPANY_TYPE + modules_for_company_type
+ get_company_config_for_user). Es el que realmente decide que modulos tiene una empresa: alimenta el
menu del frontend (`available_modules`) y `zeus_global_context.permissions`. `app.core.verticals_registry`
solo contiene la vertical "insurance" (cerrada) y no cubre tpv/crm/analytics/control_horario/payroll.

SUPERUSUARIO (coherente con J5/require_module): `modules_for_company_type(is_superuser=True)` devuelve
todos los modulos activos, asi que el superusuario no queda bloqueado por modulo (sigue exigiendo auth,
THALOS y rol reales). Es el unico que puede usar THALOS (modulo "admin").

Sin mapeo claro (NO se inventa): acciones `get_cashflow` y `get_metrics` (el ledger de caja es transversal)
y las acciones del ejecutor de agentes que no pasan por execute_action. Quedan permitidas.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.user import User
from services.company_module_config import get_company_config_for_user

logger = logging.getLogger(__name__)

MODULE_LABELS: Dict[str, str] = {
    "crm": "CRM",
    "tpv": "TPV",
    "analytics": "Analítica",
    "control_horario": "Control horario",
    "payroll": "Nóminas",
    "agents": "Agentes",
    "admin": "Administración",
}

# accion de execute_action -> modulo requerido
ACTION_MODULE: Dict[str, str] = {
    "list_customers": "crm",
    "create_customer": "crm",
    "send_campaign": "crm",  # los destinatarios salen de los clientes del CRM
    "analytics_summary": "analytics",
    "tpv_sales_summary": "tpv",
    "shift_status": "control_horario",
}
UNMAPPED_ACTIONS = frozenset({"get_cashflow", "get_metrics"})

# agente destino -> modulo requerido. "agents" esta activo para toda empresa (igual que el menu);
# THALOS exige "admin" (solo superusuario), igual que J4.
AGENT_MODULE: Dict[str, str] = {
    "ZEUS CORE": "agents",
    "PERSEO": "agents",
    "RAFAEL": "agents",
    "JUSTICIA": "agents",
    "AFRODITA": "agents",
    "THALOS": "admin",
}


def active_modules(db: Session, user: User) -> Dict[str, bool]:
    """Mapa modulo->activo de la empresa del usuario (servidor, mismo registro que el menu)."""
    return dict(get_company_config_for_user(db, user).get("modules") or {})


def blocked_message(module: str) -> str:
    return f"Tu empresa no tiene activo el módulo {MODULE_LABELS.get(module, module)}."


def check_module(db: Session, user: User, module: Optional[str]) -> Optional[str]:
    """None si permitido; mensaje claro si la empresa no tiene el modulo. Fail-closed ante error."""
    if not module:
        return None
    try:
        mods = active_modules(db, user)
    except Exception:
        logger.exception("module_gate: no se pudo resolver los modulos de la empresa")
        return "No se han podido comprobar los módulos de tu empresa; no he ejecutado nada."
    return None if mods.get(module) else blocked_message(module)


def check_action(db: Session, user: User, action_type: str) -> Optional[Dict[str, Any]]:
    """None si permitido; {module, message} si bloqueado."""
    module = ACTION_MODULE.get(action_type)
    msg = check_module(db, user, module)
    return {"module": module, "message": msg} if msg else None


def check_agent(db: Session, user: User, agent_name: str) -> Optional[Dict[str, Any]]:
    module = AGENT_MODULE.get((agent_name or "").upper())
    msg = check_module(db, user, module)
    return {"module": module, "message": msg} if msg else None
