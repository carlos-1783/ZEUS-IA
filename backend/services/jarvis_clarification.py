"""J8 — Estado de aclaracion del hilo JARVIS.

Cuando ZEUS pregunta (faltan datos o hay ambiguedad) guarda en la memoria operativa escopada
(AgentOperationalState de ZEUS CORE, clave de hilo atada al usuario, igual que el pending de
aprobacion) lo que ya entendio. La siguiente respuesta del MISMO usuario en el MISMO hilo y
empresa puede completar el dato; si no lo completa se descarta el estado y el mensaje se trata
como una peticion nueva.

LIMITES (documentados): el estado dura CLARIFICATION_TTL_SECONDS (15 min) y guarda como maximo el
mensaje original truncado (300 caracteres) y los datos ya extraidos (nombre/email/descuento) del
propio usuario; se borra al resolverse, abandonarse o cancelarse. La aclaracion solo completa
datos de UNA accion; no encadena varias preguntas de intenciones distintas.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from app.schemas.zeus_task import ZeusTaskObject
from services.agent_memory_service import load as memory_load, persist_operational_state
from services.intent_parser import (
    _default_offer_message,
    _extract_campaign_name,
    extract_entities,
    fold,
    parse_intent,
    question_for_customer,
)

logger = logging.getLogger(__name__)

AGENT = "ZEUS CORE"
KEY = "pending_clarification"
CLARIFICATION_TTL_SECONDS = 15 * 60
MIN_CONFIDENCE_RESUME = 0.7

# Respuestas que aceptan la propuesta «¿la envío a todos?»
_YES_RE = re.compile(
    r"^\s*(si|vale|ok|okey|dale|claro|de acuerdo|adelante|confirmo|confirmar|hazlo|perfecto)\b[\s,.!]*"
    r"(a\s+todos|a\s+todos\s+mis\s+clientes)?[\s.!]*$"
)
_ALL_RE = re.compile(r"\b(todos|todas|todos\s+mis\s+clientes|a\s+los\s+clientes|crm|toda\s+la\s+base)\b")

# Pista por intencion para elegir entre opciones ambiguas.
_FAMILY_HINTS = {
    "get_cashflow": r"\b(caja|tesoreria|cashflow|flujo|saldo|balance)\b",
    "tpv_sales_today": r"\b(ventas?|tpv|vendido|tickets?|facturad\w+)\b",
    "tpv_sales_summary": r"\b(ventas?|tpv|vendido|tickets?|facturad\w+)\b",
    "get_metrics": r"\b(metricas?|ingresos?|margen|costes?|revenue)\b",
    "list_customers_summary": r"\b(clientes|cuantos)\b",
    "analytics_summary": r"\b(actividad|analytics|estadisticas?)\b",
    "shift_status": r"\b(turno|fichaje|jornada)\b",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _artifacts(company_key: str, thread_key: str) -> Dict[str, Any]:
    mem = memory_load(company_key, AGENT, thread_key)
    return dict((mem.get("operational") or {}).get("artifacts") or {})


def save_state(company_key: str, thread_key: str, task: ZeusTaskObject) -> None:
    """Guarda lo ya entendido para completarlo con la siguiente respuesta del usuario."""
    ambiguity = bool(task.ambiguous_with)
    state = {
        "intent": task.intent,
        "kind": "ambiguity" if ambiguity else "missing",
        "options": [task.intent] + list(task.ambiguous_with) if ambiguity else [],
        "missing": list(task.missing_entities),
        "slots": {
            "name": (task.metadata or {}).get("name"),
            "email": (task.metadata or {}).get("email"),
            "phone": (task.metadata or {}).get("phone"),
            "discount_percent": task.discount_percent,
        },
        "original": (task.raw_message or "")[:300],
        "urgency": task.urgency,
        "asked_at": _now().isoformat(),
    }
    arts = _artifacts(company_key, thread_key)
    arts[KEY] = state
    persist_operational_state(company_key, AGENT, thread_key, artifacts=arts)


def clear_state(company_key: str, thread_key: str) -> None:
    arts = _artifacts(company_key, thread_key)
    if KEY in arts:
        arts.pop(KEY)
        persist_operational_state(company_key, AGENT, thread_key, artifacts=arts)


def load_state(company_key: str, thread_key: str) -> Optional[Dict[str, Any]]:
    state = _artifacts(company_key, thread_key).get(KEY)
    if not isinstance(state, dict):
        return None
    try:
        asked = datetime.fromisoformat(state["asked_at"])
        if asked.tzinfo is None:
            asked = asked.replace(tzinfo=timezone.utc)
    except Exception:
        return None
    if _now() - asked > timedelta(seconds=CLARIFICATION_TTL_SECONDS):
        return None
    return state


def _is_new_command(reply: str, exclude_intent: str) -> bool:
    t = parse_intent(reply)
    return t.intent not in ("unknown", exclude_intent) and t.confidence >= MIN_CONFIDENCE_RESUME


def _resume_customer(state: Dict[str, Any], reply: str) -> Optional[ZeusTaskObject]:
    slots = state.get("slots") or {}
    name, email, phone = slots.get("name"), slots.get("email"), slots.get("phone")
    ent = extract_entities(reply)
    new_email = ent.emails[0] if ent.emails else None
    new_name = None
    if not name:
        if ent.names:
            new_name = ent.names[0]
        elif not _is_new_command(reply, "create_customer"):
            # Respuesta corta tipo «Ana López» (con o sin email): lo que queda sin el email y sin relleno.
            rest = re.sub(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.\w{2,}", " ", reply)
            rest = re.sub(r"\b(con|el|su|email|correo|mail|es|se\s+llama|llamado|de|y)\b", " ", rest, flags=re.I)
            rest = " ".join(re.sub(r"[,;:]", " ", rest).split())
            toks = rest.split()
            if 1 <= len(toks) <= 5 and all(re.fullmatch(r"[A-Za-zÀ-ÿ'.-]{2,}", t) for t in toks) \
                    and parse_intent(reply).intent == "unknown":
                new_name = rest
    if not new_email and not new_name:
        return None
    name, email = new_name or name, new_email or email
    if not phone and ent.phones:
        phone = ent.phones[0]
    meta: Dict[str, Any] = {"name": name, "email": email}
    if phone:
        meta["phone"] = phone
    missing = [k for k, v in (("name", name), ("email", email)) if not v]
    task = ZeusTaskObject(
        intent="create_customer", action="create_customer", raw_message=reply, confidence=0.9,
        metadata=meta, entities=ent, urgency=state.get("urgency") or "normal",
        missing_entities=missing,
        confidence_breakdown={"rule": "clarification_completed", "base": 0.9},
    )
    if missing:
        task.needs_clarification = True
        task.clarification_question = question_for_customer(name, email)
    return task


def _resume_campaign(state: Dict[str, Any], reply: str) -> Optional[ZeusTaskObject]:
    f = fold(reply)
    if not (_YES_RE.match(f) or _ALL_RE.search(f)):
        return None
    if _is_new_command(reply, "create_campaign_send"):
        return None
    discount = (state.get("slots") or {}).get("discount_percent")
    return ZeusTaskObject(
        intent="create_campaign_send", action="create_campaign", discount_percent=discount,
        target="all_customers", campaign_name=_extract_campaign_name(state.get("original") or "", discount),
        message_template=_default_offer_message(discount), requires_confirmation=True,
        raw_message=reply, confidence=0.9, entities=extract_entities(reply),
        urgency=state.get("urgency") or "normal",
        confidence_breakdown={"rule": "clarification_completed", "base": 0.9},
    )


def _resume_ambiguity(state: Dict[str, Any], reply: str) -> Optional[ZeusTaskObject]:
    f = fold(reply)
    chosen = [i for i in state.get("options") or [] if i in _FAMILY_HINTS and re.search(_FAMILY_HINTS[i], f)]
    # tpv_sales_today y tpv_sales_summary comparten pista: cuentan como una sola familia.
    fam = {("tpv" if i.startswith("tpv") else i) for i in chosen}
    if len(fam) != 1:
        return None
    intent = chosen[0]
    task = parse_intent(state.get("original") or "", force_intent=intent)
    if task.intent == "unknown" or task.needs_clarification:
        return None
    task.confidence_breakdown = {**task.confidence_breakdown, "rule": "clarification_ambiguity_resolved"}
    return task


def resolve_reply(state: Dict[str, Any], reply: str) -> Optional[ZeusTaskObject]:
    """Tarea completada con la respuesta del usuario, o None si la respuesta no completa el dato
    (se trata como mensaje nuevo)."""
    try:
        if state.get("kind") == "ambiguity":
            return _resume_ambiguity(state, reply)
        intent = state.get("intent")
        if intent == "create_customer":
            return _resume_customer(state, reply)
        if intent == "create_campaign_send":
            return _resume_campaign(state, reply)
    except Exception:
        logger.exception("jarvis_clarification: fallo al resolver la respuesta; se trata como mensaje nuevo")
    return None
