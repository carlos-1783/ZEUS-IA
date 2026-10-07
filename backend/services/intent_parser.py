"""Detección de intención en mensajes de chat ZEUS Core."""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Any, Dict, List, Optional

from app.schemas.zeus_task import ZeusEntities, ZeusTaskObject

# J3b: frase COMPLETA. "confirmar que no", "ejecuta el informe", "adelante con otra cosa" no confirman.
_CONFIRM_RE = re.compile(
    r"^\s*(confirmar|confirmo|s[ií],?\s*confirmo|ejecutar|ejecuta|adelante|ok,?\s*confirmar)\s*[.!]?\s*$",
    re.I,
)

# «sí» / «ok» solos: solo valen como confirmacion si hay un pending (lo decide el orquestador).
_AFFIRMATIVE_RE = re.compile(r"^\s*(s[ií]|ok)\s*[.!]?\s*$", re.I)

_CANCEL_RE = re.compile(
    r"^\s*(no|cancelar|cancela|cancelo|descartar|descarta|rechazar|rechazo)(,?\s*(cancelar|cancela|gracias))?\s*[.!]?\s*$",
    re.I,
)

# --------------------------------------------------------------------------------------------
# J8: comprension estructurada.
#
# Todas las reglas trabajan sobre el texto "plegado" (minusculas, sin acentos, n con tilde -> n)
# para que campaña/campana, métrica/metrica o ¿cuánto?/cuanto sean equivalentes. Las entidades
# (nombres) se extraen del texto original para conservar mayusculas y acentos.
#
# CRITERIO DE CONFIANZA (documentado, no una constante opaca):
#   base            0.68-0.72  coincidencia debil (una sola palabra clave, p. ej. «tpv» suelto)
#                   0.78-0.80  coincidencia normal (verbo/palabra + objeto, o palabra + cue)
#                   0.82-0.85  coincidencia fuerte (frase anclada: «cuantos clientes», «flujo de caja»)
#                   0.88-0.90  frase fuerte con todos sus componentes (verbo + oferta + destinatarios)
#   + 0.05          si la accion exige entidades obligatorias y estan TODAS presentes
#   - 0.20          si otra intencion compite (diferencia de base <= 0.06): ambiguedad
#   tope 0.97. Umbral de ejecucion: MIN_CONFIDENCE (0.70) en el orquestador.
# Faltar una entidad obligatoria NO baja la confianza (se entendio la intencion): marca
# needs_clarification y el orquestador pregunta por el dato concreto antes de actuar.
# Una intencion fuerte (base >= 0.80) "suprime" a las que explica (p. ej. una campaña que
# menciona «ventas» no es una consulta de TPV).
# --------------------------------------------------------------------------------------------

AMBIGUITY_MARGIN = 0.06
AMBIGUITY_PENALTY = 0.20
REQUIRED_PRESENT_BONUS = 0.05
CONFIDENCE_CAP = 0.97

INTENT_LABELS: Dict[str, str] = {
    "get_cashflow": "el estado de caja / tesorería (cashflow)",
    "get_metrics": "las métricas del negocio (ingresos, costes, margen)",
    "tpv_sales_summary": "las ventas del TPV",
    "tpv": "las ventas del TPV",
    "tpv_sales_today": "las ventas del TPV de hoy",
    "list_customers_summary": "cuántos clientes tienes",
    "analytics_summary": "el resumen de actividad de los agentes",
    "shift_status": "tu turno / fichaje",
    "create_customer": "crear un cliente",
    "create_campaign_send": "enviar una campaña a tus clientes",
    # J9e
    "get_legal_status": "el estado legal / documentos legales",
    "run_compliance_audit": "una auditoría de cumplimiento",
    "get_inventory_status": "el estado del inventario",
    "create_ops_route": "crear una ruta operativa",
    "create_inventory_movement": "registrar un movimiento de inventario",
}


def fold(text: str) -> str:
    """Minusculas, sin acentos y n con tilde -> n."""
    t = unicodedata.normalize("NFD", (text or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.\w{2,}")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+34[\s.-]?)?[6-9]\d{2}[\s.-]?\d{3}[\s.-]?\d{3}(?!\d)")
_AMOUNT_RE = re.compile(
    r"(?<![\w.,])(\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:[.,]\d{1,2})?)\s*(?:€|euros?\b|eur\b)",
    re.I,
)
_AMOUNT_PREFIX_RE = re.compile(r"€\s*(\d+(?:[.,]\d{1,2})?)")
_PERCENT_RE = re.compile(r"(\d{1,3}(?:[.,]\d+)?)\s*(?:%|por\s*ciento)", re.I)
_DISCOUNT_RE = re.compile(r"(\d{1,3}(?:[.,]\d+)?)\s*%|descuento\s*(?:de|del)?\s*(\d{1,2})\b", re.I)
_DATE_DMY_RE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b")
_DATE_ISO_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_INVOICE_RE = re.compile(r"\bfactura\s*(?:n[ºo°.]*\s*)?#?([A-Z]{0,5}[-/]?\d[\w/-]*)", re.I)
_CUSTOMER_ID_RE = re.compile(r"\bcliente\s*(?:id\s*|n[ºo°.]*\s*|#\s*)(\d+)\b|\bcliente\s+(\d+)\b", re.I)
_NAME_AFTER_CLIENTE_RE = re.compile(
    r"\bcliente\s+(?:(?:llamad[oa]|de\s+nombre|nuevo|nueva)\s+)?"
    r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'.-]*(?:\s+[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'.-]*){0,4})",
    re.I,
)
_NAME_STOP = {
    "nuevo", "nueva", "con", "de", "que", "para", "en", "y", "mi", "un", "una", "el", "la", "los",
    "las", "email", "correo", "mail", "tel", "telefono", "movil", "llamado", "llamada", "se", "por",
    "al", "del", "a", "es", "lo",
}
_CAPITALIZED_NAME_RE = re.compile(
    r"(?<![.¿¡!?]\s)(?<!^)\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+(?:de\s+|del\s+|la\s+)?[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)+"
)


def _to_float(raw: str) -> Optional[float]:
    r = raw.strip()
    if "," in r:  # formato es-ES: 1.234,56
        r = r.replace(".", "").replace(",", ".")
    elif r.count(".") > 1 or re.fullmatch(r"\d{1,3}\.\d{3}", r):
        r = r.replace(".", "")
    try:
        return float(r)
    except ValueError:
        return None


def _extract_period(f: str) -> Optional[Dict[str, Any]]:
    m = re.search(r"(?:ultimos?\s+)?(\d{1,3})\s+dias?\b", f)
    if m:
        d = int(m.group(1))
        if 1 <= d <= 365:
            return {"label": "last_days", "days": d}
    if re.search(r"\b(mes\s+pasado|mes\s+anterior)\b", f):
        return {"label": "previous_month", "days": None}
    if re.search(r"\b(semana\s+pasada|semana\s+anterior)\b", f):
        return {"label": "previous_week", "days": None}
    if re.search(r"\bayer\b", f):
        return {"label": "yesterday", "days": None}
    if re.search(r"\b(hoy|de\s+hoy|este\s+dia)\b", f):
        return {"label": "today", "days": 1}
    if re.search(r"\b(esta\s+semana|ultima\s+semana|semanal)\b", f):
        return {"label": "week", "days": 7}
    if re.search(r"\b(este\s+mes|ultimo\s+mes|del\s+mes|mensual|mes\s+en\s+curso)\b", f):
        return {"label": "month", "days": 30}
    if re.search(r"\b(este\s+ano|del\s+ano|anual|ultimo\s+ano)\b", f):
        return {"label": "year", "days": 365}
    return None


def _clean_name(raw: str) -> Optional[str]:
    toks: List[str] = []
    for tok in raw.split():
        if fold(tok) in _NAME_STOP:
            if toks:
                break
            return None
        toks.append(tok.strip(".,;:"))
    name = " ".join(t for t in toks if t).strip()
    return name if len(name) >= 2 else None


def extract_entities(text: str) -> ZeusEntities:
    """Entidades tipadas del mensaje. Solo se rellena lo que aparece de verdad."""
    t = text or ""
    f = fold(t)
    ent = ZeusEntities()
    ent.emails = list(dict.fromkeys(_EMAIL_RE.findall(t)))
    no_email = _EMAIL_RE.sub(" ", t)
    ent.phones = list(dict.fromkeys(re.sub(r"[\s.-]", "", p) for p in _PHONE_RE.findall(no_email)))

    for m in _AMOUNT_RE.finditer(no_email):
        v = _to_float(m.group(1))
        if v is not None:
            ent.amounts.append({"value": v, "currency": "EUR"})
    for m in _AMOUNT_PREFIX_RE.finditer(no_email):
        v = _to_float(m.group(1))
        if v is not None:
            ent.amounts.append({"value": v, "currency": "EUR"})
    for m in _PERCENT_RE.finditer(no_email):
        v = _to_float(m.group(1))
        if v is not None and 0 < v <= 100:
            ent.percentages.append(v)

    for m in _DATE_ISO_RE.finditer(no_email):
        try:
            ent.dates.append(date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat())
        except ValueError:
            pass
    for m in _DATE_DMY_RE.finditer(no_email):
        try:
            ent.dates.append(date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat())
        except ValueError:
            pass
    ent.period = _extract_period(f)
    if ent.period is None and ent.dates:
        ent.period = {"label": "custom", "days": None}

    ent.invoice_ids = list(dict.fromkeys(m.group(1) for m in _INVOICE_RE.finditer(no_email)))
    ent.customer_ids = [int(a or b) for a, b in _CUSTOMER_ID_RE.findall(no_email)]

    names: List[str] = []
    m = _NAME_AFTER_CLIENTE_RE.search(no_email)
    if m and not _CUSTOMER_ID_RE.search(no_email[m.start():m.end() + 1]):
        # corta el nombre en la primera palabra de relleno / digito
        cand = re.split(
            r"\s+(?:con|que|para|y|email|correo|mail|tel|telefono|movil)\b|[,;:\d]", m.group(1), maxsplit=1,
            flags=re.I,
        )[0]
        nm = _clean_name(cand)
        if nm:
            names.append(nm)
    for m in _CAPITALIZED_NAME_RE.finditer(no_email):
        nm = m.group(0).strip()
        if nm not in names:
            names.append(nm)
    ent.names = names

    if re.search(r"\b(todos|todas|clientes|crm|base\s+de\s+datos|contactos)\b", f):
        ent.recipients = "all_customers"
    return ent


_URGENT_RE = re.compile(
    r"\b(urgente|urgentemente|urgencia|cuanto\s+antes|lo\s+antes\s+posible|ahora\s+mismo|ya\s+mismo|"
    r"inmediatamente|inmediato|asap|hoy\s+mismo|para\s+hoy|antes\s+de\s+hoy|sin\s+demora)\b"
    r"|(?:^|[\s,.;¡!])ya\s*[.!¡]*\s*$",
)
_LOW_RE = re.compile(
    r"\b(sin\s+prisa|no\s+corre\s+prisa|cuando\s+puedas|cuando\s+tengas\s+un\s+rato|con\s+calma|"
    r"no\s+es\s+urgente|no\s+hay\s+prisa)\b"
)


def detect_urgency(text: str) -> str:
    """high/low solo por senales EXPLICITAS; en cualquier otro caso normal.
    «hoy» a secas es un periodo («ventas de hoy»), no urgencia; «hoy mismo» / «para hoy» si lo es."""
    f = fold(text)
    if _LOW_RE.search(f):
        return "low"
    if _URGENT_RE.search(f):
        return "high"
    return "normal"


# ------------------------------------------------------------------------------- reglas

_OFFER_NOUN = r"(?:oferta|ofertas|descuento|descuentos|promocion|promociones|promo|promos|campana|campanas|cupon|cupones)"
_SEND_VERB = (
    r"(?:envia|enviar|enviale|enviala|enviales|enviarla|enviame|mandar|manda|mandale|mandala|mandales|mandame|"
    r"notifica|notificar|avisa|avisar|comunica|comunicar|difunde|lanza|lanzar|"
    # subjuntivo (imperativo negado: «no mandes», «no envíes»): se reconoce para poder NEGARLO
    r"mandes|envies|lances|notifiques|avises|comuniques|difundas)"
)
_CREATE_VERB = (
    r"(?:crea|crear|creame|genera|generar|haz|hacer|monta|montar|prepara|preparar|"
    r"crees|generes|hagas|montes|prepares)"
)
_OFFER_RE = re.compile(rf"\b{_OFFER_NOUN}\b")
_SEND_RE = re.compile(rf"\b{_SEND_VERB}\b")
_CREATE_RE = re.compile(rf"\b{_CREATE_VERB}\b")
# Canales/medios que no son envio CRM por email: es trabajo de PERSEO/LLM, no esta regla.
_OTHER_CHANNEL_RE = re.compile(
    r"\b(instagram|facebook|tiktok|linkedin|twitter|redes|blog|post|video|anuncio|anuncios|ads|banner|imagen|logo|web|landing)\b"
)
_PLURAL_RECIPIENTS_RE = re.compile(r"\b(todos|todas|clientes|crm|base\s+de\s+datos|contactos|lista\s+de\s+clientes)\b")
_SEGMENT_RE = re.compile(
    r"\bclientes\s+(?:de|en|que|del|cuyo|cuya)\s+(?!(?:mi|la|el)\s+(?:crm|base|lista)\b|crm\b|la\s+base\b)"
)

_CREATE_CUSTOMER_RE = re.compile(
    r"\b(crea|crear|creame|da\s+de\s+alta|dar\s+de\s+alta|alta\s+de|alta|anade|anadir|registra|registrar|"
    r"agrega|agregar|apunta|nuevo|nueva|crees|registres|agregues|anadas|apuntes|des\s+de\s+alta)\b(.{0,30}?)\bcliente\b"
)
_CREATE_CUSTOMER_BLOCK = re.compile(
    r"\b(campana|oferta|descuento|promo|factura|informe|presupuesto|email|correo|pedido|mensaje)\b"
)
_LIST_CUSTOMERS_RE = re.compile(
    r"\b(cuantos|cuantas|lista|listar|listame|mostrar|muestrame|ver|dame|tengo|resumen\s+de)\b.{0,40}?\bclientes\b"
    r"|\bclientes\b.{0,15}?\b(tengo|tenemos|hay)\b"
)
_CASH_STRONG_RE = re.compile(
    r"\b(cashflow|cash\s*flow|flujo\s+de\s+caja|flujo\s+de\s+efectivo|tesoreria|saldo|balance)\b"
)
_CASH_CUE_RE = re.compile(
    r"\b(como\s+va|como\s+esta|como\s+anda|como\s+vamos|estado\s+de|situacion\s+de|"
    r"cuanto\s+(?:hay|queda|tengo|tenemos)\s+en|saldo\s+de|resumen\s+de|cierre\s+de|movimientos\s+de|"
    r"revisa|dime)\b.{0,25}?\bcaja\b"
)
_SALES_WORD_RE = re.compile(
    r"\b(venta|ventas|vendido|vendidos|vendimos|vendi|vendemos|vender|facturado|facturacion|facturamos|"
    r"recaudado|recaudacion|tpv|ticket|tickets|comanda|comandas)\b"
)
_TODAY_RE = re.compile(r"\b(hoy|de\s+hoy|este\s+dia)\b")
_CAJA_TODAY_RE = re.compile(r"\bcaja\b.{0,25}?\b(hoy|de\s+hoy)\b|\b(hoy|de\s+hoy)\b.{0,25}?\bcaja\b")
_TPV_QUERY_RE = re.compile(r"\b(cuanto|cuantas|total|resumen|como\s+(?:van|fueron|han\s+ido|va)|ultim\w+)\b")
_METRICS_STRONG_RE = re.compile(r"\b(metrica|metricas|revenue|margen|margenes)\b")
_METRICS_WEAK_RE = re.compile(r"\b(ingreso|ingresos|coste|costes|costo|costos|staff)\b")
_METRICS_CUE_RE = re.compile(r"\b(mes|semana|ano|empresa|resumen|zeus|core|negocio|ultim\w+|dias|este|esta)\b")
_ANALYTICS_RE = re.compile(
    r"\b(actividad|analytics|estadistica|estadisticas)\b|"
    r"\b(resumen|metricas?)\b.{0,40}?\b(agentes?|sistema|zeus|global)\b"
)
_SHIFT_RE = re.compile(
    r"\b(turnos?|jornada|fichaje|fichar|fichado|control\s+horario)\b.{0,40}?"
    r"\b(activo|activa|estado|abierto|abierta|tengo|estoy)\b"
    r"|\b(estoy|sigo)\s+fichad[oa]\b"
)
_OPERATIONAL_RE = re.compile(
    r"(env[ií][aáe]s?|mand(?:ar|a|es)\b|campa[nñ]a|oferta|descuento|cliente|venta|tpv|caja|turno|"
    r"jornada|fichaje|importar|confirmar|promoci[oó]n)",
    re.I,
)
# Peticiones de redaccion/consejo: aunque nombren «clientes» o «ventas» son conversacion con el LLM.
_CONVERSATIONAL_RE = re.compile(
    r"\b(redacta|redactame|escribe|escribeme|explica|explicame|idea|ideas|consejo|consejos|recomienda|"
    r"recomiendame|que\s+opinas|por\s+que|como\s+puedo\s+mejorar|sugiere|sugerencias)\b"
)


# --- H2: negacion / duda / mensajes de varias acciones --------------------------------------
# DISEÑO: una orden de accion (crear cliente, enviar campaña) precedida en la misma frase (hasta 40
# caracteres, sin punto/interrogacion/punto y coma de por medio) por una negacion o duda NO se
# ejecuta ni genera vista previa: ZEUS pregunta. Incluye «no, envía oferta…» (un «no» que contesta
# y luego ordena): se decide lo SEGURO, preguntar, porque el mensaje es contradictorio.
_NEGATION_BEFORE_RE = re.compile(
    r"(?:\b(?:no|nunca|jamas|tampoco|evita|evitar|evites|evitemos|dudo|quiza|quizas)\b"
    r"|\btal\s+vez\b|\ba\s+lo\s+mejor\b|\bsin\s+necesidad\s+de\b)[^.?!;]{0,40}$"
)
# Destinatarios parciales dichos DESPUES del verbo: «envía la oferta pero no a todos», «solo a…».
_PARTIAL_RECIPIENTS_RE = re.compile(
    r"\bpero\s+no\b|\bno\s+a\s+(?:todos|todas|los|las)\b|\bsolo\b|\bunicamente\b|\bexcepto\b|"
    r"(?<!al\s)\bmenos\b|\bsalvo\b|\bsin\s+(?:los|las)\b"
)
_NEGATION_ANY_RE = re.compile(r"\b(no|nunca|jamas|evita|evitar|evites)\b")

QUESTION_NEGATED = (
    "No lo he entendido como una orden clara y única (hay una negación, duda, condición, retractación u otra cosa añadida), así que no he hecho nada. "
    "Si quieres que lo haga, dímelo de forma explícita (p. ej. «envía oferta 10% a todos mis clientes»)."
)
QUESTION_PARTIAL = (
    "Solo puedo enviar campañas a TODOS los clientes del CRM: no sé excluir a nadie ni enviar a un "
    "subconjunto o a una sola persona. No he hecho nada. ¿La envío a todos tus clientes o prefieres no enviarla?"
)
QUESTION_MULTI = (
    "Me pides varias cosas a la vez ({parts}). Hago una cada vez y no ejecuto nada sin tu confirmación: "
    "dime cuál quieres primero y luego me pides la otra."
)


# --- LISTA BLANCA para acciones con consecuencias (crear cliente, enviar campaña) --------------
# CRITERIO: la accion solo se PREPARA si el verbo de accion (el primero del mensaje) va en una
# clausula con forma de ORDEN AFIRMATIVA: verbo en imperativo/infinitivo de peticion y, ANTES de el
# en esa frase (desde el ultimo . ; : ! ? del texto), como mucho formulas de cortesia/vocativo
# («por favor», «zeus,», «oye», «vale,», «venga,», «ahora») y formulas de peticion («quiero que»,
# «necesito», «puedes», «me gustaria que»…). Cualquier OTRO material antes del verbo (negacion,
# «nada de», «deja de», «sin», «ni se te ocurra», «si quieres», «y si», dudas, subordinadas,
# condicionales) => NO se prepara: needs_clarification con pregunta explicita.
# El subjuntivo («envíes», «crees») solo vale tras una formula con «que» («quiero que envíes»).
# La lista negra (_NEGATION_BEFORE_RE) se mantiene como defensa adicional.
# FALSOS NEGATIVOS CONSERVADORES CONOCIDOS (se pregunta aunque el usuario si queria hacerlo):
# «no olvides enviar…», «no dejes de enviar…», «no es que no quiera, envía…», «primero revisa X y
# luego envía…» (material antes del verbo), «para aumentar ventas, crea una campaña…».
_COURTESY = (
    "por favor", "porfa", "porfavor", "zeus", "jarvis", "oye", "hola", "vale", "venga", "ahora", "ok", "bien",
    "entonces", "pues", "gracias", "perdona", "disculpa", "urgente", "a ver", "me", "nos", "ya", "y",
)
_REQUEST_FORMULAS = (
    "quiero que", "queremos que", "necesito que", "necesitamos que", "me gustaria que", "quisiera que",
    "te pido que", "te pedimos que", "puedes", "podrias", "podeis", "podemos", "quiero", "queremos",
    "necesito", "necesitamos", "me gustaria", "quisiera", "tienes que", "debes", "hay que", "vamos a",
    "voy a", "vas a",
)
_SUBJUNCTIVE = {
    "envies", "mandes", "lances", "notifiques", "avises", "comuniques", "difundas",
    "crees", "generes", "hagas", "montes", "prepares", "registres", "agregues", "anadas", "apuntes",
    "anotes", "planifiques",
}
_SENTENCE_BREAK_RE = re.compile(r"[.;:!?¿¡\n]")


def _is_affirmative_request(f: str, verb_start: int, verb_text: str) -> bool:
    """True solo si el prefijo de la frase antes del verbo son formulas de cortesia/peticion."""
    before = f[:verb_start]
    parts = _SENTENCE_BREAK_RE.split(before)
    prefix = re.sub(r"[,\"'«»()]", " ", parts[-1] if parts else "")
    prefix = " ".join(prefix.split())
    had_que = False
    ordered = sorted(_REQUEST_FORMULAS + _COURTESY, key=len, reverse=True)
    while prefix:
        for tok in ordered:
            if prefix == tok or prefix.startswith(tok + " "):
                if tok.endswith(" que"):
                    had_que = True
                prefix = prefix[len(tok):].strip()
                break
        else:
            return False
    if verb_text in _SUBJUNCTIVE and not had_que:
        return False
    return True


# --- PLANTILLAS COMPLETAS para acciones confirmables (J8, red de seguridad hasta J8b) -----------
# CRITERIO: el MENSAJE ENTERO (tras NFKC y espacios colapsados, comparando en minusculas sin
# acentos) debe encajar EXACTAMENTE, anclado ^...$, en una plantilla de orden afirmativa:
#   campaña : [prefijo] VERBO [art] (oferta|campaña|promoción|descuento…) [de descuento] [del N%]
#             a [todos] [mis|los] clientes [con un N% de descuento] [cierre]
#             (o «crea/genera… <oferta> [N%] y envíala a [los] clientes»)
#   cliente : [prefijo] (crea|da de alta|añade…) [el|un|al] [nuevo] cliente [NOMBRE] [,] [con]
#             [email|correo] [EMAIL] [y teléfono TEL] [cierre]
# - prefijo: solo cortesía y fórmulas de petición («por favor», «zeus,», «quiero que», «puedes»…).
# - NOMBRE: 1-4 palabras, solo letras latinas, Capitalizadas (partículas de/del/la/los/las/y en
#   minúscula), ANTES del email y ninguna en la lista de parada (no, nunca, mejor, cancela, stop…).
# - EMAIL: uno, forma estricta; ningún token del local-part/dominio (separado por . _ + - @) puede
#   estar en la lista de parada («no.envies@x.es», «no@x.es» se rechazan).
# - cierre: solo «, gracias» / «gracias» / «por favor» y un único «.» o «!» final.
# Todo lo demás (emoji, símbolos, números sueltos fuera de N% o teléfono, «?», «...», «!!»,
# caracteres de otros alfabetos o no convertibles por NFKC, texto añadido, otra frase) => no encaja =>
# explicit_intent y pregunta, NUNCA vista previa.
# FALSOS NEGATIVOS CONSERVADORES ESPERADOS: cualquier formulación fuera de plantilla («envía ofertas
# a mis clientes cuanto antes», «No. Envía…», nombres en minúsculas o con guion/apóstrofo, «…para
# aumentar las ventas…»). RESIDUO CONOCIDO: un nombre propio extraño pero con forma válida se verá en
# la vista previa («Voy a crear el cliente X») y requiere confirmación humana explícita.
_STOP_WORDS = set(
    """no nunca jamas mejor cancela cancelar cancelo cancel annule stop espera esperar wait broma manana luego
    despues ya ahora ni nada pas maintenant don nein nope non nao arrete solo si cuando quizas quiza tal vez
    olvida olvidalo borra borrar lo hagas hagais haga crees creas envies envias tampoco sin deja dejes es hay se
    te le ok vale bien pues momento jaja jajaja jeje hoy ninguno ninguna ningun lo la los las de del y a al
    mal peor aun todavia aunque pero o u e detente aguarda anula frena basta olvidate quieto abortar desiste
    suspende pausa cese""".split()
)
_NAME_PARTICLES_LOWER = {"de", "del", "la", "los", "las", "y"}
_NAME_WORD_RE = re.compile(r"[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+")
_ART = r"(?:(?:la|las|el|los|una|un|unas|unos|mi|esta|nueva|nuevo)\s+){0,2}"
_NOUN = r"(?:oferta|ofertas|descuento|descuentos|promocion|promociones|promo|promos|campana|campanas|cupon|cupones)"
_PCT = r"(?:(?:del|de\s+un|de|con\s+un|con|al)\s+)?\d{1,3}(?:[.,]\d+)?\s?%"
_DISC = rf"(?:\s+de\s+descuento)?(?:\s+{_PCT})?(?:\s+de\s+descuento)?"
_RECIP = r"\s+a\s+(?:(?:todos|todas)\s+)?(?:(?:mis|los|las|nuestros|nuestras)\s+)?clientes"
_RECIP_TAIL = r"(?:\s+(?:con|de)\s+(?:un\s+)?\d{1,3}(?:[.,]\d+)?\s?%(?:\s+de\s+descuento)?)?"
_SEND_V = (r"(?:envia|enviar|manda|mandar|lanza|lanzar|difunde|envies|mandes|enviame|mandame)"
           r"(?:la|lo|le|les|me)?")
_CREATE_V = r"(?:crea|crear|creame|genera|generar|haz|hacer|monta|montar|prepara|preparar|crees|generes|hagas)"
_CLOSE = r"(?:,?\s+(?:gracias|por\s+favor))?[.!]?"
_CAMPAIGN_TEMPLATES = (
    re.compile(rf"^(?P<prefix>.*?)\b(?P<verb>{_SEND_V})\s+{_ART}{_NOUN}{_DISC}{_RECIP}{_RECIP_TAIL}{_CLOSE}$"),
    re.compile(
        rf"^(?P<prefix>.*?)\b(?P<verb>{_CREATE_V})\s+{_ART}{_NOUN}{_DISC}(?:\s*,)?\s+y\s+{_SEND_V}{_RECIP}{_CLOSE}$"
    ),
)
_EMAIL_STRICT = r"[a-z0-9]+(?:[._+-][a-z0-9]+)*@[a-z0-9]+(?:[.-][a-z0-9]+)*\.[a-z]{2,}"
_PHONE_STRICT = r"(?:\+34\s?)?[6-9]\d{2}[\s.-]?\d{3}[\s.-]?\d{3}"
_NAME_FOLDED = r"[a-z]+(?:\s+(?:(?:de|del|la|los|las|y)\s+)*[a-z]+){0,3}?"
_CUSTOMER_TEMPLATE = re.compile(
    r"^(?P<prefix>.*?)\b(?P<verb>crea|crear|creame|da\s+de\s+alta|dar\s+de\s+alta|des\s+de\s+alta|anade|anadir|"
    r"registra|registrar|agrega|agregar|apunta|crees|registres|agregues|anadas|apuntes)\s+"
    r"(?:(?:el|un|al|a\s+un)\s+)?(?:nuevo\s+)?cliente"
    rf"(?:\s+(?:llamado|de\s+nombre))?(?:\s+(?P<name>{_NAME_FOLDED}))??"
    rf"(?:\s*,)?(?:\s+con)?(?:\s+(?:email|correo|mail))?(?:\s+(?P<email>{_EMAIL_STRICT}))?"
    rf"(?:(?:\s*,)?\s+(?:y|con)\s+(?:telefono|tel|movil)\s+(?P<tel>{_PHONE_STRICT}))?{_CLOSE}$"
)


def _prefix_ok(prefix: str, verb: str) -> bool:
    pre = " ".join(re.sub(r",", " ", prefix).split())
    had_que = False
    ordered = sorted(_REQUEST_FORMULAS + _COURTESY, key=len, reverse=True)
    while pre:
        for tok in ordered:
            if pre == tok or pre.startswith(tok + " "):
                had_que = had_que or tok.endswith(" que")
                pre = pre[len(tok):].strip()
                break
        else:
            return False
    return not (verb in _SUBJUNCTIVE and not had_que)


def _name_ok(original: str) -> bool:
    words = original.split()
    if not 1 <= len(words) <= 4:
        return False
    for i, w in enumerate(words):
        fw = fold(w)
        if fw in _STOP_WORDS and not (i > 0 and w in _NAME_PARTICLES_LOWER):
            return False
        if i > 0 and w in _NAME_PARTICLES_LOWER:
            continue
        if not _NAME_WORD_RE.fullmatch(w):
            return False
    return words[-1] not in _NAME_PARTICLES_LOWER and words[0] not in _NAME_PARTICLES_LOWER


def _email_ok(email: str) -> bool:
    local, _, domain = email.rpartition("@")
    labels = domain.split(".")[:-1]  # el TLD («.es») no cuenta
    toks = re.split(r"[._+-]", local) + [x for lab in labels for x in lab.split("-")]
    return not any(tok in _STOP_WORDS for tok in toks)


def _is_clean_order(text: str, customer: bool) -> bool:
    """True solo si el mensaje ENTERO encaja en una plantilla de orden afirmativa (ver arriba)."""
    t = " ".join(unicodedata.normalize("NFKC", text or "").split())
    f = "".join(fold(ch) for ch in t)
    if len(f) != len(t) or not t:
        return False
    if customer:
        m = _CUSTOMER_TEMPLATE.match(f)
        if not m or not _prefix_ok(m.group("prefix"), m.group("verb")):
            return False
        if m.group("name") is not None and not _name_ok(t[m.start("name"):m.end("name")]):
            return False
        return m.group("email") is None or _email_ok(m.group("email"))
    for tpl in _CAMPAIGN_TEMPLATES:
        m = tpl.match(f)
        if m and _prefix_ok(m.group("prefix"), m.group("verb")):
            return True
    return False


# --- J9e: JUSTICIA / AFRODITA en el chat -------------------------------------------------------
# CONSULTAS (sin confirmacion): estado legal, auditoria de cumplimiento, inventario, turnos.
# ESCRITURAS (vista previa + aprobacion J3b): ruta operativa y movimiento de inventario. CRITERIO
# ESTRICTO como J8: el mensaje ENTERO debe encajar, anclado, en UNA de estas dos plantillas (tras NFKC y
# espacios colapsados, sin acentos), con el mismo prefijo de cortesia/peticion que las demas acciones:
#   ruta      : [prefijo] (crea|genera|planifica|prepara|monta|registra|anade|haz) [una|la|nueva] ruta
#               [operativa|de reparto|de entrega|logistica] (de|desde) ORIGEN (a|hasta|hacia) DESTINO [cierre]
#   movimiento: [prefijo] (registra|anota|anade|agrega|apunta|crea|genera|haz) [un|una|el] [movimiento de]
#               (entrada|salida) [de stock] de N [unidades|uds|ud|u] (de|del) PRODUCTO [en el inventario] [cierre]
# - ORIGEN/DESTINO: 1-5 palabras Capitalizadas o numeros (particulas de/del/la/las/los/el/y interiores en
#   minuscula), ninguna en la lista de parada. - PRODUCTO: 1-6 palabras (letras/digitos/.-'), ninguna en la
#   lista de parada; la identidad real la decide el SERVIDOR al preparar (nombre o SKU EXACTOS dentro de LA
#   EMPRESA del usuario: otro tenant, ausente o ambiguo -> no se prepara).
# - N: numero positivo (<= 1.000.000). «salida» resta, «entrada» suma. «ajuste», kg/litros, signos, varias
#   cantidades o cualquier otro texto => no encaja => pregunta, NUNCA vista previa.
# FALSOS NEGATIVOS CONSERVADORES: cualquier formulacion fuera de plantilla, ciudades con palabras de parada
# («A Coruña»), productos con «sin»/«no» en el nombre, mensajes con otra frase o negacion.
QUESTION_OPS = (
    "No lo he entendido como una orden clara y completa, así que no he preparado nada. Dímelo así: "
    "«crea una ruta de Madrid a Valencia» o «registra una entrada de 5 unidades de Harina»."
)
_OPS_CREATE_V = (
    r"(?:crea|crear|creame|genera|generar|planifica|planificar|prepara|preparar|monta|montar|registra|registrar|"
    r"anade|anadir|agrega|agregar|haz|hacer|apunta|apuntar|anota|anotar|da\s+de\s+alta|"
    r"crees|generes|planifiques|prepares|montes|registres|anadas|agregues|hagas|apuntes|anotes)"
)
_MOV_NOUN = r"(?:movimientos?|entradas?|salidas?|ajustes?)"
_ROUTE_TRIGGER_RE = re.compile(rf"\b{_OPS_CREATE_V}\b.{{0,30}}?\bruta\b")
_MOV_TRIGGER_RE = re.compile(
    rf"\b{_OPS_CREATE_V}\b.{{0,30}}?\b{_MOV_NOUN}\b.{{0,60}}?\b(?:stock|inventario|existencias|unidades|uds?|\d)"
)
_ROUTE_TEMPLATE = re.compile(
    rf"^(?P<prefix>.*?)\b(?P<verb>{_OPS_CREATE_V})\s+(?:(?:una|la|nueva)\s+){{1,2}}ruta"
    r"(?:\s+(?:operativa|de\s+reparto|de\s+entrega|logistica))?\s+(?:de|desde)\s+(?P<o>.+?)"
    rf"\s+(?:a|hasta|hacia)\s+(?P<d>.+?){_CLOSE}$"
)
_MOV_TEMPLATE = re.compile(
    rf"^(?P<prefix>.*?)\b(?P<verb>{_OPS_CREATE_V})\s+(?:(?:un|una|el)\s+)?(?:movimiento\s+de\s+)?"
    r"(?P<type>entrada|salida)\s+(?:de\s+)?(?:stock\s+)?(?:de\s+)?(?P<qty>\d{1,7}(?:[.,]\d{1,3})?)"
    r"\s*(?:unidades|unidad|uds|ud|u)?\s+(?:de|del)\s+(?P<prod>.+?)"
    rf"(?:\s+en\s+(?:el\s+)?(?:inventario|almacen|stock))?{_CLOSE}$"
)
# separadores (. ' -) solo ENTRE letras/digitos: «harina...», «Madrid.» o «--» no son palabras validas
_PLACE_WORD_RE = re.compile(r"[A-ZÁÉÍÓÚÜÑ]\w*(?:[.'-]\w+)*|\d+[A-Za-z]?")
_PRODUCT_WORD_RE = re.compile(r"\w+(?:[.'-]\w+)*")
_PLACE_PARTICLES = {"de", "del", "la", "las", "los", "el", "y"}


def _words_ok(original: str, max_words: int, word_re: "re.Pattern[str]") -> bool:
    words = original.split()
    if not 1 <= len(words) <= max_words or words[0] in _PLACE_PARTICLES or words[-1] in _PLACE_PARTICLES:
        return False
    for i, w in enumerate(words):
        if i > 0 and w in _PLACE_PARTICLES:
            continue
        if not word_re.fullmatch(w) or fold(w) in _STOP_WORDS:
            return False
    return True


def _num(raw: str) -> Optional[float]:
    v = _to_float(raw)
    return v if v is not None and 0 < v <= 1_000_000 else None


def parse_ops_write(text: str, kind: str) -> Optional[Dict[str, Any]]:
    """Plantilla estricta (ver arriba). kind: "route" | "movement". -> campos o None si no encaja."""
    t = " ".join(unicodedata.normalize("NFKC", text or "").split())
    f = "".join(fold(ch) for ch in t)
    if not t or len(f) != len(t):
        return None
    m = (_ROUTE_TEMPLATE if kind == "route" else _MOV_TEMPLATE).match(f)
    if not m or not _prefix_ok(m.group("prefix"), m.group("verb")):
        return None
    if kind == "route":
        o, d = t[m.start("o"):m.end("o")], t[m.start("d"):m.end("d")]
        ok = _words_ok(o, 5, _PLACE_WORD_RE) and _words_ok(d, 5, _PLACE_WORD_RE)
        return {"origin": o, "destination": d} if ok else None
    prod = t[m.start("prod"):m.end("prod")]
    qty = _num(m.group("qty"))
    if qty is None or not _words_ok(prod, 6, _PRODUCT_WORD_RE):
        return None
    return {"product_text": prod, "quantity": qty, "movement": "in" if m.group("type") == "entrada" else "out"}


_LEGAL_STATUS_RE = re.compile(
    r"\b(?:estado|situacion)\s+(?:legal|juridic[oa]|de\s+cumplimiento|normativ[oa])\b"
    r"|\bdocumentos?\s+legales\b|\bcumplimiento\s+(?:legal|normativo)\b"
)
_AUDIT_RE = re.compile(
    r"\b(?:audit\w*|revis\w*|chequ\w*|comprueb\w*|ejecut\w*|lanz\w*|haz|hacer|pasa)\b.{0,30}?"
    r"\b(?:cumplimiento|compliance|rgpd)\b|\bauditoria\s+de\s+cumplimiento\b"
)
_INVENTORY_RE = re.compile(r"\b(?:inventario|stock|existencias)\b")
_INVENTORY_CUE_RE = re.compile(
    r"\b(?:estado|como\s+(?:esta|va|anda|vamos)|cuanto|cuantos|cuantas|que\s+hay|hay|queda|quedan|bajo|bajos|"
    r"resumen|dame|muestra\w*|ver|revisa\w*|dime|nivel\w*|tengo|tenemos|consulta\w*)\b"
)
_SHIFT_STATUS_RE = re.compile(
    r"\b(?:estado|situacion)\s+de\s+(?:mi|mis|los|el|la)\s+(?:turnos?|fichajes?|jornada)\b"
)


def _is_negated_before(f: str, verb_start: int) -> bool:
    return bool(_NEGATION_BEFORE_RE.search(f[:verb_start]))


def has_negation(message: str) -> bool:
    return bool(_NEGATION_ANY_RE.search(fold(message)))


# Particion en clausulas para detectar varias peticiones en un mismo mensaje.
_CLAUSE_SPLIT_RE = re.compile(
    r"\s+(?:y|e|ademas|tambien|luego|despues|y\s+luego|y\s+despues)\s+|[;?]", re.I
)
_FAMILY = {"tpv_sales_today": "tpv", "tpv_sales_summary": "tpv"}


def _multi_action(text: str) -> List[str]:
    """Familias de intencion DISTINTAS pedidas en clausulas distintas (en orden). Vacio si es una sola."""
    found: List[str] = []
    for clause in _CLAUSE_SPLIT_RE.split(text):
        if not clause or not clause.strip():
            continue
        cf = fold(clause)
        cands = [cd for cd in _candidates(clause, cf, extract_entities(clause)) if cd.base >= 0.72]
        sup: set = set()
        for cd in cands:
            if cd.base >= 0.8:
                sup |= cd.suppresses
        cands = [cd for cd in cands if cd.intent not in sup]
        if not cands:
            continue
        top = max(cands, key=lambda x: x.base).intent
        fam = _FAMILY.get(top, top)
        if fam not in found:
            found.append(fam)
    return found if len(found) >= 2 else []


class _Cand:
    __slots__ = ("intent", "action", "base", "suppresses", "metadata", "fields", "missing", "question", "rule")

    def __init__(self, intent, action, base, rule, *, suppresses=(), metadata=None, fields=None,
                 missing=None, question=None):
        self.intent = intent
        self.action = action
        self.base = base
        self.rule = rule
        self.suppresses = set(suppresses)
        self.metadata = metadata or {}
        self.fields = fields or {}
        self.missing = missing or []
        self.question = question


def looks_like_operational(message: str) -> bool:
    text = (message or "").strip()
    return bool(text and _OPERATIONAL_RE.search(text))


def is_confirmation_message(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    return bool(_CONFIRM_RE.match(text))


def is_affirmative_message(message: str) -> bool:
    """«sí» / «ok» exactos. Solo vale como confirmación si hay un pending (lo decide el orquestador)."""
    return bool(_AFFIRMATIVE_RE.match(message or ""))


def is_cancel_message(message: str) -> bool:
    """«no» / «cancelar» explicitos (frase completa)."""
    return bool(_CANCEL_RE.match(message or ""))


def _extract_discount(text: str) -> Optional[float]:
    m = _DISCOUNT_RE.search(text)
    if not m:
        return None
    for g in m.groups():
        if g:
            v = _to_float(g)
            if v is not None and 0 < v <= 100:
                return v
    return None


def _extract_campaign_name(text: str, discount: Optional[float]) -> str:
    if discount:
        return f"Oferta {int(discount)}% clientes"
    return "Campaña clientes CRM"


def _default_offer_message(discount: Optional[float]) -> str:
    pct = f"{int(discount)}%" if discount else "especial"
    return (
        f"<p>Hola,</p>"
        f"<p>Tenemos una oferta {pct} reservada para ti. "
        f"Contáctanos para activarla antes de que finalice la promoción.</p>"
        f"<p>Saludos,<br/>Tu equipo</p>"
    )


def question_for_customer(name: Optional[str], email: Optional[str]) -> Optional[str]:
    if name and email:
        return None
    if name:
        return (f"¿Cuál es el email de {name}? Con él preparo el alta "
                f"(te pediré confirmación antes de crearlo).")
    if email:
        return f"¿Cómo se llama el cliente con email {email}?"
    return "¿Cómo se llama el cliente y cuál es su email? (ej.: «Ana López, ana@empresa.com»)"


QUESTION_RECIPIENTS = (
    "¿A quién quieres enviarla? Ahora mismo puedo enviarla a todos tus clientes del CRM "
    "(te mostraré la vista previa y pediré confirmación). ¿La envío a todos?"
)
QUESTION_SEGMENT = (
    "Solo puedo enviar campañas a todos los clientes del CRM; no filtro por segmento ni por persona. "
    "¿La envío a todos tus clientes?"
)


def _candidates(text: str, f: str, ent: ZeusEntities) -> List[_Cand]:
    c: List[_Cand] = []
    period = ent.period or {}
    days_p = period.get("days")

    # --- crear cliente (verbo de alta + «cliente», sin objeto de otra cosa entre medias)
    m = _CREATE_CUSTOMER_RE.search(f)
    if m and not _CREATE_CUSTOMER_BLOCK.search(m.group(2) or ""):
        name = ent.names[0] if ent.names else None
        email = ent.emails[0] if ent.emails else None
        missing = [k for k, v in (("name", name), ("email", email)) if not v]
        meta: Dict[str, Any] = {"name": name, "email": email}
        if ent.phones:
            meta["phone"] = ent.phones[0]
        question = question_for_customer(name, email)
        if (
            _is_negated_before(f, m.start(1))
            or not _is_affirmative_request(f, m.start(1), m.group(1))
            or not _is_clean_order(text, True)
        ):
            missing, question = ["explicit_intent"], QUESTION_NEGATED
        c.append(_Cand("create_customer", "create_customer", 0.85, "create_customer",
                       suppresses={"list_customers_summary", "get_metrics", "tpv_sales_summary",
                                   "tpv_sales_today"},
                       metadata=meta, missing=missing, question=question))

    # --- campana: oferta + verbo de envio, sin otros canales
    if _OFFER_RE.search(f) and not _OTHER_CHANNEL_RE.search(f) and _SEND_RE.search(f):
        discount = _extract_discount(text)
        plural = bool(_PLURAL_RECIPIENTS_RE.search(f))
        specific = bool(ent.emails) or (
            not plural and re.search(r"\b(?:a|para)\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+", text) is not None
        )
        segment = bool(_SEGMENT_RE.search(f))
        missing: List[str] = []
        question = None
        verb = _SEND_RE.search(f)
        cverb = _CREATE_RE.search(f)
        first = min((v for v in (verb, cverb) if v), key=lambda v: v.start())
        if (
            _is_negated_before(f, verb.start())
            or (cverb and _is_negated_before(f, cverb.start()))
            or not _is_affirmative_request(f, first.start(), first.group(0))
        ):
            missing, question = ["explicit_intent"], QUESTION_NEGATED
        elif _PARTIAL_RECIPIENTS_RE.search(f[verb.end():]):
            missing, question = ["recipients_scope"], QUESTION_PARTIAL
        elif specific and not plural:
            missing, question = ["recipients"], QUESTION_SEGMENT
        elif segment:
            missing, question = ["recipients_scope"], QUESTION_SEGMENT
        elif not plural:
            missing, question = ["recipients"], QUESTION_RECIPIENTS
        if not missing and not _is_clean_order(text, False):
            missing, question = ["explicit_intent"], QUESTION_NEGATED
        if plural and not missing:
            base = 0.90 if (_CREATE_RE.search(f) or discount) else 0.88
        else:
            base = 0.80
        c.append(_Cand("create_campaign_send", "create_campaign", base, "campaign",
                       suppresses={"list_customers_summary", "get_metrics", "tpv_sales_summary", "tpv_sales_today",
                                   "get_cashflow", "analytics_summary", "create_customer"},
                       fields={"discount_percent": discount,
                               "target": "all_customers",
                               "campaign_name": _extract_campaign_name(text, discount),
                               "message_template": _default_offer_message(discount),
                               "requires_confirmation": True},
                       missing=missing, question=question))

    # --- listar clientes (verbos con limite de palabra: «ver» ya no casa dentro de «convertir»)
    if _LIST_CUSTOMERS_RE.search(f):
        c.append(_Cand("list_customers_summary", "list_customers", 0.85, "list_customers"))

    # --- cashflow: palabra financiera fuerte, o «caja» con cue de estado financiero
    if _CASH_STRONG_RE.search(f):
        c.append(_Cand("get_cashflow", "get_cashflow", 0.85, "cashflow_strong",
                       metadata={"days": days_p or 30}))
    elif _CASH_CUE_RE.search(f):
        c.append(_Cand("get_cashflow", "get_cashflow", 0.80, "cashflow_caja_cue",
                       metadata={"days": days_p or 30}))

    # --- TPV
    sales = bool(_SALES_WORD_RE.search(f))
    caja_today = bool(_CAJA_TODAY_RE.search(f))
    if (sales and _TODAY_RE.search(f)) or caja_today:
        base = 0.88 if sales else 0.75
        c.append(_Cand("tpv_sales_today", "tpv_sales_summary", base, "tpv_today",
                       suppresses={"tpv_sales_summary"}, metadata={"period": "today", "days": 1}))
    elif sales:
        label = period.get("label")
        unsupported = label in ("yesterday", "previous_week", "previous_month", "custom")
        base = 0.82 if (period or _TPV_QUERY_RE.search(f)) else 0.72
        c.append(_Cand(
            "tpv_sales_summary", "tpv_sales_summary", base, "tpv_summary",
            metadata={"days": days_p or 7},
            missing=["supported_period"] if unsupported else [],
            question=("Solo puedo resumir las ventas de los últimos N días (hoy, 7, 30…), no de un día o "
                      "mes concreto. ¿Te sirven los últimos 7 días o los últimos 30?") if unsupported else None,
        ))

    # --- analytics vs metricas
    if _ANALYTICS_RE.search(f):
        c.append(_Cand("analytics_summary", "analytics_summary", 0.82, "analytics",
                       suppresses={"get_metrics"}, metadata={"days": days_p or 30}))
    elif _METRICS_STRONG_RE.search(f):
        c.append(_Cand("get_metrics", "get_metrics", 0.80 if _METRICS_CUE_RE.search(f) else 0.78,
                       "metrics_strong", metadata={"days": days_p or 30}))
    elif _METRICS_WEAK_RE.search(f):
        base = 0.80 if _METRICS_CUE_RE.search(f) else 0.68  # palabra suelta («ingreso») NO basta
        c.append(_Cand("get_metrics", "get_metrics", base, "metrics_weak", metadata={"days": days_p or 30}))

    # --- J9e: AFRODITA ruta / movimiento (escrituras: plantilla estricta o pregunta, nunca por defecto)
    ops_write = False
    for kind, trig, intent in (("route", _ROUTE_TRIGGER_RE, "create_ops_route"),
                               ("movement", _MOV_TRIGGER_RE, "create_inventory_movement")):
        if trig.search(f):
            fields_ = parse_ops_write(text, kind)
            ops_write = True
            c.append(_Cand(
                intent, intent, 0.85, intent,
                suppresses={"list_customers_summary", "get_metrics", "tpv_sales_summary", "tpv_sales_today",
                            "get_inventory_status", "shift_status", "get_legal_status", "run_compliance_audit"},
                metadata=fields_ or {}, fields={"requires_confirmation": True},
                missing=[] if fields_ else ["explicit_intent"], question=None if fields_ else QUESTION_OPS,
            ))

    # --- J9e: JUSTICIA consultas
    if _LEGAL_STATUS_RE.search(f):
        c.append(_Cand("get_legal_status", "get_legal_status", 0.85, "legal_status"))
    ma = _AUDIT_RE.search(f)
    if ma:
        neg = _is_negated_before(f, ma.start()) or _NEGATION_ANY_RE.search(f[:ma.start()]) is not None
        c.append(_Cand("run_compliance_audit", "run_compliance_audit", 0.85, "compliance_audit",
                       missing=["explicit_intent"] if neg else [], question=QUESTION_NEGATED if neg else None))

    # --- J9e: AFRODITA consultas (inventario; turnos ya cubiertos por shift_status)
    if not ops_write and _INVENTORY_RE.search(f):
        c.append(_Cand("get_inventory_status", "get_inventory_status",
                       0.82 if _INVENTORY_CUE_RE.search(f) else 0.68, "inventory_status"))

    # --- turno
    if _SHIFT_RE.search(f) or _SHIFT_STATUS_RE.search(f):
        c.append(_Cand("shift_status", "shift_status", 0.85, "shift"))
    return c


def parse_intent(message: str) -> ZeusTaskObject:
    """Comprension estructurada del mensaje (ver criterio de confianza arriba)."""
    text = (message or "").strip()

    if is_confirmation_message(text):
        return ZeusTaskObject(
            intent="confirm_pending", action="confirm_pending", raw_message=text, confidence=0.95,
            confidence_breakdown={"rule": "confirm_exact", "base": 0.95},
        )

    f = fold(text)
    ent = extract_entities(text)
    urgency = detect_urgency(text)
    cands = _candidates(text, f, ent)

    # H3: varias peticiones distintas en un mensaje: se avisa y se pregunta cual primero; no se
    # ejecuta ni se prepara ninguna (antes la mas fuerte suprimia a la otra en silencio).
    multi = _multi_action(text)
    if multi:
        parts = " y ".join(INTENT_LABELS.get(i, i) for i in multi)
        first = "tpv_sales_summary" if multi[0] == "tpv" else multi[0]
        return ZeusTaskObject(
            intent=first, raw_message=text, confidence=0.8, entities=ent, urgency=urgency,
            needs_clarification=True, missing_entities=["single_action"],
            clarification_question=QUESTION_MULTI.format(parts=parts),
            confidence_breakdown={"rule": "multi_action", "actions": multi},
        )

    # Supresion por dominancia (una intencion fuerte explica a otras: «campaña para aumentar ventas»).
    suppressed: set = set()
    for cd in cands:
        if cd.base >= 0.8:
            suppressed |= cd.suppresses
    cands = [cd for cd in cands if cd.intent not in suppressed]
    cands.sort(key=lambda x: -x.base)

    if not cands:
        return ZeusTaskObject(
            intent="unknown", raw_message=text, confidence=0.0, entities=ent, urgency=urgency,
            confidence_breakdown={"rule": "no_match"},
        )

    best = cands[0]
    rivals = [cd for cd in cands[1:] if best.base - cd.base <= AMBIGUITY_MARGIN and cd.intent != best.intent]
    required = best.intent in ("create_customer", "create_campaign_send", "create_ops_route",
                               "create_inventory_movement")
    bonus = REQUIRED_PRESENT_BONUS if (required and not best.missing) else 0.0
    penalty = AMBIGUITY_PENALTY if rivals else 0.0
    conf = round(max(0.0, min(CONFIDENCE_CAP, best.base + bonus - penalty)), 2)
    breakdown = {"rule": best.rule, "base": best.base, "required_entities_bonus": bonus,
                 "ambiguity_penalty": -penalty, "competing": [r.intent for r in rivals]}

    task = ZeusTaskObject(
        intent=best.intent, action=best.action, raw_message=text, confidence=conf,
        metadata=dict(best.metadata), entities=ent, urgency=urgency,
        missing_entities=list(best.missing), ambiguous_with=[r.intent for r in rivals],
        confidence_breakdown=breakdown, **best.fields,
    )
    if rivals:
        labels = [INTENT_LABELS.get(best.intent, best.intent)] + [
            INTENT_LABELS.get(r.intent, r.intent) for r in rivals
        ]
        task.needs_clarification = True
        task.clarification_question = "No tengo claro qué necesitas: ¿" + " o ".join(labels) + "?"
    elif best.missing:
        task.needs_clarification = True
        task.clarification_question = best.question
    return task


_UNKNOWN_HINTS = (
    (r"\bcaja\b", "¿Quieres las ventas de caja del TPV o el estado de tesorería (cashflow)?"),
    (r"\bclientes?\b",
     "¿Quieres saber cuántos clientes tienes, crear uno nuevo (necesito nombre y email) o enviarles una campaña?"),
    (r"\b(venta|ventas|tpv)\b", "¿De qué periodo quieres las ventas: hoy, últimos 7 días o últimos 30?"),
    (r"\b(turno|jornada|fichaje)\b", "¿Quieres saber si tienes un turno activo?"),
    (r"\b(campana|oferta|descuento|promocion|promo|envia|mandar)\b",
     "¿Quieres enviar una oferta a todos tus clientes? Dime el descuento (ej. «envía oferta 10% a clientes»)."),
    (r"\bimportar\b", "¿Qué quieres importar? Hoy se hace desde el módulo de importación del CRM."),
)


def is_conversational_request(message: str) -> bool:
    """Peticion de redaccion/consejo/explicacion o texto largo: va al LLM conversacional, no se interroga."""
    f = fold(message)
    return len(f) > 280 or bool(_CONVERSATIONAL_RE.search(f))


def clarification_for_unknown(message: str) -> str:
    """Pregunta CONCRETA para un mensaje de apariencia operativa que no se pudo clasificar."""
    f = fold(message)
    hints = [h for pat, h in _UNKNOWN_HINTS if re.search(pat, f)]
    if hints:
        return "No he podido entender qué acción quieres. " + hints[0]
    return ("No he podido entender qué acción quieres. ¿Es sobre clientes, ventas del TPV, caja, "
            "turnos o una campaña?")
