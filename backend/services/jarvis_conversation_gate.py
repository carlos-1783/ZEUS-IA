"""
ZEUS conversa por defecto.

Solo se entra en el camino de accion/plan (comprension por modelo, plan multiagente, pregunta de
aclaracion «¿es sobre clientes, TPV…?») cuando el mensaje expresa una INTENCION CLARA de que ZEUS haga
algo: una orden en imperativo («envía», «crea», «dame», «prepara»…) o una peticion explicita
(«quiero/necesito/puedes + verbo de accion»). Charla, opiniones, preguntas sobre el negocio o
peticiones de algo que ZEUS no hace van al modelo conversacional, que responde HABLANDO.

La deteccion es deliberadamente barata y sin modelo. No relaja ninguna salvaguarda: lo que si entra
sigue por el criterio J8/J8b, la aprobacion humana J3 y THALOS exactamente igual que antes.
"""

from __future__ import annotations

import re

from services import jarvis_model_comprehension as model_comp
from services.intent_parser import fold, has_negation, looks_like_operational

# Imperativos (tu/usted, con o sin enclitico) de acciones que ZEUS sabe ejecutar o consultar.
_IMPERATIVE = (
    r"envia|enviale|envialo|enviales|envie|mandale|mandalo|mandales|manda|mande|lanza|lance|publica|publique|"
    r"crea|cree|creame|crealo|genera|genere|generame|da\s+de\s+alta|dale\s+de\s+alta|anade|anada|agrega|"
    r"registra|registre|apunta|apunte|anota|cobra|cobre|factura|facture|borra|borre|elimina|elimine|anula|"
    r"anule|paga|programa|programe|notifica|avisa|dame|deme|dime|dinos|digame|muestrame|muestra|ensename|lista|listame|"
    r"consulta|revisa|revise|prepara|preparame|prepare|haz|hazme|calcula|calculame|busca|buscame|"
    r"planifica|organiza|redacta|redactame|redacte|escribe|escribeme|resume|resumeme|importa|exporta|"
    r"descarga|ficha|confirma|cancela"
)
# Verbos de accion en infinitivo tras una peticion explicita.
_INFINITIVE = (
    r"enviar|mandar|lanzar|publicar|crear|generar|dar\s+de\s+alta|anadir|agregar|registrar|apuntar|anotar|"
    r"cobrar|facturar|borrar|eliminar|anular|pagar|programar|notificar|avisar|preparar|hacer|calcular|"
    r"consultar|revisar|ver|saber|buscar|planificar|organizar|importar|exportar|descargar|fichar|"
    r"conocer|sacar|listar"
)

# Orden al principio de la frase (tras saludo/vocativo/cortesia opcional) o tras un separador.
_COMMAND_RE = re.compile(
    r"(?:^|[.,;:!?¿¡]\s*|\b(?:y|luego|despues|tambien|ademas)\s+)"
    r"(?:(?:hola|oye|ey|zeus|jarvis|perseo|rafael|justicia|afrodita|thalos|porfa|por\s+favor|venga|vale|ok)"
    r"[\s,]+)*"
    rf"(?:{_IMPERATIVE})\b"
)
_REQUEST_RE = re.compile(
    r"\b(?:quiero|quisiera|necesito|me\s+gustaria|puedes|podrias|puede|podria|te\s+pido|"
    r"hay\s+que|tienes\s+que|vamos\s+a)\s+(?:\w+\s+){0,2}?"
    rf"(?:{_INFINITIVE})\b"
)
# Peticion en subjuntivo: «me gustaria que lanzaras…», «quiero que envies…», «necesito que me prepares…».
_SUBJ_STEMS = (
    r"envi|mand|lanc|lanz|public|cre|gener|prepar|hag|hicier|registr|anot|apunt|cobr|factur|borr|elimin|"
    r"anul|pag|program|notific|avis|calcul|busqu|busc|revis|consult|organic|organiz|planific|"
    r"import|export|descarg|fich|anad|agreg|redact|escrib|resum|muestr|mostr|ensen"
)
_SUBJ_REQUEST_RE = re.compile(
    r"\b(?:quiero|quisiera|necesito|me\s+gustaria|te\s+pido|preferiria)\s+que\s+"
    r"(?:(?:me|nos|le|les|lo|la|los|las|se)\s+)?"
    rf"(?:{_SUBJ_STEMS})\w*"
)
# Coletilla final de pregunta («…, ¿no crees?», «…, ¿no?», «…, ¿verdad?»): pide opinion, no niega nada.
_TAG_QUESTION_RE = re.compile(
    r"[\s,]*¿?\s*(?:no\s+(?:crees|te\s+parece|es\s+asi|es\s+verdad|lo\s+crees)|no|verdad)\s*\?+\s*$"
)


def has_clear_action_intent(message: str) -> bool:
    """True si el mensaje pide de forma clara que ZEUS HAGA o CONSULTE algo real."""
    f = " ".join(fold(message or "").split())
    if not f:
        return False
    return bool(_COMMAND_RE.search(f) or _REQUEST_RE.search(f) or _SUBJ_REQUEST_RE.search(f))


# ----------------------------------------------------------------------------- orden de PARADA
# Solo IMPERATIVO (tu/usted, con o sin enclitico) al inicio de clausula. Nunca sustantivos ni pasados:
# «cancelaciones», «suspendí», «se aplazó», «anuló su reserva» NO son paradas.
_STOP_LEAD = (
    r"(?:^|[.,;:!?¿¡]\s*|\b(?:y|pero|ahora|mejor|asi\s+que)\s+)"
    r"(?:(?:hola|oye|ey|zeus|jarvis|perseo|rafael|justicia|afrodita|thalos|porfa|por\s+favor|venga|vale|ok|"
    r"mejor|ahora)[\s,]+)*"
)
_END = r"\s*(?:$|[.,;:!?¡¿]|\s+ya\b|\s+ahora\b|\s+mismo\b)"
# Paradas que lo son por si solas, digan lo que digan despues.
_STOP_ALONE = (
    r"stop|basta|quieto|alto(?=" + _END + r")|"
    r"(?:deja|deje|dejalo|dejala|dejalos|dejalas|dejelo|dejela)\s+(?:estar|correr)|"
    r"(?:dejalo|dejala|dejelo|olvidalo|olvidala|olvidate\s+de\s+(?:eso|esto|ello))(?=" + _END + r")|"
    r"(?:para|pare|paralo|parala|paralos|paralas)(?=" + _END + r")|"
    # «espera» solo como orden de pausa: sola o con «antes / un momento / un poco / a que». «Espera,
    # ¿cuánto vendí?» es una muletilla, no una parada, y va a la conversacion.
    r"(?:espera|espere|esperate)(?=\s*(?:$|[.!]|\s+(?:antes|un\s+momento|un\s+poco|a\s+que)\b))"
)
# Verbos que paran ALGO: solo son parada si lo que se para es una accion en curso/programada (envio,
# campaña, oferta, mensaje, proceso…), un pronombre («eso», «lo», enclitico) o nada. «anula la factura
# 23» / «cancela la reserva de Ana» tienen objeto propio (un registro del negocio): son ACCIONES, no
# paradas, y siguen el camino de accion/aclaracion normal (con aprobacion J3 si procede).
_STOP_VERB = (
    r"deten|detenga|detente|pare|frena|frene|suspende|suspenda|aborta|aborte|aplaza|aplace|pospon|"
    r"posponga|cancela|cancele|anula|anule|interrumpe|interrumpa|retira|retire"
)
# Lo que se para es una comunicacion/proceso EN CURSO o programado. Fuera a proposito: «plan» («cancela el
# plan premium» = suscripcion), «tarea» y «operacion» («anula la operación 45» = registro del TPV): son
# objetos propios del negocio, o sea ACCIONES, no paradas.
_STOP_OBJ = (
    r"envio|envios|campana|campanas|oferta|ofertas|promocion|promociones|promo|promos|mensaje|mensajes|"
    r"mailing|difusion|correo|correos|newsletter|proceso|publicacion|publicaciones|post|programacion|accion"
)
_DET = r"(?:el|la|los|las|este|esta|estos|estas|ese|esa|esos|esas|mi|mis|tu|tus|su|sus)"
_STOP_RE = re.compile(
    _STOP_LEAD + r"(?:"
    rf"(?:{_STOP_ALONE})"
    rf"|(?:{_STOP_VERB}|para|pare)(?:lo|la|los|las)\b"
    rf"|(?:{_STOP_VERB})(?:{_END}|\s+(?:eso|esto|todo|lo\s+que)\b|\s+{_DET}\s+(?:{_STOP_OBJ})\b)"
    r")"
)
# «para» + objeto es AMBIGUO: verbo («para el envío») o preposicion («para la campaña de verano, prepara
# un post», «para el post de mañana, ¿qué foto uso?»). Criterio: solo es parada si va al inicio de clausula,
# el objeto es de envio/difusion (no post/publicacion/accion/programacion, que son objetivos tipicos de
# «para») y lo que sigue hasta el final es, por LISTA BLANCA, solo complementos del propio objeto: grupos
# que empiezan por preposicion (de/del/a/al/con/en/hacia/para) seguida unicamente de determinantes,
# cifras/% y un vocabulario CERRADO de sustantivos de envio/destinatarios/temporada (_PARA_NOUNS), mas
# «ya/ahora/mismo/inmediatamente» al final. Cualquier otra palabra (un verbo como «usa», «tengo»,
# «usaremos», «pon», «me gusta», un adverbio como «mañana»…) => preposicion => NO es parada. Conservador:
# ante la duda no hay parada; la parada con objeto sigue cubierta por detén/frena/suspende/aborta/…
_PARA_OBJ = (
    r"envio|envios|campana|campanas|oferta|ofertas|promocion|promociones|promo|promos|mensaje|mensajes|"
    r"mailing|difusion|correo|correos|newsletter|proceso"
)
_PARA_OBJ_RE = re.compile(
    _STOP_LEAD + rf"(?:para|pare)\s+{_DET}\s+(?:{_PARA_OBJ})\b(?P<rest>[^,;:?¿!¡]*)[.!¡\s]*$"
)
_PARA_PREPS = frozenset("de del a al con en hacia para".split())
_PARA_DETS = frozenset(
    "el la los las lo un una unos unas este esta estos estas ese esa esos esas aquel aquella mi mis tu tus "
    "su sus nuestro nuestra nuestros nuestras vuestro vuestra todo toda todos todas cada".split()
)
_PARA_NOUNS = frozenset(
    "envio envios campana campanas oferta ofertas promocion promociones promo promos mensaje mensajes "
    "mailing difusion correo correos newsletter proceso descuento descuentos cupon cupones cliente clientes "
    "contacto contactos suscriptor suscriptores socio socios usuario usuarios lista listas base vip vips "
    "verano invierno primavera otono navidad navidades rebajas black friday ciento".split()
)
_PARA_TAIL = frozenset("ya ahora mismo inmediatamente".split())
_PARA_NUM_RE = re.compile(r"^\d+(?:[.,]\d+)?$")


def _para_with_object_is_stop(f: str) -> bool:
    m = _PARA_OBJ_RE.search(f)
    if not m:
        return False
    tokens = re.findall(r"\d+(?:[.,]\d+)?|%|\w+", m.group("rest"))
    while tokens and tokens[-1] in _PARA_TAIL:
        tokens.pop()
    if not tokens:
        return True  # «para el envío», «para el envío ya»
    if tokens[0] not in _PARA_PREPS:
        return False
    for i, tok in enumerate(tokens):
        if tok in _PARA_PREPS:
            # una preposicion abre un grupo nominal: no puede cerrar el mensaje ni ir seguida de otra
            if i + 1 >= len(tokens) or tokens[i + 1] in _PARA_PREPS:
                return False
        elif not (tok in _PARA_DETS or tok in _PARA_NOUNS or tok == "%" or _PARA_NUM_RE.match(tok)):
            return False
    return True


def is_stop_order(message: str) -> bool:
    """Orden de PARADA/retractacion sin «no» en imperativo («detén el envío», «para», «para ya», «stop»,
    «frena la campaña», «suspende la oferta», «aborta», «aplaza/pospón eso», «déjalo estar», «cancela el
    envío»…). Se trata igual que una negacion: no se hace nada. Ver _STOP_VERB/_STOP_OBJ para el criterio
    parada (accion en curso) frente a accion con objeto propio («anula la factura 23») y _PARA_OBJ_RE para
    «para» verbo frente a «para» preposicion."""
    f = " ".join(fold(message or "").split())
    return bool(f) and bool(_STOP_RE.search(f) or _para_with_object_is_stop(f))


def may_negate_or_stop(message: str) -> bool:
    """True si el mensaje contiene una negacion, duda o retractacion que deben decidir las salvaguardas
    J8/J8c (nunca el modelo conversacional). Mismo detector que usa la comprension J8c para el conflicto
    de polaridad. Solo se ignora la coletilla final de pregunta («¿no crees?»): pedir opinion no es negar."""
    f = " ".join(fold(message or "").split())
    if not f:
        return False
    core = _TAG_QUESTION_RE.sub("", f)
    return bool(has_negation(core) or model_comp._rules_see_negation(core) or is_stop_order(core))


def is_terse_operational(message: str) -> bool:
    """Referencia telegrafica a un modulo del negocio («la caja», «ventas hoy», «turnos»): es una
    peticion elidida, no charla; se pregunta que accion se quiere (aclaracion concreta J8)."""
    f = " ".join(fold(message or "").split())
    return bool(f) and len(re.findall(r"\w+", f)) <= 3 and looks_like_operational(f)


def wants_action_path(message: str) -> bool:
    """Puerta de entrada al camino de accion/plan para mensajes que las reglas no clasifican."""
    return has_clear_action_intent(message) or is_terse_operational(message) or may_negate_or_stop(message)
