"""Bloqueo honesto del chat (ZEUS/JARVIS y workspace de AFRODITA): ordenes de CREAR, CAMBIAR, BORRAR,
ASIGNAR o ENVIAR horarios, turnos o cuadrantes de LA PLANTILLA.

No existe una accion de chat que guarde horarios (`employee_schedules` se edita en Control horario). Una
orden asi NO se contesta con la lectura del cuadrante ni la decide el modelo conversacional (que podria
contestar que ya lo ha cambiado): se responde con un texto fijo que dice el motivo, sin ejecutar nada.
Mismo patron que `jarvis_legal_block`.

Hace falta, en la misma frase, una ORDEN (verbo de escritura + cuadrante/horario/turno, «…cuadrante… y
mándaselo», o «pon a Ana de tarde») Y un CONTEXTO DE PLANTILLA positivo:
  - «cuadrante(s)», o «turnos» en plural suelto o con complemento de tiempo/plantilla («de esta semana»,
    «de los camareros», «de Ana»; no «de caja», «de reservas»…; el singular no basta), o
  - «horario(s)/turno(s)» junto a «empleado(s)», «plantilla», «personal», «equipo», «camarero(s)»…, o
  - el nombre de un empleado activo de la empresa (`names`, leido de la BD por quien llama), o
  - «pon/cambia/pasa a <Nombre propio> de mañana/tarde/noche» (nombre en mayúscula en el mensaje).
Sin ese contexto («cambia el turno de caja», «envía el horario de verano a los clientes», «mete el pedido en
el turno de tarde») no es este bloqueo: el mensaje sigue su camino como antes.

Criterio LECTURA vs ORDEN para el cuadrante:
  - «hazme / móntame / prepárame / sácame / pásame / enséñame el cuadrante» = ENSEÑAR el cuadrante con los
    turnos guardados -> lectura (`get_staff_schedule`), que pide el dato si falta. No se bloquea.
  - crear, generar, rehacer, organizar, planificar, distribuir, repartir o asignar turnos, o pedir uno
    NUEVO/OTRO («hazme un cuadrante nuevo») = producir y GUARDAR un reparto distinto -> no hay accion que lo
    guarde: bloqueo honesto.
  - «haz uno nuevo» sin nombrar cuadrante/turnos no tiene contexto de plantilla en el propio mensaje: no se
    bloquea (sigue al modelo como cualquier frase sin intencion reconocida).
Las negaciones y las ordenes de parada las filtra quien llama (igual que el bloqueo legal).
"""

from __future__ import annotations

import re
from typing import Callable, Iterable, Optional, Tuple, Union

from services.intent_parser import STAFF_ROLE_ALT, fold, turnos_staff_context

_NOUN = r"(?:cuadrantes?|turnos?|horarios?)"
# Imperativo (+ enclitico), infinitivo y subjuntivo («quiero que borres…»). «mándame/envíame/pásame» (a mí)
# son peticiones de VER el cuadrante, no ordenes de enviarlo a terceros: no estan.
_VERB = (
    r"(?:borr(?:a|ar|es|alo|ala|alos|alas)|elimin(?:a|ar|es|alo|ala|alos|alas)|quit(?:a|ar|es|alo|ala|ale|ales)|"
    r"cambi(?:a|ar|es|alo|ala|ale|ales)|modific(?:a|ar|alo|ala)|modifiques|muev(?:e|es|elo|ela)|mover|"
    r"asign(?:a|ar|es|ale|ales)|cre(?:a|ar|es|alo|ala)|creame|anad(?:e|ir|as|ele|eles)|agreg(?:a|ar|ale|ales)|"
    r"agregues|mete|meter|metas|metele|guard(?:a|ar|es|alo|ala)|actualiz(?:a|ar|alo|ala)|actualices|"
    r"edit(?:a|ar|es|alo|ala)|cancel(?:a|ar|es|alo|ala)|envi(?:a|ar|es|alo|ala|aselo|aselos)|"
    r"mand(?:a|ar|es|alo|ala|aselo|aselos)|programa|programar|programes|apunt(?:a|ar|es|ale|ales)|"
    # producir un reparto nuevo (ver criterio arriba)
    r"gener(?:a|ar|es|alo|ala|ame)|organiz(?:a|ar|alo|ala|ame)|organices|planific(?:a|ar|alo|ala|ame)|"
    r"planifiques|distribu(?:ye|ir|yas|yelo|yela)|rehaz|rehazlo|rehazla|rehacer|rehagas|"
    r"repart(?:e|ir|as|elo|ela))"
)
# «hazme/haz/móntame… un cuadrante NUEVO / OTRO cuadrante»: pedir un reparto distinto, no enseñar el guardado.
_NEW_RE = re.compile(
    r"\b(?:haz|hazme|hacer|hacerme|hagas|monta|montame|montar|prepara|preparame|preparar)\b[^.?!;\n]{0,40}?"
    r"(?:\b(?:otro|otra|otros|otras)\s+" + _NOUN + r"\b|\b" + _NOUN + r"\b[^.?!;\n]{0,15}?\b(?:nuevos?|nuevas?|distint[oa]s?)\b)"
)
_STAFF_WORD_RE = re.compile(rf"\b(?:{STAFF_ROLE_ALT})\b")  # misma lista que la lectura (intent_parser)
# «cuadrante(s)» siempre es de la plantilla. «turnos» (plural) solo con el criterio compartido con la lectura
# (`intent_parser.turnos_staff_context`: suelto o con complemento de tiempo/plantilla; «turnos de caja», «de
# reservas», «de reparto»… no). El singular («el turno de caja», «el turno de tarde») no basta por si solo.
_CUADRANTE_RE = re.compile(r"\bcuadrantes?\b")
_TURNOS_RE = re.compile(r"\bturnos\b")
_CLAUSE = r"[^.?!;\n]"
_VERB_NOUN_RE = re.compile(rf"\b{_VERB}\b{_CLAUSE}{{0,50}}?\b{_NOUN}\b")
_NOUN_THEN_SEND_RE = re.compile(rf"\b{_NOUN}\b{_CLAUSE}{{0,60}}?\b(?:y|luego|despues)\s+{_VERB}\b")
# «pon a Ana de tarde», «pasa a Carlos al turno de noche»: sobre el texto ORIGINAL (nombre en mayúscula).
_PUT_SHIFT_RE = re.compile(
    r"\b(?:[Pp]on|[Pp]onle|[Pp]onme|[Pp]oner|[Pp]ongas|[Cc]ambia|[Cc]ambiale|[Cc]ámbiale|[Pp]asa|[Pp]ásale|"
    r"[Pp]asale|[Mm]ueve)\s+a\s+(?P<name>[A-ZÁÉÍÓÚÑ][\wáéíóúñü]+(?:\s+[A-ZÁÉÍÓÚÑ][\wáéíóúñü]+)?)\s+"
    r"(?:de|en\s+el\s+turno\s+de|al\s+turno\s+de|a\s+la|al)\s+(?:mañana|manana|tarde|noche|partido)\b"
)

MSG_SCHEDULE_WRITE = (
    "Desde el chat no puedo crear, cambiar, borrar, asignar ni enviar horarios o cuadrantes: no existe esa "
    "acción en AFRODITA, así que no se ha modificado ningún horario. Los turnos de cada empleado se guardan "
    "en Control horario (empleado, días y horas). Si quieres, te enseño el cuadrante actual: pídeme "
    "«cuadrante de la semana»."
)

Names = Union[None, Iterable[str], Callable[[], Iterable[str]]]


def _name_tokens(names: Names) -> set:
    """Nombres de empleados activos (completo y nombre de pila, sin acentos/mayúsculas; mín. 3 letras)."""
    if names is None:
        return set()
    raw = names() if callable(names) else names
    out: set = set()
    for n in raw or ():
        full = fold(" ".join(str(n or "").split()))
        if len(full) >= 3:
            out.add(full)
            first = full.split(" ")[0]
            if len(first) >= 3:
                out.add(first)
    return out


def _sentence(f: str, pos: int) -> str:
    start = max(f.rfind(c, 0, pos) for c in ".?!;\n") + 1
    ends = [i for i in (f.find(c, pos) for c in ".?!;\n") if i != -1]
    return f[start:min(ends) if ends else len(f)]


def _staff_context(sentence: str, tokens: Callable[[], set]) -> bool:
    if _CUADRANTE_RE.search(sentence) or _STAFF_WORD_RE.search(sentence):
        return True
    # «turnos» en plural: mismo criterio que la lectura (suelto o con complemento de tiempo/plantilla)
    if any(turnos_staff_context(sentence[m.end():], tokens()) for m in _TURNOS_RE.finditer(sentence)):
        return True
    return any(re.search(rf"\b{re.escape(t)}\b", sentence) for t in tokens())


def schedule_write_block(message: str, names: Names = None) -> Optional[Tuple[str, str]]:
    """(motivo, mensaje) si el mensaje es una ORDEN de escribir horarios/turnos/cuadrantes de la plantilla;
    si no, None. `names`: nombres de los empleados activos de la empresa (lista o funcion perezosa)."""
    text = " ".join((message or "").split())
    f = fold(text)
    if not f:
        return None
    cache: dict = {}

    def tokens() -> set:  # la plantilla se lee de la BD solo si hace falta, y una vez
        if "t" not in cache:
            cache["t"] = _name_tokens(names)
        return cache["t"]

    mp = _PUT_SHIFT_RE.search(text)
    if mp:
        nm = fold(mp.group("name"))
        # con la plantilla a mano, el nombre debe ser de un empleado; sin ella basta el nombre propio
        if not tokens() or nm in tokens() or nm.split(" ")[0] in tokens():
            return "schedule_write_put_shift", MSG_SCHEDULE_WRITE
    for rx, reason in ((_NEW_RE, "schedule_write_new"), (_VERB_NOUN_RE, "schedule_write"),
                       (_NOUN_THEN_SEND_RE, "schedule_write")):
        for m in rx.finditer(f):
            if _staff_context(_sentence(f, m.start()), tokens):
                return reason, MSG_SCHEDULE_WRITE
    return None
