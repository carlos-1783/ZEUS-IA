"""Guardarrail legal del chat (ZEUS y workspaces de agente): ordenes de enviar algo a la AEAT/Verifactu
o de presentar/pagar/aplazar impuestos.

ZEUS no esta adaptado a Verifactu ni presenta impuestos (eso va via gestor/colaborador social). Una orden
asi NO se atiende con una lectura ni la decide el modelo conversacional (que podria contestar «hecho"):
se responde con un BLOQUEO HONESTO que dice el motivo, sin ejecutar nada.

Solo ordenes: imperativo (o «quiero/necesito/puedes… + infinitivo») al inicio de clausula. Preguntas
(«¿cuándo presento el 303?», «¿cuánto IVA tengo que pagar?») y negaciones no se bloquean aqui.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

from services.intent_parser import fold

_LEAD = (
    r"(?:^|[.,;:!?¿¡]\s*|\b(?:y|luego|despues|tambien|ademas)\s+)"
    r"(?:(?:hola|oye|ey|zeus|jarvis|rafael|perseo|justicia|afrodita|thalos|porfa|por\s+favor|venga|vale|ok)"
    r"[\s,]+)*"
    r"(?:(?:quiero|quisiera|necesito|puedes|podrias|me\s+gustaria|hay\s+que|tienes\s+que)\s+(?:que\s+)?(?:(?:me|nos|le|les|lo|la|se)\s+)?)?"
)
# Enviar/subir/registrar ALGO en la AEAT/Verifactu (facturas, registros…).
_SUBMIT_VERB = (
    r"sube\w*|subir\w*|subas|envia\w*|enviar\w*|envies|manda\w*|mandar\w*|mandes|presenta\w*|presentar\w*|"
    r"presentes|declara\w*|declarar\w*|registra\w*|registrar\w*|remite\w*|remitir\w*|transmite\w*|"
    r"transmitir\w*|comunica\w*|comunicar\w*|reporta\w*|reportar\w*|da\s+de\s+alta|dar\s+de\s+alta|"
    r"registres|remitas|transmitas|comuniques|declares"
)
# Destino: Verifactu siempre es el sistema de la AEAT; el resto solo como destino («a/al/en/ante Hacienda»),
# para no bloquear «envía un correo a mi gestor sobre Hacienda».
_AEAT_TARGET = (r"\bveri\s*factu\b|\b(?:a|al|en|ante|hacia|para)\s+(?:la\s+|el\s+)?"
                r"(?:aeat|hacienda|agencia\s+tributaria|sii)\b")
# Presentar/pagar/aplazar/fraccionar/domiciliar un IMPUESTO (IVA, modelos, IRPF…).
_TAX_VERB = (
    r"presenta\w*|presentar\w*|declara\w*|declarar\w*|liquida\w*|liquidar\w*|ingresa\w*|ingresar\w*|"
    r"paga|pagalo|pagala|pagar|pagues|domicilia\w*|domiciliar\w*|fracciona\w*|fraccionar\w*|aplaza\w*|"
    r"aplazar\w*|aplaces|"
    # subjuntivo tras «quiero/necesito que…»
    r"presentes|declares|liquides|ingreses|domicilies|fracciones"
)
# El impuesto es el OBJETO directo del verbo («aplaza el IVA», «domicilia el pago del IVA»), no una mencion
# suelta («paga la factura del proveedor con IVA» no es un tramite fiscal).
_TAX_OBJ = (r"^\s*(?:(?:el|la|los|las|mi|mis|nuestro|nuestra|este|esta|ese|esa|del|de|pago|pagos|cuota|"
            r"cuotas|deuda|importe|recibo)\s+){0,3}"
            r"(?:iva|modelo\s*\d{3}|303|130|390|111|115|impuestos?|irpf|declaracion\w*|autoliquidacion\w*)\b")

_SUBMIT_RE = re.compile(_LEAD + rf"(?:{_SUBMIT_VERB})\b(?P<rest>.*)$")
_TAX_RE = re.compile(_LEAD + rf"(?:{_TAX_VERB})\b(?P<rest>.*)$")

MSG_AEAT = (
    "No puedo enviar nada a la AEAT ni a Verifactu: ZEUS todavía no está adaptado a Verifactu (huella "
    "encadenada, QR y registro oficial) y no tiene el circuito legal para enviar registros a Hacienda. "
    "No he enviado nada. Puedes consultar tus facturas aquí y descargarlas para tu gestor."
)
MSG_TAX = (
    "No puedo presentar, pagar, aplazar, fraccionar ni domiciliar impuestos: eso se hace a través de tu "
    "gestor (colaborador social) o con apoderamiento, no desde ZEUS. No he hecho nada. Sí puedo darte el "
    "cálculo orientativo del IVA del trimestre («¿cuál es el IVA de este trimestre?»)."
)


def legal_block(message: str) -> Optional[Tuple[str, str]]:
    """(motivo, mensaje) si el mensaje ORDENA un tramite con la AEAT/Verifactu o con impuestos; si no, None."""
    f = " ".join(fold(message or "").split())
    if not f:
        return None
    for m in _SUBMIT_RE.finditer(f):
        if re.search(_AEAT_TARGET, m.group("rest")):
            return "aeat_submission", MSG_AEAT
    for m in _TAX_RE.finditer(f):
        if re.match(_TAX_OBJ, m.group("rest")):
            return "tax_filing", MSG_TAX
    return None
