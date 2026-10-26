"""Contexto operativo compartido por ZEUS Core y todos los handlers del orquestador."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.employee_work_session import EmployeeWorkSession
from app.models.user import User
from services.company_module_config import get_company_config_for_user
import services.crm_office_service as crm_svc

logger = logging.getLogger(__name__)

# Clave del bloque «actividad de hoy» dentro de `zeus_global_context` (solo charla LLM de ZEUS CORE).
TODAY_ACTIVITY_KEY = "today_activity"
# Clave del proveedor perezoso en el contexto. Prefijo `_`: nunca llega al prompt (base_agent) y el
# cliente no puede imponerla (build_server_context descarta las claves `_` del cliente).
TODAY_ACTIVITY_PROVIDER_KEY = "_today_activity_provider"
TODAY_ACTIVITY_RULE = ("Son las cifras reales de hoy leídas de la base de datos; úsalas tal cual y no "
                       "inventes otras.")


def build_global_context(db: Session, user: User) -> Dict[str, Any]:
    company_id = crm_svc.primary_company_id(db, user)
    cfg = get_company_config_for_user(db, user)
    customers = crm_svc.list_customers(db, user)
    with_email = sum(1 for c in customers if c.email and str(c.email).strip())

    active_session: Optional[Dict[str, Any]] = None
    ws = (
        db.query(EmployeeWorkSession)
        .filter(
            EmployeeWorkSession.user_id == user.id,
            EmployeeWorkSession.status == "active",
        )
        .order_by(EmployeeWorkSession.id.desc())
        .first()
    )
    if ws:
        active_session = {
            "id": ws.id,
            "employee_code": ws.employee_code,
            "status": ws.status,
            "opened_at": ws.opened_at.isoformat() if ws.opened_at else None,
            "company_id": ws.company_id,
        }

    return {
        "company_id": company_id,
        "user_id": user.id,
        "active_customers": {
            "total": len(customers),
            "with_email": with_email,
        },
        "active_session": active_session,
        "permissions": cfg.get("modules") or {},
        "company_type": cfg.get("company_type"),
        "company_name": cfg.get("company_name"),
    }


def build_agent_company_context(db: Session, user: User) -> Dict[str, Any]:
    """J9a: contexto de servidor para agentes que no son ZEUS CORE: empresa, tipo y modulos activos.
    Sin datos personales (ni clientes, ni sesiones, ni identificadores de usuario)."""
    cfg = get_company_config_for_user(db, user)
    modules = cfg.get("modules") or {}
    return {
        "company_name": cfg.get("company_name"),
        "company_type": cfg.get("company_type"),
        "active_modules": sorted(k for k, v in modules.items() if v),
    }


def build_today_activity(
    db: Session, company_id: Optional[int], modules: Dict[str, Any]
) -> Tuple[str, Dict[str, Any]]:
    """Actividad de HOY (dia local Europe/Madrid) de la empresa, en una linea compacta para el modelo.

    Reutiliza las lecturas reales de RAFAEL (`rafael_daily_reads_v1.daily_close_summary`: ventas TPV
    del dia + arqueo de `tpv_cash_closures`; `invoices_day_summary`: facturas emitidas hoy) y su mismo
    texto de chat (`jarvis_ops_actions._format_read`). Ambito: SOLO `company_id` (resuelto en servidor).
    Sin ventas lo dice con un 0 explicito; si la lectura falla lo dice (nunca un 0 falso).
    Devuelve (texto para el prompt, cardinalidades para el registro de la cadena)."""
    from services import rafael_daily_reads_v1 as rafael_reads
    from services.jarvis_ops_actions import _eur, _format_read
    from services.local_day_v1 import today_local
    from services.module_gate import blocked_message

    if company_id is None:
        return ("Actividad de hoy: no disponible (tu usuario no tiene empresa asociada); no des cifras "
                "de hoy.", {"available": False, "reason": "no_company"})
    day = today_local()
    try:
        inv = rafael_reads.invoices_day_summary(db, company_id, day, top=5)
        if modules.get("tpv"):
            close = rafael_reads.daily_close_summary(db, company_id, day)
            head = f"{close['tickets']} ventas TPV ({_eur(close['total'])})"
            tpv_txt = _format_read("get_daily_close", {"data": close})
            stats = {"tickets": close["tickets"], "cash_closures": len(close["cash_closures"])}
        else:
            head, tpv_txt = "ventas TPV: sin módulo TPV", blocked_message("tpv")
            stats = {"tickets": None, "cash_closures": None}
    except Exception:
        logger.exception("zeus_global_context: no se pudo leer la actividad de hoy (empresa %s)", company_id)
        try:
            db.rollback()
        except Exception:
            logger.exception("zeus_global_context: rollback fallido tras error de lectura")
        return ("Actividad de hoy: no se ha podido leer ahora de la base de datos; no des cifras de hoy "
                "y dilo.", {"available": False, "reason": "read_error"})
    inv_txt = _format_read("get_invoices_today", {"data": inv})
    text = (f"Actividad de hoy {day.isoformat()} ({inv['timezone']}) de tu empresa: {head}, "
            f"{inv['count']} facturas emitidas ({_eur(inv['amount_total'])}). {tpv_txt} {inv_txt} "
            f"{TODAY_ACTIVITY_RULE}")
    stats.update({"available": True, "date": day.isoformat(), "invoices": inv["count"]})
    return text, stats


def make_today_activity_provider(user: User, context: Dict[str, Any]) -> Callable[[], str]:
    """Lectura PEREZOSA de la actividad de hoy: devuelve un callable que solo se evalua si contesta el
    PROPIO ZEUS (`ZeusCore._handle_directly`). Si ZEUS delega en otro agente o entra en pre-lanzamiento,
    no se lee nada ni se registra nada.

    La empresa sale del `zeus_global_context` ya construido en servidor (JWT -> BD), nunca del cliente.
    Se evalua en el hilo del runtime del agente: usa su PROPIA sesion de BD (la de la peticion no es
    segura entre hilos si el runtime vence por timeout) y registra el paso CONTEXTO/load_today_activity
    con la correlacion de la peticion en el momento en que se pasa al modelo."""
    from services.chain_log import current_correlation_id, log_chain_step

    gc = context.get("zeus_global_context") or {}
    company_id = gc.get("company_id")
    modules = dict(gc.get("permissions") or {})
    correlation_id = current_correlation_id()

    def provider() -> str:
        from app.db.rls_context import open_tenant_session

        # Hilo propio: sesion con el contexto RLS de la empresa del contexto global (servidor).
        db = open_tenant_session(company_id, user_id=getattr(user, "id", None))
        try:
            text, stats = build_today_activity(db, company_id, modules)
        finally:
            db.close()
        log_chain_step(
            "CONTEXTO", company_id=company_id, user=user, agent="ZEUS CORE",
            action="load_today_activity", status="success" if stats.get("available") else "failed",
            details={"today_activity": stats}, correlation_id=correlation_id,
        )
        return text

    return provider


def enrich_chat_context(
    db: Session,
    user: User,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    ctx = dict(context or {})
    gc = build_global_context(db, user)
    # H-01 (ZEUS_JARVIS_INTERACTION_AUDIT.md): la empresa y el usuario los fija SIEMPRE el
    # servidor (JWT -> BD). Un `company_id` enviado por el cliente nunca prevalece: antes se
    # usaba como clave del pending de ZEUS y de la memoria, lo que permitía actuar sobre el
    # estado de otra empresa.
    ctx["company_id"] = gc.get("company_id")
    ctx["user_id"] = user.id
    ctx["zeus_global_context"] = gc
    return ctx


def attach_context_to_action_payload(
    action_payload: Dict[str, Any],
    global_context: Dict[str, Any],
) -> Dict[str, Any]:
    out = dict(action_payload)
    out["_zeus_context"] = global_context
    return out
