"""J9a: control por modulos activos para ZEUS (acciones del orquestador y agentes destino).

REGISTRO ELEGIDO: `services.company_module_config` (MODULES_BY_COMPANY_TYPE + modules_for_company_type
+ get_company_config_for_user). Es el que realmente decide que modulos tiene una empresa: alimenta el
menu del frontend (`available_modules`) y `zeus_global_context.permissions`. `app.core.verticals_registry`
solo contiene la vertical "insurance" (cerrada) y no cubre tpv/crm/analytics/control_horario/payroll.

SUPERUSUARIO (coherente con J5/require_module): `modules_for_company_type(is_superuser=True)` devuelve
todos los modulos activos, asi que el superusuario no queda bloqueado por modulo (sigue exigiendo auth,
THALOS y rol reales). Es el unico que puede usar THALOS (modulo "admin").

Sin mapeo claro (NO se inventa): `list_customers`, `create_customer`, `send_campaign`, `get_cashflow` y
`get_metrics` (clientes/campanas existen en ambas verticales; el ledger de caja es transversal)
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
    "analytics_summary": "analytics",
    "tpv_sales_summary": "tpv",
    "shift_status": "control_horario",
    # J9e: acciones de JUSTICIA expuestas en el chat (mismo criterio que EXECUTOR_ACTION_MODULE).
    "get_legal_status": "agents",
    "run_compliance_audit": "agents",
}
# Sin mapeo claro (decision de producto pendiente; quedan permitidas): clientes y campanas existen en
# hosteleria y oficina (send_campaign ya lo cubre el rol, J3b); el ledger de caja es transversal.
UNMAPPED_ACTIONS = frozenset(
    {"list_customers", "create_customer", "send_campaign", "get_cashflow", "get_metrics",
     # J9e: AFRODITA inventario/rutas sin modulo propio en el registro real (ver EXECUTOR_UNMAPPED_ACTIONS)
     "get_inventory_status", "create_ops_route", "create_inventory_movement"}
)

# J9c: acciones del EJECUTOR de agentes (`zeus_agent_executor_v1._dispatch`) -> modulo requerido.
# Todas las acciones del ejecutor pasan por `check_executor_action`; las que no estan aqui estan
# en EXECUTOR_UNMAPPED_ACTIONS (permitidas, decision documentada). Criterios:
# - track_leads: CrmLead es el modulo CRM -> "crm".
# - get_shift_status (AFRODITA): fichajes/turnos -> "control_horario".
# - JUSTICIA (auditoria/estado legal): trabaja sobre documentos y eventos de cumplimiento de todos
#   los agentes, no sobre un modulo de menu -> "agents" (activo en toda empresa; deja la puerta
#   a desactivarlo por empresa sin tocar el ejecutor).
EXECUTOR_ACTION_MODULE: Dict[str, str] = {
    "track_leads": "crm",
    "get_shift_status": "control_horario",
    "run_compliance_audit": "agents",
    "get_legal_status": "agents",
}
# Sin mapeo claro (permitidas): clientes/campanas existen en hosteleria y oficina (el rol ya las
# gobierna, J3b); caja/metricas son transversales; RAFAEL (facturas, 303, resumen fiscal) vive en
# "payments" solo en oficina pero la facturacion aplica a ambas verticales; AFRODITA inventario y
# rutas (ERP/TPV/logistica) no tienen un modulo propio en el registro real (company_module_config).
EXECUTOR_UNMAPPED_ACTIONS = frozenset(
    {
        "create_customer", "get_customers", "list_customers", "send_campaign", "launch_campaign",
        "create_campaign", "get_cashflow", "get_metrics",
        "generate_invoice", "generate_model_303", "get_tax_summary",
        "get_inventory_status", "create_inventory_movement", "create_ops_route",
    }
)

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
    if msg and module == "admin":
        msg = "THALOS (seguridad) solo está disponible para administradores de la plataforma."
    return {"module": module, "message": msg} if msg else None


def check_executor_action(db: Session, user: User, action: str) -> Optional[Dict[str, Any]]:
    """J9c: None si permitido; {module, message} si la empresa no tiene el modulo de la accion
    del ejecutor. Accion sin mapeo -> permitida (ver EXECUTOR_UNMAPPED_ACTIONS). Fail-closed ante
    error al resolver los modulos (check_module)."""
    module = EXECUTOR_ACTION_MODULE.get((action or "").strip().lower())
    msg = check_module(db, user, module)
    return {"module": module, "message": msg} if msg else None
