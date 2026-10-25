"""Bloqueo honesto del chat (ZEUS/JARVIS y workspaces de agente): ordenes de ANULAR, CANCELAR, BORRAR, QUITAR,
DAR DE BAJA, INVALIDAR, SUPRIMIR, DEJAR SIN EFECTO, RECTIFICAR, MODIFICAR o FIRMAR una factura de la empresa.

Que existe hoy en el backend (revisado antes de decidir):
  - No hay ninguna accion de chat sobre facturas (ni en `CONFIRMABLE_ACTIONS` ni en el ejecutor de agentes).
  - `POST /invoices/{id}/void` (REST, con THALOS) solo anula BORRADORES. Una factura ya EMITIDA (enviada,
    pagada, pagada en parte, vencida) se rechaza con 409 sin tocar nada: en España una factura emitida no se
    borra ni se anula, se corrige con una factura rectificativa que la referencie (Reglamento de facturacion,
    RD 1619/2012, art. 15). El chat no se engancha a ese endpoint (decision pendiente del titular): el texto
    fijo de abajo no promete ninguna anulacion.
  - No existe endpoint para borrar facturas (tampoco borradores: la serie debe ser correlativa y sin huecos),
    ni para emitir rectificativas (el tipo `credit_note` existe en el modelo, sin flujo), ni para firmarlas:
    la firma/huella de Verifactu no esta implementada (`jarvis_legal_block`, zeus-guardarrailes-legales).
Por eso una orden asi NO se contesta con una lectura («cancela la última factura» no enseña la última factura)
ni la decide el modelo conversacional (podria contestar que ya esta anulada): texto fijo con el motivo, sin
ejecutar nada. Mismo patron que `jarvis_legal_block` y `jarvis_schedule_write_block`.

Hace falta, en la misma clausula:
  - una ORDEN al inicio de clausula (imperativo, o «quiero que / puedes / necesito… + verbo»), con el mismo
    arranque `_LEAD` que el bloqueo legal. «¿cómo se anula una factura?», «¿puedo anular una factura emitida?»,
    «explícame cómo rectificar una factura» y las PREGUNTAS «¿hay que / tienes que firmar las facturas?» no son
    ordenes y siguen su camino como antes («hay que anular la factura 23», sin interrogacion, si es orden);
  - la FACTURA como objeto directo del verbo, con contexto POSITIVO de que es una factura de la empresa:
    «la última factura», «esta/esa factura», «todas las facturas», o «la factura» / «las facturas» seguidas de
    nada, de un número («F-2026-0001», «23», «nº 5»), de un complemento de tiempo («de ayer», «que hice ayer»,
    «emitida») o de un cliente («del cliente Pepe», «de Juan Pérez» con el nombre en mayúscula en el mensaje).
    «anula la factura de la luz», «cancela la factura del gas» no tienen ese contexto: no se bloquean aqui;
  - o «pon/marca la factura 23 como anulada», o pedir una factura RECTIFICATIVA;
  - o, SIN la palabra «factura» («anula la última», «anula la nº 23», «cancélala», «bórrala»), solo si el
    contexto es de facturas: el mismo mensaje habla de facturas («facturas de ayer, anula la 23»), es el chat de
    RAFAEL, o el turno anterior del mismo hilo del chat de ZEUS fue una lectura de facturas (`invoice_context`,
    lo decide quien llama). Sin ese contexto no se sabe qué es «la última»: sigue su camino como antes.
Antes de mirar la orden se quitan las muletillas iniciales («no,», «no sé,», «bueno,»): «no, cancela la última
factura» es una orden. La NEGACION de la propia orden («no canceles la factura», «para, no anules la 23»,
«no quiero que anules…») no ejecuta ni bloquea: `invoice_order_check` devuelve "negated" y quien llama responde
con un texto fijo (sin modelo).
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

from services.intent_parser import fold
from services.jarvis_legal_block import _LEAD  # mismo arranque de orden que el bloqueo legal

_CLAUSE = r"[^.?!;\n]"
_VOID_VERB = (
    r"anul(?:a|ar|es|ala|alas|ame|amela|amelas)|cancel(?:a|ar|es|ala|alas|ame|amela|amelas)|"
    r"borr(?:a|ar|es|ala|alas|ame|amela|amelas)|elimin(?:a|ar|es|ala|alas|ame|amela|amelas)|"
    r"quit(?:a|ar|es|ala|alas|ame|amela|amelas)|invalid(?:a|ar|es|ala|alas|ame)|"
    r"suprim(?:e|ir|as|ela|elas|eme)|tir(?:a|ar|es|ala|alas)|"
    r"(?:da|dale|dales|dar|darle|des|le\s+des)\s+de\s+baja(?:\s+a)?|dej(?:a|ar|es|ala|alas)\s+sin\s+efecto"
)
_RECTIFY_VERB = (
    r"rectific(?:a|ar|ala|alas|ame|amela)|rectifiques|corrig(?:e|ela|elas|eme|emela)|corregir|corrijas|"
    r"modific(?:a|ar|ala|alas|ame)|modifiques|edit(?:a|ar|es|ala|alas|ame)|cambi(?:a|ar|es|ala|alas|ame)"
)
_SIGN_VERB = r"firm(?:a|ar|es|ala|alas|ame|amela|amelas)"
_ANY_VERB = rf"(?:{_VOID_VERB}|{_RECTIFY_VERB}|{_SIGN_VERB})"
_REASON_BY_GROUP = {"void": "invoice_void", "rectify": "invoice_rectify", "sign": "invoice_sign"}
_ORDER_RE = re.compile(
    _LEAD + rf"(?:(?P<void>{_VOID_VERB})|(?P<rectify>{_RECTIFY_VERB})|(?P<sign>{_SIGN_VERB}))\b"
    rf"(?P<rest>{_CLAUSE}*)"
)
# «pon / marca / deja la factura 23 como anulada»
_MARK_RE = re.compile(
    _LEAD + r"(?:pon|ponme|poner|pongas|ponla|marca|marcar|marques|marcala|deja|dejar|dejes)\b"
    rf"(?P<rest>{_CLAUSE}*?)\bcomo\s+(?P<state>anulad[ao]s?|cancelad[ao]s?|borrad[ao]s?|eliminad[ao]s?|"
    r"invalid[ao]s?|nul[ao]s?|de\s+baja|sin\s+efecto|rectificad[ao]s?|firmad[ao]s?)\b"
)
# Objeto directo: determinantes/adverbios y luego «factura(s)» (no «factura de la luz»: ver _POSITIVE_AFTER)
_OBJECT_RE = re.compile(
    # «modifica EL IMPORTE DE la factura 23»: un dato de la factura tambien es la factura
    r"^\s*(?:(?:el|la|los|las)\s+(?:importe|total|iva|fecha|cliente|concepto|conceptos|precio|precios|nif|cif|"
    r"direccion|datos|linea|lineas|descuento)\s+(?:de|del)\s+)?"
    r"(?:(?:la|las|el|los|una|unas|un|esa|esas|esta|estas|aquella|aquellas|dicha|dichas|mi|mis|tu|tus|"
    r"nuestra|nuestras|todas|ultima|ultimas|digitalmente|electronicamente|ya|ahora|tambien|me|nos|por\s+favor)"
    r"\s+){0,4}?(?P<pre>(?:\w+\s+)?)facturas?\b(?P<after>" + _CLAUSE + r"*)"
)
_POSITIVE_BEFORE = re.compile(r"\b(?:ultimas?|esas?|estas?|aquellas?|dichas?|todas)\s+(?:(?:las|mis)\s+)?$")
_COURTESY_TAIL = re.compile(r"^\s*(?:(?:por\s+favor|porfa|ya|ahora(?:\s+mismo)?|de\s+una\s+vez)\s*)*[,!]*\s*$")
_ID = r"(?:(?:n|no|num|numero)\s*[.º°]?\s*)?[\w/-]*\d[\w/-]*"
_TIME_C = (r"(?:de|del)\s+(?:hoy|ayer|antes\s+de\s+ayer|anteayer|esta\s+semana|la\s+semana(?:\s+pasada)?|"
           r"este\s+mes|el\s+mes\s+pasado|mes(?:\s+pasado)?|este\s+trimestre|este\s+ano|\d)")
_DID = r"que\s+(?:he|hemos|has|hice|hicimos|emiti|emitimos|mande|mandamos|envie|enviamos|cree|creamos)\b"
_POSITIVE_AFTER = re.compile(
    r"^\s*(?:"
    + _ID +  # identificador: «F-2026-0001», «23», «nº 5», «numero 12»
    r"|mas\s+reciente|anterior|emitidas?|" + _DID +  # «que he emitido», «que hice ayer»
    r"|" + _TIME_C +
    r"|(?:de|del|a|al|para)\s+(?:(?:mi|el|la|nuestro|nuestra)\s+)?client[ea]s?\b"  # cliente explicito
    r")"
)
# «de/a/para + Nombre propio» sobre el texto ORIGINAL (cliente con nombre en mayúscula): «la factura de Juan Pérez»
_NAMED_CUSTOMER_RE = re.compile(r"^\s*(?:de|del|a|al|para)\s+[A-ZÁÉÍÓÚÑ][\wáéíóúñü]+")
_RECTIFICATIVA_RE = re.compile(
    _LEAD + r"(?:haz|hazme|hacer|hacerme|hagas|crea|creame|crear|crees|genera|generame|generar|generes|emite|"
    r"emiteme|emitir|emitas|prepara|preparame|preparar)\b" + _CLAUSE + r"{0,25}?\brectificativas?\b"
)
# Sin «factura» (solo con contexto de facturas). La referencia es TODO lo que sigue al verbo (anclada al final,
# admitiendo cortesia): «anula la última», «anula la 23», «anula la de ayer»; «cancela la última cita», «anula la
# última reserva», «quita 10 euros del total», «cambia 2024 por 2025» no lo son (sobra o falta algo).
_END = r"(?:\s*,?\s*(?:por\s+favor|porfa|gracias|ya|ahora(?:\s+mismo)?))*\s*[,!]*\s*$"
_ART = r"^\s*(?:tambien\s+)?(?:la|las|esa|esas|esta|estas)\s+"
# Identificador EXPLICITO de factura: «la nº 23», «la número 23», «la F-23», «la F-2026-0001»
_EXPLICIT_ID = r"(?:(?:n|no|num|numero)\s*[.º°]?\s*\d[\w/-]*|[a-z]{1,4}-\d[\w/-]*)"
# Verbos propios de una factura (anular, cancelar, invalidar, dar de baja, dejar sin efecto, rectificar, firmar):
# admiten «la última», «la anterior», «la 23», «la de ayer», «la que hice ayer» y el identificador explicito.
_PRONOUN_STRONG_RE = re.compile(
    _ART + r"(?:ultimas?(?:\s+emitidas?)?|anterior|\d+|" + _EXPLICIT_ID + r"|" + _TIME_C + r"|"
    r"que\s+(?:he|hemos|has|hice|hicimos|emiti|emitimos)\b[^,]*?)" + _END
)
# Verbos genericos (borrar, quitar, eliminar, tirar, suprimir, cambiar, modificar, editar, corregir): «borra la 3»,
# «quita la última», «elimina la anterior», «borra la de ayer» pueden ser cualquier cosa -> solo el identificador
# explicito de factura («borra la nº 23», «borra la F-23»).
_PRONOUN_WEAK_RE = re.compile(_ART + _EXPLICIT_ID + _END)
_STRONG_VERB_RE = re.compile(
    r"^(?:anul|cancel|invalid|rectific|firm)\w*$|^(?:da|dale|dales|dar|darle|des|le\s+des)\s+de\s+baja|^dej"
)
# «cancélala», «bórrala», «anúlamela» (no «cancela»: el pronombre va DESPUES de la terminacion del verbo)
_CLITIC_RE = re.compile(
    r"^(?:(?:anul|cancel|borr|elimin|quit|invalid|tir|firm|rectific|modific|edit|cambi)alas?|"
    r"(?:suprim|corrig)elas?|\w+amelas?|\w+emelas?)$"
)
_INVOICE_NOUN_RE = re.compile(r"\bfacturas?\b")
# Preguntas «¿hay que / tienes que firmar las facturas?»: no son ordenes (el arranque _LEAD si las admite)
_DUTY_LEAD_RE = re.compile(r"\b(?:hay|tienes|tengo|tenemos)\s+que\b")

_ME_PUEDES_RE = re.compile(r"\b(me|nos)\s+(puedes|podrias)\b")
# Muletillas iniciales que NO niegan la orden: «no, cancela…», «no sé, anula…», «bueno, borra…»
_INTERJECTION_RE = re.compile(
    r"^\s*(?:(?:no|no\s+se|bueno|vale|vaya|venga|oye|eh|ah|uf|mm+|pues)\s*[,.;:!]+\s*)+"
)
# Negacion PEGADA al verbo de la orden («no canceles», «nunca firmes», «no me la anules», «no quiero que anules»)
_NEG_ADJ_RE = re.compile(
    r"\b(?:no|nunca|jamas)\s+(?:(?:quiero|quisiera|necesito)\s+que\s+)?"
    rf"(?P<pron>(?:(?:me|nos|la|las|lo|le|les|se)\s+){{0,2}})(?={_ANY_VERB}\b)"
)
_NEG_CLITIC_RE = re.compile(r"\b(?:la|las)\b")

MSG_INVOICE_VOID = (
    "Desde el chat no puedo anular, cancelar ni borrar facturas: no existe esa acción en RAFAEL, así que no he "
    "tocado ninguna factura. Además, una factura ya emitida no se borra ni se anula sin más: se corrige con una "
    "factura rectificativa que la referencie, y ZEUS todavía no emite rectificativas. Hazlo con tu gestor o tu "
    "programa de facturación. Si quieres, te enseño la factura: pídeme «¿cuál es mi última factura?»."
)
MSG_INVOICE_RECTIFY = (
    "Desde el chat no puedo rectificar ni modificar facturas: ZEUS todavía no emite facturas rectificativas, así "
    "que no he tocado ninguna factura. Una factura emitida se corrige con una rectificativa que la referencie; "
    "hazla con tu gestor o tu programa de facturación. Si quieres, te enseño la factura: pídeme «¿cuál es mi "
    "última factura?»."
)
MSG_INVOICE_SIGN = (
    "No puedo firmar facturas: ZEUS todavía no está adaptado a Verifactu (huella encadenada, QR y registro "
    "oficial) ni firma facturas electrónicamente, así que no he firmado nada. Puedes consultar tus facturas aquí "
    "y descargarlas para tu gestor."
)
MSG_INVOICE_NEGATED = "Entendido: no toco ninguna factura. No he hecho nada."
_MSG_BY_REASON = {"invoice_void": MSG_INVOICE_VOID, "invoice_rectify": MSG_INVOICE_RECTIFY,
                  "invoice_sign": MSG_INVOICE_SIGN}


def _blank(f: str, start: int, end: int) -> str:
    """Sustituye f[start:end] por espacios terminados en «,» (frontera de clausula para `_LEAD`): el texto original
    sigue alineado con `f` (mismo largo)."""
    if end <= start:
        return f
    return f[:start] + " " * (end - start - 1) + "," + f[end:]


def _normalize(message: str) -> Tuple[str, str]:
    """(texto original con espacios normalizados, texto plegado alineado con el original y sin muletillas)."""
    text = " ".join((message or "").split())
    f = fold(text)
    if len(f) != len(text):  # `fold` solo quita marcas combinantes; si no, no se usa el original (sin nombres)
        text = f
    mi = _INTERJECTION_RE.match(f)
    if mi:
        f = _blank(f, 0, mi.end())
    # «¿me puedes anular…?» = «¿puedes anular…?»
    f = _ME_PUEDES_RE.sub(lambda m: m.group(2) + " " * (len(m.group(1)) + 1), f)
    return text, f


def _is_company_invoice(text: str, rest_start: int, rest: str) -> bool:
    mo = _OBJECT_RE.match(rest)
    if mo is None:
        return False
    head = rest[:mo.start("after")]
    after = mo.group("after")
    if _POSITIVE_BEFORE.search(head[:head.rfind("factura")]):
        return True
    if _COURTESY_TAIL.match(after) or _POSITIVE_AFTER.match(after):
        return True
    return bool(_NAMED_CUSTOMER_RE.match(text[rest_start + mo.start("after"):]))


def _is_duty_question(f: str, m: "re.Match[str]", verb_start: int) -> bool:
    """«¿hay que firmar las facturas?»: arranque «hay/tienes que» en una clausula interrogativa."""
    if not _DUTY_LEAD_RE.search(f[m.start():verb_start]):
        return False
    return "¿" in f[max(0, m.start() - 1):verb_start] or f[m.end():m.end() + 1] == "?"


def _pronoun_ref(verb: str, rest: str) -> bool:
    """Referencia a una factura SIN la palabra «factura» (solo se mira con contexto de facturas)."""
    rx = _PRONOUN_STRONG_RE if _STRONG_VERB_RE.match(verb) else _PRONOUN_WEAK_RE
    return bool(rx.match(rest))


def _block_folded(text: str, f: str, invoice_context: bool) -> Optional[Tuple[str, str]]:
    if _RECTIFICATIVA_RE.search(f):
        return "invoice_rectify", MSG_INVOICE_RECTIFY
    # el propio mensaje habla de facturas («facturas de ayer, anula la 23») = contexto de facturas
    ctx = invoice_context or bool(_INVOICE_NOUN_RE.search(f))
    for m in _ORDER_RE.finditer(f):
        group = next(g for g in ("void", "rectify", "sign") if m.group(g))
        if _is_duty_question(f, m, m.start(group)):
            continue
        rest = m.group("rest")
        ok = _is_company_invoice(text, m.start("rest"), rest)
        if not ok and ctx:
            ok = _pronoun_ref(m.group(group), rest) or (
                bool(_CLITIC_RE.search(m.group(group))) and bool(re.match(_END, rest)))
        if ok:
            reason = _REASON_BY_GROUP[group]
            return reason, _MSG_BY_REASON[reason]
    for m in _MARK_RE.finditer(f):
        if _is_company_invoice(text, m.start("rest"), m.group("rest")) or (
                ctx and _PRONOUN_STRONG_RE.match(m.group("rest"))):
            st = m.group("state")
            reason = ("invoice_sign" if st.startswith("firmad") else
                      "invoice_rectify" if st.startswith("rectificad") else "invoice_void")
            return reason, _MSG_BY_REASON[reason]
    return None


def invoice_write_block(message: str, invoice_context: bool = False) -> Optional[Tuple[str, str]]:
    """(motivo, mensaje) si el mensaje es una ORDEN (no negada) de anular/cancelar/borrar/rectificar/modificar/
    firmar una factura de la empresa; si no, None. `invoice_context`: el contexto es de facturas (chat de RAFAEL o
    turno anterior de facturas) y cuentan las ordenes sin la palabra «factura» («anula la última»)."""
    text, f = _normalize(message)
    if not f.strip():
        return None
    return _block_folded(text, f, invoice_context)


def negated_invoice_order(message: str, invoice_context: bool = False) -> bool:
    """True si el mensaje es una orden sobre una factura de la empresa (mismo criterio que
    `invoice_write_block`) NEGADA junto al verbo («no canceles la factura», «para, no anules la 23»). «no sé, anula
    la factura 23» o «no, cancela la última factura» no son negaciones de la orden (muletilla inicial)."""
    text, f = _normalize(message)
    found = list(_NEG_ADJ_RE.finditer(f))
    if not found:
        return False
    # «no me la anules» con contexto de facturas: el «la» es la factura de la que se habla
    if invoice_context and any(_NEG_CLITIC_RE.search(m.group("pron")) for m in found):
        return True
    spans = [(m.start(), m.end()) for m in found]  # se quitan negacion y pronombres: «no me anules» -> «anules»
    for s, e in spans:
        f = _blank(f, s, e)
    return _block_folded(text, f, invoice_context) is not None


def invoice_order_check(message: str, invoice_context: bool = False) -> Optional[Tuple[str, str, str]]:
    """Orden sobre facturas -> ("block", motivo, mensaje); la misma orden negada -> ("negated", "negated",
    mensaje fijo); si no, None. Primero la negacion (una orden negada nunca se bloquea como si fuera orden)."""
    if negated_invoice_order(message, invoice_context):
        return "negated", "negated", MSG_INVOICE_NEGATED
    blk = invoice_write_block(message, invoice_context)
    if blk is not None:
        return "block", blk[0], blk[1]
    return None
