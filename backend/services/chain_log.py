"""J7: registro de la cadena JARVIS en agent_activities (sin tabla nueva).

Cadena: ESCUCHAR, COMPRENDER, CONTEXTO, ORQUESTAR, ACTUAR, AUDITAR, RESPONDER, CONTINUAR.
Cada paso deja una fila en `agent_activities` con empresa y usuario EXPLICITOS (nunca
inferidos por email), estado real y un `correlation_id` por peticion, guardado en
`details["correlation_id"]` junto a `details["chain_step"]` (sin migracion).

El correlation_id se genera en el servidor al entrar al chat (`begin_chain`) y se propaga por
un ContextVar: viaja a `asyncio.to_thread` (copia de contexto) y a las funciones del orquestador
sin cambiar sus firmas. Las filas de THALOS/aprobaciones (J2/J3b/J5) lo recogen del mismo sitio.

Un fallo del logger nunca tumba la peticion, pero se registra con logger.exception/error y, para
los pasos ACTUAR y AUDITAR, se acumula como advertencia que el chat devuelve en la respuesta.

Privacidad: ver `summarize_text` (el texto del usuario nunca se guarda completo aqui)."""

from __future__ import annotations

import logging
import re
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

STEPS = ("ESCUCHAR", "COMPRENDER", "CONTEXTO", "ORQUESTAR", "ACTUAR", "AUDITAR", "RESPONDER", "CONTINUAR")
# Pasos cuyo fallo de registro no puede ocultarse al usuario.
CRITICAL_STEPS = frozenset({"ACTUAR", "AUDITAR"})
ALLOWED_CHANNELS = frozenset({"text", "voice"})
PREVIEW_MAX = 60

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_NUM_RE = re.compile(r"\d[\d\s().-]{4,}\d")


@dataclass
class ChainContext:
    correlation_id: str
    warnings: List[str] = field(default_factory=list)


_current: ContextVar[Optional[ChainContext]] = ContextVar("zeus_chain_ctx", default=None)


def begin_chain() -> tuple:
    """Abre la cadena de una peticion: genera el correlation_id en servidor. -> (ctx, token)."""
    ctx = ChainContext(correlation_id=uuid.uuid4().hex)
    return ctx, _current.set(ctx)


def end_chain(token) -> None:
    _current.reset(token)


def current_chain() -> Optional[ChainContext]:
    return _current.get()


def current_correlation_id() -> Optional[str]:
    c = _current.get()
    return c.correlation_id if c else None


CHAIN_ACTION_PREFIX = "chain_"
SUCCESS_STATUSES = ("completed", "success")


def is_chain_step(activity: Any) -> bool:
    """True para las filas internas de la cadena (action_type chain_*): son trazas de auditoria,
    no actividades de negocio, y no deben contar en metricas/uptime."""
    return str(getattr(activity, "action_type", "") or "").startswith(CHAIN_ACTION_PREFIX)


def business_activities(activities: Any) -> list:
    """Actividades sin las filas internas de la cadena (para metricas, uptime y success_rate)."""
    return [a for a in activities if not is_chain_step(a)]


def exclude_chain_steps(query: Any) -> Any:
    """Filtro SQL equivalente a `business_activities` para una query de AgentActivity."""
    from app.models.agent_activity import AgentActivity

    return query.filter(AgentActivity.action_type.notlike(r"chain\_%", escape="\\"))


def is_success_status(status: Any) -> bool:
    return status in SUCCESS_STATUSES


def summarize_text(text: Optional[str]) -> str:
    """Resumen truncado y enmascarado del texto del usuario: emails -> [email], secuencias
    numericas largas (telefonos, DNI, tarjetas) -> [num], maximo PREVIEW_MAX caracteres.
    LIMITE CONOCIDO: nombres propios y direcciones en texto libre NO se enmascaran; por eso el
    resumen es corto (60 caracteres) y el texto completo nunca se guarda en la cadena."""
    t = " ".join((text or "").split())
    t = _EMAIL_RE.sub("[email]", t)
    t = _NUM_RE.sub("[num]", t)
    return t[:PREVIEW_MAX] + ("..." if len(t) > PREVIEW_MAX else "")


def normalize_channel(value: Any) -> str:
    v = str(value or "").strip().lower()
    return v if v in ALLOWED_CHANNELS else "text"


def log_chain_step(
    step: str,
    *,
    company_id: Optional[int],
    user: Any,
    agent: str,
    action: str,
    status: str,
    details: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
    description: Optional[str] = None,
    action_type: Optional[str] = None,
    priority: str = "normal",
    visible_to_client: bool = False,
) -> bool:
    """Registra un paso de la cadena. Devuelve True si la fila quedo persistida.

    company_id y user son explicitos: sin inferencia por email. `status` es el resultado real
    (success, failed, needs_confirmation, rejected, audit_failed, ...). Nunca lanza."""
    step_u = (step or "").upper()
    ctx = _current.get()
    cid = correlation_id or (ctx.correlation_id if ctx else None)
    body: Dict[str, Any] = dict(details or {})
    body["chain_step"] = step_u
    body["action"] = action
    if cid:
        body["correlation_id"] = cid
    uid = getattr(user, "id", None)
    if uid is not None:
        body.setdefault("user_id", uid)
    ok = False
    try:
        from services.activity_logger import ActivityLogger

        row = ActivityLogger.log_activity(
            agent_name=agent,
            action_type=action_type or f"chain_{step_u.lower()}",
            action_description=description or f"[{step_u}] {action}",
            details=body,
            user_email=getattr(user, "email", None),
            status=status,
            priority=priority,
            visible_to_client=visible_to_client,
            company_id=company_id,
            infer_company=False,
        )
        ok = row is not None
    except Exception:
        logger.exception("chain_log: excepcion registrando paso %s (%s)", step_u, action)
    if not ok:
        logger.error("chain_log: paso %s (%s) NO registrado correlation=%s", step_u, action, cid)
        if step_u in CRITICAL_STEPS and ctx is not None:
            ctx.warnings.append(
                f"No se pudo registrar el paso {step_u} ({action}) en el registro de actividad."
            )
    return ok
