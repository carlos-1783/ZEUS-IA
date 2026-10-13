"""ZEUS recepcionista: clasificacion, extraccion y enrutado de documentos que llegan por foto.

Flujo (lo orquesta el endpoint /api/v1/zeus/inbox):
  1. El binario ya esta en R2 (services.object_storage); aqui solo se trabaja con sus bytes.
  2. `classify_document` manda la imagen/PDF al modelo de vision de OpenAI y normaliza la
     respuesta: tipo documental de una lista cerrada y campos extraidos. Lo que el modelo no
     lea queda en null: este modulo NUNCA rellena ni estima un campo.
  3. `validate_fields` comprueba coherencia (base + IVA ~= total, NIF/CIF/NIE, fecha) y
     `confidence_level` combina la confianza del modelo con esas comprobaciones.
  4. `AGENT_FOR_TYPE` decide el agente responsable. El "reparto" es una revision pendiente
     (document_approvals, estado pending_review) que un humano tiene que mirar.

Guardarrailes: nada aqui contabiliza, registra facturas ni envia nada a AEAT ni a terceros.
Sin OPENAI_API_KEY se lanza `ClassificationUnavailable` (el endpoint responde 503 honesto).
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from config.settings import settings

logger = logging.getLogger(__name__)

DOC_TYPES = ("factura_proveedor", "ticket", "nomina", "albaran", "pedido", "contrato", "otro")

AGENT_FOR_TYPE: Dict[str, str] = {
    "factura_proveedor": "RAFAEL",
    "ticket": "RAFAEL",
    "nomina": "AFRODITA",
    "albaran": "AFRODITA",
    "pedido": "AFRODITA",
    "contrato": "JUSTICIA",
    "otro": "ZEUS",
}

# Tipos en los que la coherencia base + IVA = total es exigible.
_AMOUNT_TYPES = frozenset({"factura_proveedor", "ticket"})

FIELD_NAMES = ("proveedor", "nif", "fecha", "numero", "base", "iva", "total")
_AMOUNT_FIELDS = ("base", "iva", "total")

VISION_MODEL = os.getenv("ZEUS_INBOX_VISION_MODEL", "").strip() or os.getenv(
    "PERSEO_AI_MODEL", "gpt-4o"
).strip() or "gpt-4o"

MISSING_KEY_DETAIL = "clasificación no disponible: falta OPENAI_API_KEY"


class ClassificationUnavailable(RuntimeError):
    """No hay modelo de vision configurado (falta OPENAI_API_KEY)."""

    def __init__(self) -> None:
        super().__init__(MISSING_KEY_DETAIL)


class ClassificationFailed(RuntimeError):
    """El modelo respondio con error o con algo que no se puede interpretar."""


def classification_available() -> bool:
    key = (getattr(settings, "OPENAI_API_KEY", "") or "").strip()
    return bool(key) and key != "your-api-key-here"


# ------------------------------------------------------------------ llamada al modelo

_SYSTEM_PROMPT = (
    "Eres ZEUS, recepcionista documental de una empresa espanola. Recibes la foto o el PDF de "
    "UN documento. Responde SOLO un objeto JSON con estas claves:\n"
    '  "tipo": uno de factura_proveedor, ticket, nomina, albaran, pedido, contrato, otro;\n'
    '  "confianza": numero entre 0 y 1 sobre la clasificacion;\n'
    '  "campos": objeto con proveedor (emisor), nif (NIF/CIF del emisor), fecha (YYYY-MM-DD), '
    "numero (numero de documento), base (base imponible), iva (cuota de IVA), total (importe "
    "total). Importes como numero con punto decimal, sin simbolo de moneda;\n"
    '  "observaciones": texto breve con lo que no se lee bien.\n'
    "REGLA ESTRICTA: si un dato no aparece o no se lee con claridad, pon null. No lo deduzcas, "
    "no lo calcules a partir de otros importes y no lo inventes."
)


def _content_part(data: bytes, content_type: str, filename: str) -> Dict[str, Any]:
    b64 = base64.b64encode(data).decode("ascii")
    if content_type == "application/pdf":
        return {
            "type": "file",
            "file": {"filename": filename or "documento.pdf", "file_data": f"data:application/pdf;base64,{b64}"},
        }
    return {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{b64}", "detail": "high"}}


def _vision_call(data: bytes, content_type: str, filename: str, note: Optional[str]) -> Dict[str, Any]:
    """Llamada real a OpenAI (chat completions con imagen/PDF). Devuelve el JSON del modelo."""
    from services.openai_service import get_openai_client, parse_json_response

    user_text = "Clasifica este documento y extrae sus campos."
    if note:
        user_text += f"\nNota del usuario (contexto, no es parte del documento): {note}"
    client = get_openai_client()
    response = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": [{"type": "text", "text": user_text}, _content_part(data, content_type, filename)]},
        ],
        temperature=0,
        max_tokens=800,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content or ""
    parsed = parse_json_response(content)
    if not isinstance(parsed, dict):
        raise ClassificationFailed("El modelo de visión no devolvió un JSON válido.")
    return parsed


# ------------------------------------------------------------------ normalizacion


def _to_decimal(value: Any) -> Optional[Decimal]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return Decimal(str(value)).quantize(Decimal("0.01"))
    if isinstance(value, str):
        s = value.strip().replace("€", "").replace("EUR", "").replace(" ", "")
        if not s:
            return None
        # Formato espanol 1.234,56 -> 1234.56
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
        elif "," in s:
            s = s.replace(",", ".")
        try:
            return Decimal(s).quantize(Decimal("0.01"))
        except InvalidOperation:
            return None
    return None


def _clean_str(value: Any, max_len: int = 200) -> Optional[str]:
    if value is None or isinstance(value, (dict, list, bool)):
        return None
    s = str(value).strip()
    if not s or s.lower() in ("null", "none", "n/a", "-"):
        return None
    return s[:max_len]


def normalize_model_output(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Solo conserva lo que el modelo dio; lo ausente o ilegible queda en None."""
    doc_type = _clean_str(raw.get("tipo"), 40)
    doc_type = doc_type.lower() if doc_type else None
    if doc_type not in DOC_TYPES:
        doc_type = "otro"
    try:
        model_conf = float(raw.get("confianza"))
        model_conf = min(max(model_conf, 0.0), 1.0)
    except (TypeError, ValueError):
        model_conf = None
    campos = raw.get("campos") if isinstance(raw.get("campos"), dict) else {}
    fields: Dict[str, Any] = {}
    for name in FIELD_NAMES:
        v = campos.get(name)
        if name in _AMOUNT_FIELDS:
            d = _to_decimal(v)
            fields[name] = str(d) if d is not None else None
        elif name == "nif":
            s = _clean_str(v, 20)
            fields[name] = re.sub(r"[\s.-]", "", s).upper() if s else None
        else:
            fields[name] = _clean_str(v)
    return {
        "doc_type": doc_type,
        "model_confidence": model_conf,
        "fields": fields,
        "observations": _clean_str(raw.get("observaciones"), 500),
    }


# ------------------------------------------------------------------ validacion

_DNI_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"
_NIF_RE = re.compile(r"^\d{8}[A-Z]$")
_NIE_RE = re.compile(r"^[XYZ]\d{7}[A-Z]$")
_CIF_RE = re.compile(r"^[ABCDEFGHJNPQRSUVW]\d{7}[0-9A-J]$")


def nif_is_valid(nif: str) -> bool:
    nif = (nif or "").upper()
    if nif.startswith("ES") and len(nif) > 9:
        nif = nif[2:]
    if _NIF_RE.match(nif):
        return _DNI_LETTERS[int(nif[:8]) % 23] == nif[8]
    if _NIE_RE.match(nif):
        num = "XYZ".index(nif[0])
        return _DNI_LETTERS[int(f"{num}{nif[1:8]}") % 23] == nif[8]
    if _CIF_RE.match(nif):
        digits = nif[1:8]
        even = sum(int(digits[i]) for i in (1, 3, 5))
        odd = sum(sum(divmod(int(digits[i]) * 2, 10)) for i in (0, 2, 4, 6))
        control = (10 - (even + odd) % 10) % 10
        return nif[8] in (str(control), "JABCDEFGHI"[control])
    return False


def validate_fields(doc_type: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    """Comprobaciones deterministas sobre lo extraido. Nunca corrige ni completa campos."""
    checks: Dict[str, Any] = {}
    issues: List[str] = []

    base, iva, total = (_to_decimal(fields.get(k)) for k in _AMOUNT_FIELDS)
    if base is not None and iva is not None and total is not None:
        diff = abs(base + iva - total)
        tolerance = max(Decimal("0.02"), (abs(total) * Decimal("0.005")).quantize(Decimal("0.01")))
        ok = diff <= tolerance
        checks["importes"] = {"estado": "coherente" if ok else "incoherente", "diferencia": str(diff)}
        if not ok:
            issues.append(f"base + IVA no cuadra con el total (diferencia {diff} EUR)")
    else:
        checks["importes"] = {"estado": "incompleto"}
        if doc_type in _AMOUNT_TYPES:
            faltan = [k for k, v in zip(_AMOUNT_FIELDS, (base, iva, total)) if v is None]
            issues.append("faltan importes legibles: " + ", ".join(faltan))

    nif = fields.get("nif")
    if nif:
        valid = nif_is_valid(nif)
        checks["nif"] = "valido" if valid else "formato_o_control_invalido"
        if not valid:
            issues.append("el NIF/CIF leído no supera la comprobación de formato/control")
    else:
        checks["nif"] = "ausente"
        if doc_type == "factura_proveedor":
            issues.append("no se ha leído el NIF/CIF del proveedor")

    fecha = fields.get("fecha")
    if fecha:
        try:
            d = date.fromisoformat(fecha)
            checks["fecha"] = "futura" if d > date.today() else "valida"
            if d > date.today():
                issues.append("la fecha leída es futura")
        except ValueError:
            checks["fecha"] = "formato_invalido"
            issues.append("la fecha leída no tiene formato AAAA-MM-DD")
    else:
        checks["fecha"] = "ausente"

    return {"checks": checks, "issues": issues}


def confidence_level(doc_type: str, model_confidence: Optional[float], validation: Dict[str, Any]) -> str:
    """alta / media / baja. Cualquier incoherencia o confianza desconocida baja el nivel."""
    issues = validation.get("issues") or []
    importes = (validation.get("checks") or {}).get("importes", {}).get("estado")
    if model_confidence is None or model_confidence < 0.5 or importes == "incoherente":
        return "baja"
    if model_confidence >= 0.8 and not issues:
        return "alta"
    return "media"


def classify_document(
    data: bytes, content_type: str, filename: str, note: Optional[str] = None
) -> Dict[str, Any]:
    """Clasificacion + extraccion + validacion. Lanza ClassificationUnavailable sin clave y
    ClassificationFailed si el modelo falla; nunca devuelve campos inventados."""
    if not classification_available():
        raise ClassificationUnavailable()
    try:
        raw = _vision_call(data, content_type, filename, note)
    except (ClassificationUnavailable, ClassificationFailed):
        raise
    except Exception as exc:  # error de red / API de OpenAI
        logger.error("ZEUS inbox: fallo del modelo de vision: %s", type(exc).__name__)
        raise ClassificationFailed(f"El modelo de visión falló ({type(exc).__name__}).") from exc
    norm = normalize_model_output(raw)
    validation = validate_fields(norm["doc_type"], norm["fields"])
    return {
        **norm,
        "validation": validation,
        "confidence": confidence_level(norm["doc_type"], norm["model_confidence"], validation),
        "assigned_agent": AGENT_FOR_TYPE[norm["doc_type"]],
        "model": VISION_MODEL,
    }


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)
