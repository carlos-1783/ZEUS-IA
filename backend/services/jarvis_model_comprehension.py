"""J8b: comprension de JARVIS con MODELO para mensajes que pueden pedir acciones con consecuencias.

Reparto de responsabilidades (el modelo NUNCA decide nada de seguridad):
  - Reglas (intent_parser): puerta barata ("¿puede este mensaje pedir una accion con consecuencias?")
    y RED DE SEGURIDAD (criterio estricto J8) cuando el modelo no esta disponible.
  - Modelo: clasifica polaridad (affirm/negate/uncertain), tipo de accion (catalogo cerrado) y
    extrae entidades. Salida JSON validada con pydantic (extra=forbid); si no valida -> fallback.
  - Servidor: umbral de certeza, ambiguedad, varias acciones, VALIDACION de cada entidad (forma +
    presencia literal en el texto del usuario), empresa/usuario/rol/THALOS, vista previa y
    confirmacion humana (J3b). Esta capa solo produce un ZeusTaskObject o una respuesta directa; la
    ejecucion sigue exigiendo la aprobacion humana del orquestador, igual que antes.

DECISION (documentada):
  1. alguna accion `negate`                        -> "Entendido, no hago nada." (nada se prepara)
  2. needs_clarification / `uncertain` / certeza < umbral / entidades dudosas -> ZEUS pregunta
  3. varias acciones `affirm`                      -> ZEUS pregunta por cual empezar (no prepara
     ninguna: es lo mas seguro y coherente con el criterio multi-accion de J8)
  4. una accion `affirm` con certeza >= umbral y entidades validas y completas -> ZeusTaskObject
     que el orquestador convierte en vista previa + aprobacion exactamente como antes.
  5. sin acciones / `other_consequential` afirmativa -> se usa el criterio estricto (reglas).
FALLBACK al criterio estricto J8 (nunca se prepara nada por defecto): modelo no configurado, error,
timeout, salida invalida, tope de gasto, empresa desconocida, o fallo comprobando el tope.

VARIABLES DE ENTORNO (todas opcionales; se leen en cada llamada):
  JARVIS_MODEL_COMPREHENSION            "1" (defecto) / "0": interruptor. Sin OPENAI_API_KEY no hay modelo.
  JARVIS_CLASSIFIER_MODEL               modelo (defecto: OPENAI_MODEL).
  JARVIS_CLASSIFIER_TIMEOUT_SEC         defecto 6.
  JARVIS_CLASSIFIER_MIN_CERTAINTY       defecto 0.8 (acotado a [0.7, 1.0]).
  JARVIS_CLASSIFIER_CONFLICT_CERTAINTY  defecto 0.9: certeza minima (por accion y global) para preparar una vista
                                        previa cuando el modelo dice affirm y las reglas ven negacion/duda.
  JARVIS_CLASSIFIER_MAX_TOKENS          defecto 350 (tope de salida; acota el sobrecoste de una llamada).
  JARVIS_CLASSIFIER_JSON_MODE           "json_object" (defecto, lo soportan todos los modelos de chat
                                        actuales) o "json_schema" (esquema pydantic en response_format).
  JARVIS_CLASSIFIER_COMPANY_DAILY_BUDGET_USD  tope por empresa y dia UTC, defecto 0.50. <= 0 => sin modelo.
  JARVIS_CLASSIFIER_GLOBAL_DAILY_BUDGET_USD   tope global opcional (todas las empresas); vacio = sin tope.
El gasto se contabiliza en BD (agent_activities, paso COMPRENDER action=model_classify, details.cost_usd),
no en memoria del proceso. Un modelo sin tarifa en calculate_cost se registra con cost_known=false y se
cuenta con la tarifa mas cara conocida (gpt-4). Un timeout/excepcion cuenta el coste de la entrada estimada.
LIMITE: el tope se comprueba antes de cada llamada; una llamada en vuelo puede sobrepasarlo como maximo en el
coste de una llamada (acotado por max_tokens); peticiones concurrentes de la misma empresa tambien."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.schemas.zeus_task import ZeusEntities, ZeusTaskObject
from services import intent_parser as ip
from services.jarvis_classifier_prompt import build_messages

logger = logging.getLogger(__name__)

AGENT = "ZEUS CORE"
LOG_ACTION = "model_classify"
KNOWN_TARIFF_MODELS = frozenset({"gpt-3.5-turbo", "gpt-4-turbo", "gpt-4"})
CONSERVATIVE_TARIFF_MODEL = "gpt-4"
MAX_MESSAGE_CHARS = 600


# --------------------------------------------------------------------------------- esquema
class ClassifierEntities(ZeusEntities):
    model_config = ConfigDict(extra="forbid")
    recipients: Optional[Literal["all_customers", "segment", "specific"]] = None


class ClassifierAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action_type: Literal["send_campaign", "create_customer", "other_consequential"]
    polarity: Literal["affirm", "negate", "uncertain"]
    entities: ClassifierEntities = Field(default_factory=ClassifierEntities)
    certainty: float = Field(ge=0.0, le=1.0)


class ClassifierOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actions: List[ClassifierAction] = Field(default_factory=list, max_length=6)
    overall_certainty: float = Field(ge=0.0, le=1.0)
    needs_clarification: bool = False
    clarification_question: Optional[str] = Field(default=None, max_length=400)
    notes: str = Field(default="", max_length=400)


# --------------------------------------------------------------------------------- config
@dataclass
class ClassifierConfig:
    enabled: bool
    model: str
    timeout: float
    min_certainty: float
    max_tokens: int
    json_mode: str
    company_budget: float
    global_budget: Optional[float]
    conflict_certainty: float


def _f(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


def load_config() -> ClassifierConfig:
    try:
        from config.settings import settings

        default_model = settings.OPENAI_MODEL
    except Exception:  # pragma: no cover
        default_model = "gpt-3.5-turbo"
    g = os.getenv("JARVIS_CLASSIFIER_GLOBAL_DAILY_BUDGET_USD", "").strip()
    try:
        gb: Optional[float] = float(g) if g else None
    except ValueError:
        gb = None
    return ClassifierConfig(
        enabled=os.getenv("JARVIS_MODEL_COMPREHENSION", "1").strip().lower() not in ("0", "false", "no", "off"),
        model=os.getenv("JARVIS_CLASSIFIER_MODEL", "").strip() or default_model,
        timeout=max(0.05, _f("JARVIS_CLASSIFIER_TIMEOUT_SEC", 6.0)),
        min_certainty=min(1.0, max(0.7, _f("JARVIS_CLASSIFIER_MIN_CERTAINTY", 0.8))),
        max_tokens=int(_f("JARVIS_CLASSIFIER_MAX_TOKENS", 350)),
        json_mode="json_schema" if os.getenv("JARVIS_CLASSIFIER_JSON_MODE", "").strip() == "json_schema"
        else "json_object",
        company_budget=_f("JARVIS_CLASSIFIER_COMPANY_DAILY_BUDGET_USD", 0.50),
        global_budget=gb,
        conflict_certainty=min(1.0, max(0.7, _f("JARVIS_CLASSIFIER_CONFLICT_CERTAINTY", 0.9))),
    )


# --------------------------------------------------------------------------------- cliente
def get_client() -> Any:
    """Cliente OpenAI sincrono o None si no hay clave. Los tests lo sustituyen (monkeypatch)."""
    try:
        from config.settings import settings

        key = settings.OPENAI_API_KEY
    except Exception:  # pragma: no cover
        key = None
    if not key:
        return None
    from openai import OpenAI

    return OpenAI(api_key=key, max_retries=0)


# --------------------------------------------------------------------------------- puerta
# Verbos/sustantivos de acciones con consecuencias en cualquier forma (plegado: sin tildes).
_GATE_RE = re.compile(
    r"\b(?:envi|manda|mande|mandar|mandes|mandal|mandam|lanz|publi|difund|crea|crear|cree|crees|creame|"
    r"genera|alta|anad|agreg|registr|apunt|cobr|factur|borr|elimin|anul|pag|programa|suscrib|notific|"
    r"oferta|campan|promo|descuento|cupon|mailing|newsletter|cliente\s+nuevo|nuevo\s+cliente)\w*"
)


def passes_gate(message: str) -> bool:
    """True si el mensaje PUEDE pedir (o negar) una accion con consecuencias: barato, sin modelo."""
    t = (message or "").strip()
    if not t or len(t) > MAX_MESSAGE_CHARS:
        return False
    return bool(_GATE_RE.search(ip.fold(t)))


# --------------------------------------------------------------------------------- coste/tope
def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> Tuple[float, bool]:
    from services.openai_service import calculate_cost

    usage = {"prompt_tokens": int(prompt_tokens), "completion_tokens": int(completion_tokens)}
    if model in KNOWN_TARIFF_MODELS:
        return calculate_cost(usage, model), True
    return calculate_cost(usage, CONSERVATIVE_TARIFF_MODEL), False


def _day_start() -> datetime:
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def spent_today(db: Any, company_id: Optional[int]) -> float:
    """Gasto del dia UTC en llamadas al clasificador, sumado desde BD. company_id=None => global."""
    from app.models.agent_activity import AgentActivity

    q = db.query(AgentActivity.details).filter(
        AgentActivity.agent_name == AGENT,
        AgentActivity.action_type == "chain_comprender",
        AgentActivity.created_at >= _day_start(),
    )
    if company_id is not None:
        q = q.filter(AgentActivity.company_id == company_id)
    total = 0.0
    for (d,) in q.all():
        if isinstance(d, dict) and d.get("action") == LOG_ACTION:
            try:
                total += float(d.get("cost_usd") or 0.0)
            except (TypeError, ValueError):
                total += 0.0
    return total


def budget_ok(db: Any, company_id: int, cfg: ClassifierConfig) -> bool:
    """Fail-closed: cualquier fallo al comprobar el tope => no se llama al modelo."""
    if cfg.company_budget <= 0:
        return False
    try:
        db.rollback()  # lectura fresca (no un snapshot viejo de esta sesion)
        if spent_today(db, company_id) >= cfg.company_budget:
            return False
        if cfg.global_budget is not None and spent_today(db, None) >= max(cfg.global_budget, 0.0):
            return False
        return True
    except Exception:
        logger.exception("jarvis_model: no se pudo comprobar el tope de gasto; se usa el criterio estricto")
        return False


# --------------------------------------------------------------------------------- resultado
@dataclass
class Comprehension:
    task: ZeusTaskObject
    reply: Optional[str] = None          # respuesta directa (negacion, pregunta); None => seguir con `task`
    reply_is_question: bool = False
    used_model: bool = False
    result: str = "skipped"              # ok|timeout|invalid|error|budget_exceeded|skipped
    decision: str = "strict_rules"
    polarity_conflict: bool = False      # el modelo dijo affirm pero las reglas ven negacion/duda
    notice: Optional[str] = None         # aviso que el orquestador antepone a la vista previa


NOOP_REPLY = "Entendido, no hago nada. Si quieres que haga algo, dímelo de forma explícita."
GENERIC_QUESTION = (
    "No tengo claro si quieres que lo haga ahora. No he hecho nada: dime de forma explícita qué quieres "
    "(p. ej. «envía la oferta del 10% a todos mis clientes»)."
)
_INTENT_OF = {"send_campaign": "create_campaign_send", "create_customer": "create_customer"}
_LABEL_OF = {
    "send_campaign": "enviar una campaña a tus clientes",
    "create_customer": "crear un cliente",
    "other_consequential": "otra acción",
}


_EXEC_WORDS_RE = re.compile(
    r"\b(?:confirm\w*|ejecut\w*|proced\w*|actu(?:a|ar|are|o)|respond\w*|contest\w*|escrib\w*|"
    r"reply|answer|aprueb\w*|autoriz\w*)\b"
)


# Instrucciones disfrazadas: la pregunta pide al usuario que diga/escriba/pulse/ponga/mande un «sí/ok/vale».
# El «sí» con tilde es afirmacion; sin tilde solo cuenta si cierra la frase («di si», «di si y listo»), para no
# vetar «dime si quieres…». Se evalua sobre texto plegado (el «sí» acentuado se marca antes de plegar).
_AFFIRM_W = r"(?:siaff|ok|okay|vale|dale|adelante|hazlo|yes|de\s+acuerdo|si(?=\s*(?:[?.!,;]|$|y\b|para\b)))"
_SAY_VERBS = (r"(?:di|dime|digas|diga|decir|escribe|escribas|escribir|escribeme|teclea\w*|pulsa\w*|pon|ponme|"
              r"pongas|ponga|poner|contesta\w*|responde\w*|marca\w*|clica\w*|haz\s+clic\s+en)")
_DISGUISED_RE = re.compile(
    rf"\b{_SAY_VERBS}\b[^?.!]{{0,25}}?\b{_AFFIRM_W}"
    rf"|\b(?:manda\w*|mande\w*|envia\w*)(?:me|te)?\s+(?:un|el|tu)?\s*(?:siaff|ok|okay|vale)\b"
)
_BARE_CONFIRM_RE = re.compile(rf"[¿¡\s]*{_AFFIRM_W}[\s?!.]*")


def _clean_question(q: Optional[str]) -> Optional[str]:
    """Pregunta del modelo mostrable al usuario; si pudiera inducir a confirmar/ejecutar -> None."""
    if not q:
        return None
    t = " ".join(re.sub(r"[\x00-\x1f]", " ", q).split())
    if not t or len(t) > 300 or re.search(r"https?:|www\.|@|<|>|`", t):
        return None
    f = ip.fold(t.lower().replace("sí", "siaff"))
    if _EXEC_WORDS_RE.search(f) or _DISGUISED_RE.search(f) or _BARE_CONFIRM_RE.fullmatch(f):
        return None
    t = t.rstrip(".!,;: ").rstrip("?").rstrip(".!,;: ")
    return t + "?"


# --------------------------------------------------------------------------------- validacion
# Todas las comprobaciones son por TOKEN completo: una entidad del modelo debe ser EXACTAMENTE la que
# el usuario escribio, no un trozo de otra («ana.lopez@x.es» no valida «lopez@x.es»).
_PUNCT = ".,;:!?¡¿()«»\"'"


def _num_in_text(x: float, f: str) -> bool:
    """El numero debe ir pegado a «%» o seguido de «por ciento» (no «10 compras»)."""
    forms = {str(int(x))} if float(x).is_integer() else {str(x), str(x).replace(".", ",")}
    return any(
        re.search(rf"(?<![\d.,]){re.escape(s)}(?![\d.,]\d)\s?(?:%|por\s*ciento\b)", f) for s in forms
    )


def _email_in_text(cand: str, text: str) -> bool:
    return re.search(rf"(?<![\w.+@-]){re.escape(cand)}(?![\w@-]|\.\w)", text.lower()) is not None


def _phone_in_text(cand: str, text: str) -> bool:
    def norm(d: str) -> str:
        d = re.sub(r"\D", "", d)
        return d[2:] if len(d) == 11 and d.startswith("34") else d

    want = norm(cand)
    return any(norm(m.group(0)) == want
               for m in re.finditer(rf"(?<![\d+]){ip._PHONE_STRICT}(?!\d)", text))


def _name_in_text(cand: str, text: str) -> Optional[str]:
    """Devuelve el nombre tal como lo escribio el usuario si el del modelo es EXACTAMENTE el run de
    nombre (palabras completas, sin palabra capitalizada contigua que lo prolongue); si no, None."""
    words = [w.strip(_PUNCT) for w in text.split()]
    want = [ip.fold(w) for w in cand.split()]
    k = len(want)
    if not 1 <= k <= 4:
        return None

    def cap(w: str) -> bool:
        return bool(ip._NAME_WORD_RE.fullmatch(w))

    for i in range(len(words) - k + 1):
        if [ip.fold(w) for w in words[i:i + k]] != want:
            continue
        j = i - 1
        while j >= 0 and words[j] in ip._NAME_PARTICLES_LOWER:
            j -= 1
        if (i >= 1 and cap(words[i - 1])) or (j < i - 1 and j >= 0 and cap(words[j])):
            continue
        j = i + k
        while j < len(words) and words[j] in ip._NAME_PARTICLES_LOWER:
            j += 1
        if (i + k < len(words) and cap(words[i + k])) or (j > i + k and j < len(words) and cap(words[j])):
            continue
        return " ".join(words[i:i + k])
    return None


def _validate_campaign(act: ClassifierAction, text: str, f: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """(campos, pregunta). Valida en servidor lo que dijo el modelo; ante duda pregunta."""
    ent = act.entities
    if ip._PARTIAL_RECIPIENTS_RE.search(f):
        return None, ip.QUESTION_PARTIAL
    if ent.recipients == "segment" or ip._SEGMENT_RE.search(f):
        return None, ip.QUESTION_SEGMENT
    if ent.recipients != "all_customers" or not re.search(r"\b(?:clientes|todos|todas|crm|base)\b", f):
        return None, ip.QUESTION_RECIPIENTS if ent.recipients != "specific" else ip.QUESTION_SEGMENT
    if len(ent.percentages) > 1:
        return None, "Veo varios porcentajes en tu mensaje. ¿Qué descuento aplico a la oferta?"
    disc: Optional[float] = None
    if ent.percentages:
        p = float(ent.percentages[0])
        if not (0 < p <= 100) or not _num_in_text(p, f):
            return None, "No tengo claro el descuento. ¿Qué porcentaje aplico (entre 1 y 100)?"
        disc = p
    return {"discount": disc}, None


def _validate_customer(act: ClassifierAction, text: str, f: str) -> Dict[str, Any]:
    """Nombre/email/telefono validados (forma + presentes literalmente en el texto). Lo no valido => None."""
    ent = act.entities
    name = email = phone = None
    if len(ent.names) == 1:
        cand = " ".join(ent.names[0].split())
        written = _name_in_text(cand, text)
        if written and ip._name_ok(written):
            name = written
    if len(ent.emails) == 1:
        cand = ent.emails[0].strip().lower()
        if re.fullmatch(ip._EMAIL_STRICT, cand) and ip._email_ok(cand) and _email_in_text(cand, text):
            email = cand
    if len(ent.phones) == 1:
        cand = ent.phones[0].strip()
        if re.fullmatch(ip._PHONE_STRICT, cand) and _phone_in_text(cand, text):
            phone = cand
    return {"name": name, "email": email, "phone": phone}


_CONFLICT_RE = re.compile(
    r"\b(?:tampoco|ni|nada\s+de|deja(?:s)?\s+de|sin|mejor|todavia|aun\s+no|olvida\w*)\b"
)

# Negaciones/retractaciones SIN «no» (texto plegado): cancelar, detener, pausar, posponer, abstenerse...
# en imperativo, subjuntivo, infinitivo y forma nominal. Ver _PARA_VERB_RE para «para» como verbo.
_CANCEL_LEX_RE = re.compile(
    r"\b(?:cancel\w*|anul\w*|abort\w*|deten\w*|deteng\w*|abstente|abstenerte|abstengas|abstenga\w*|"
    r"abstencion|fren(?:a|as|e|es|ar|o)|suspend\w*|suspension|aplaz\w*|"
    r"posp(?:on|ones|oner|ongas|onga|ongamos|osicion)|pospues\w*|"
    r"deja(?:r|s|me)?\s+estar|espera(?:s|r)?\s+(?:antes|un\s+poco|a\s+que)|"
    r"retir(?:a|as|e|es|ar)\s+(?:el|la|los|las)\s+(?:envio|oferta|campana|mensaje|promocion)\w*)\b"
)
# «para» solo es verbo (parar) al inicio de clausula y seguido de articulo + sustantivo de accion/envio;
# «envia la oferta para mis clientes» (preposicion) no casa.
_PARA_VERB_RE = re.compile(
    r"(?:^|[.,;:!?¡¿]\s*|\b(?:y|pero|oye|ahora|mejor|porfa|favor)\s+)"
    r"para\s+(?:el|la|los|las|este|esta|ese|esa)\s+"
    r"(?:envio|envios|oferta|ofertas|campana|campanas|mensaje|mensajes|promocion|promociones|mailing|difusion|"
    r"correo|correos|proceso|mandar|enviar)\b"
)


def _rules_see_negation(f: str) -> bool:
    return bool(ip._NEGATION_ANY_RE.search(f) or ip._NEGATION_BEFORE_RE.search(f) or _CONFLICT_RE.search(f)
                or _CANCEL_LEX_RE.search(f) or _PARA_VERB_RE.search(f))


def _notice(action_type: str) -> str:
    return f"He entendido que SÍ quieres {_LABEL_OF[action_type]}. Si no es así, responde \"cancelar\"."


def decide(out: ClassifierOutput, text: str, cfg: ClassifierConfig) -> Comprehension:
    """Decision del servidor sobre la salida YA validada del modelo (ver docstring del modulo)."""
    f = ip.fold(" ".join(text.split()))
    acts = out.actions
    if not acts:
        return Comprehension(task=ZeusTaskObject(), decision="model_no_actions")  # el llamador cae a reglas
    if any(a.polarity == "negate" for a in acts):
        return Comprehension(task=ZeusTaskObject(), reply=NOOP_REPLY, decision="negate")
    thr = cfg.min_certainty
    uncertain = (
        out.needs_clarification
        or any(a.polarity == "uncertain" for a in acts)
        or out.overall_certainty < thr
        or any(a.certainty < thr for a in acts)
    )
    if uncertain:
        q = _clean_question(out.clarification_question) or GENERIC_QUESTION
        return Comprehension(task=ZeusTaskObject(), reply=q, reply_is_question=True, decision="clarify_uncertain")
    affirm = [a for a in acts if a.polarity == "affirm"]
    if len(affirm) >= 2:
        parts = " y ".join(_LABEL_OF[a.action_type] for a in affirm)
        return Comprehension(
            task=ZeusTaskObject(), reply=ip.QUESTION_MULTI.format(parts=parts), reply_is_question=True,
            decision="clarify_multi",
        )
    act = affirm[0]
    conflict = False
    if act.action_type != "other_consequential" and _rules_see_negation(f):
        # El modelo dice affirm pero hay negacion/duda en el texto («no te olvides de…» es legitimo; «no
        # envies…» con un modelo erroneo no). Solo se prepara con certeza reforzada y aviso explicito.
        if act.certainty < cfg.conflict_certainty or out.overall_certainty < cfg.conflict_certainty:
            lab = _LABEL_OF[act.action_type]
            return Comprehension(
                task=ZeusTaskObject(), polarity_conflict=True, reply_is_question=True,
                reply=(f"No tengo claro si quieres que lo haga o no ({lab}). No he hecho nada: dime de forma "
                       f"explícita si quieres que lo haga ahora."),
                decision="clarify_polarity_conflict")
        conflict = True
    if act.action_type == "other_consequential":
        return Comprehension(task=ZeusTaskObject(), decision="model_unsupported_action")  # reglas
    ent_all = ZeusEntities(percentages=list(act.entities.percentages))
    conf = round(min(ip.CONFIDENCE_CAP, act.certainty), 2)
    base_breakdown = {"rule": "model_classifier", "model_certainty": act.certainty,
                      "overall_certainty": out.overall_certainty, "threshold": thr}
    urgency = ip.detect_urgency(text)
    if act.action_type == "send_campaign":
        fields, question = _validate_campaign(act, text, f)
        if question:
            return Comprehension(task=ZeusTaskObject(), reply=question, reply_is_question=True,
                                 decision="clarify_invalid_entities")
        disc = fields["discount"]
        task = ZeusTaskObject(
            intent="create_campaign_send", action="create_campaign", discount_percent=disc,
            target="all_customers", campaign_name=ip._extract_campaign_name(text, disc),
            message_template=ip._default_offer_message(disc), requires_confirmation=True,
            raw_message=text, confidence=conf, entities=ZeusEntities(percentages=ent_all.percentages,
                                                                      recipients="all_customers"),
            urgency=urgency, confidence_breakdown=base_breakdown,
        )
        return Comprehension(task=task, decision="affirm_prepare", polarity_conflict=conflict,
                             notice=_notice(act.action_type) if conflict else None)
    # create_customer
    v = _validate_customer(act, text, f)
    meta = {"name": v["name"], "email": v["email"]}
    if v["phone"]:
        meta["phone"] = v["phone"]
    missing = [k for k in ("name", "email") if not v[k]]
    task = ZeusTaskObject(
        intent="create_customer", action="create_customer", raw_message=text, confidence=conf,
        metadata=meta, urgency=urgency, missing_entities=missing, confidence_breakdown=base_breakdown,
        entities=ZeusEntities(names=[v["name"]] if v["name"] else [], emails=[v["email"]] if v["email"] else [],
                              phones=[v["phone"]] if v["phone"] else []),
    )
    if missing:
        task.needs_clarification = True
        task.clarification_question = ip.question_for_customer(v["name"], v["email"])
        return Comprehension(task=task, decision="affirm_missing_entities")
    return Comprehension(task=task, decision="affirm_prepare", polarity_conflict=conflict,
                         notice=_notice(act.action_type) if conflict else None)


# --------------------------------------------------------------------------------- llamada
def _call_model(client: Any, cfg: ClassifierConfig, message: str) -> Any:
    kw: Dict[str, Any] = dict(
        model=cfg.model, messages=build_messages(message), temperature=0, max_tokens=cfg.max_tokens,
        timeout=cfg.timeout,
    )
    if cfg.json_mode == "json_schema":
        kw["response_format"] = {"type": "json_schema", "json_schema": {
            "name": "jarvis_classifier", "strict": False, "schema": ClassifierOutput.model_json_schema()}}
    else:
        kw["response_format"] = {"type": "json_object"}
    return client.chat.completions.create(**kw)


def _approx_tokens(s: str) -> int:
    return max(1, int(len(s) / 3.5))


async def comprehend(
    db: Any,
    user: Any,
    company_id: Optional[int],
    message: str,
    strict_task: ZeusTaskObject,
    step: Callable[..., bool],
) -> Comprehension:
    """Entrada unica. `strict_task` es el resultado de las reglas (red de seguridad). `step` registra
    en el paso COMPRENDER (mismo correlation_id J7). Nunca lanza: ante cualquier fallo -> reglas."""
    fallback = Comprehension(task=strict_task)
    try:
        cfg = load_config()
        if not cfg.enabled or company_id is None or not passes_gate(message):
            return fallback
        client = get_client()
        if client is None:
            logger.debug("jarvis_model: sin modelo configurado; criterio estricto")
            return fallback
        base = {"model": cfg.model, "min_certainty": cfg.min_certainty, "timeout_sec": cfg.timeout}
        if not budget_ok(db, company_id, cfg):
            step("COMPRENDER", LOG_ACTION, "budget_exceeded", result="budget_exceeded", decision="fallback_strict",
                 cost_usd=0.0, cost_known=True, tokens_in=0, tokens_out=0, latency_ms=0, **base)
            return Comprehension(task=strict_task, result="budget_exceeded", decision="fallback_strict")

        t0 = time.monotonic()
        result, resp, err = "ok", None, None
        try:
            resp = await asyncio.wait_for(asyncio.to_thread(_call_model, client, cfg, message), cfg.timeout)
        except asyncio.TimeoutError:
            result = "timeout"
        except Exception as exc:  # error de red/SDK: se registra el TIPO, nunca el texto del usuario
            result, err = "error", type(exc).__name__
            logger.warning("jarvis_model: fallo de la llamada (%s); criterio estricto", err)
        latency = int((time.monotonic() - t0) * 1000)

        tin = tout = 0
        out: Optional[ClassifierOutput] = None
        if resp is not None:
            try:
                usage = getattr(resp, "usage", None)
                tin = int(getattr(usage, "prompt_tokens", 0) or 0)
                tout = int(getattr(usage, "completion_tokens", 0) or 0)
                content = resp.choices[0].message.content
                if not tin:
                    tin = _approx_tokens(json.dumps(build_messages(message), ensure_ascii=False))
                if not tout:
                    tout = _approx_tokens(content or "")
                out = ClassifierOutput.model_validate(json.loads(content))
            except (ValidationError, ValueError, TypeError, AttributeError, IndexError):
                result, out = "invalid", None
        if not tin:  # timeout/error: se cuenta la entrada estimada (conservador)
            tin = _approx_tokens(json.dumps(build_messages(message), ensure_ascii=False))
        cost, known = estimate_cost(cfg.model, tin, tout)

        comp = fallback
        if out is not None:
            comp = decide(out, message, cfg)
            comp.used_model, comp.result = True, "ok"
            if comp.decision in ("model_no_actions", "model_unsupported_action"):
                comp.task = strict_task  # el modelo no vio accion soportada: manda el criterio estricto
        else:
            comp = Comprehension(task=strict_task, result=result, decision="fallback_strict")
        step("COMPRENDER", LOG_ACTION, "success" if comp.result == "ok" else comp.result,
             result=comp.result, decision=comp.decision, cost_usd=cost, cost_known=known, tokens_in=tin,
             tokens_out=tout, latency_ms=latency, error_type=err, polarity_conflict=comp.polarity_conflict,
             actions=[f"{a.action_type}:{a.polarity}" for a in out.actions] if out else [],
             overall_certainty=out.overall_certainty if out else None, **base)
        return comp
    except Exception:
        logger.exception("jarvis_model: fallo inesperado; criterio estricto")
        return fallback
