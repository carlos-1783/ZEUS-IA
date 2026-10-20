"""
Diagnostico del modelo conversacional (OpenAI) en el proceso que corre de verdad (Railway).

Responde a «¿por qué los agentes no conversan?» sin exponer la clave:
  - si `config.settings.OPENAI_API_KEY` llega al proceso (el modulo que usa openai_service, distinto
    de app.core.config) y si coincide con la variable de entorno actual;
  - defectos tipicos al pegarla en Railway (espacios, comillas, saltos de linea);
  - si OPENAI_MODEL existe y es accesible con esa clave (models.retrieve: sin coste de tokens);
  - opcionalmente, una llamada real minima por el MISMO camino que los agentes (chat_completion).

Nunca devuelve la clave ni fragmentos de ella: los errores del proveedor se sanean (sk-…).
"""

from __future__ import annotations

import os
import re
import time
from typing import Any, Dict, Optional

_KEY_RE = re.compile(r"sk-[A-Za-z0-9_\-*]{4,}")


def _redact(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    return _KEY_RE.sub("sk-***", str(text))[:400]


def _key_shape(key: str) -> Dict[str, Any]:
    raw = key or ""
    stripped = raw.strip().strip('"').strip("'").strip()
    return {
        "present": bool(stripped),
        "length": len(raw),
        "starts_with_sk": stripped.startswith("sk-"),
        "has_surrounding_whitespace": raw != raw.strip(),
        "has_quotes": raw.strip()[:1] in ("'", '"') or raw.strip()[-1:] in ("'", '"'),
        "has_inner_whitespace": bool(re.search(r"\s", raw.strip())),
        "placeholder": stripped in ("your-api-key-here", "sk-xxx", "changeme"),
    }


def _model_check(model: str) -> Dict[str, Any]:
    """models.retrieve: confirma que el modelo existe y que la clave tiene acceso (sin gastar tokens)."""
    from services.openai_service import get_openai_client

    t0 = time.monotonic()
    try:
        client = get_openai_client()
        info = client.models.retrieve(model)
        return {"ok": True, "id": getattr(info, "id", model),
                "latency_ms": int((time.monotonic() - t0) * 1000)}
    except Exception as exc:
        return {"ok": False, "error_type": type(exc).__name__, "error": _redact(str(exc)),
                "status_code": getattr(exc, "status_code", None),
                "latency_ms": int((time.monotonic() - t0) * 1000)}


def _live_call(model: str) -> Dict[str, Any]:
    """Llamada real minima por el mismo wrapper que usan los agentes (base_agent → chat_completion)."""
    from services.openai_service import chat_completion

    res = chat_completion(
        messages=[{"role": "system", "content": "Responde solo con la palabra OK."},
                  {"role": "user", "content": "¿Me recibes?"}],
        model=model,
        max_tokens=5,
        temperature=0,
    )
    if res.get("success"):
        return {"ok": True, "model": res.get("model"), "reply": (res.get("content") or "")[:20],
                "elapsed_s": res.get("elapsed_time"), "cost_usd": res.get("cost")}
    return {"ok": False, "error": _redact(res.get("error")), "technical_error": _redact(res.get("technical_error")),
            "elapsed_s": res.get("elapsed_time")}


def run_llm_diagnostics(*, live: bool = False) -> Dict[str, Any]:
    from config.settings import settings

    key = settings.OPENAI_API_KEY or ""
    env_key = os.environ.get("OPENAI_API_KEY")
    model = (settings.OPENAI_MODEL or "").strip()
    classifier_model = os.getenv("JARVIS_CLASSIFIER_MODEL", "").strip() or model
    shape = _key_shape(key)

    out: Dict[str, Any] = {
        "settings_module": "config.settings",
        "key": shape,
        "env_var_present": env_key is not None and bool(env_key.strip()),
        "env_matches_settings": env_key == key if env_key is not None else False,
        "model": model,
        "model_from_env": os.getenv("OPENAI_MODEL") is not None,
        "classifier_model": classifier_model,
        "timeout_sec": settings.OPENAI_TIMEOUT_SEC,
        "max_retries": settings.OPENAI_MAX_RETRIES,
        "model_check": None,
        "live_call": None,
    }
    problems = []
    if not shape["present"] or shape["placeholder"]:
        problems.append("OPENAI_API_KEY no llega a config.settings (vacia o placeholder).")
    else:
        if shape["has_surrounding_whitespace"] or shape["has_quotes"] or shape["has_inner_whitespace"]:
            problems.append("OPENAI_API_KEY tiene espacios/comillas/saltos de linea: pégala limpia en Railway.")
        if not shape["starts_with_sk"]:
            problems.append("OPENAI_API_KEY no empieza por 'sk-': probablemente no es una clave de OpenAI.")
        if env_key is not None and env_key != key:
            problems.append("La variable de entorno cambió tras arrancar: redeploy para que el proceso la lea.")
        out["model_check"] = _model_check(model)
        if not out["model_check"]["ok"]:
            problems.append(f"El modelo '{model}' no es accesible con esta clave (revisa OPENAI_MODEL).")
        if classifier_model != model:
            out["classifier_model_check"] = _model_check(classifier_model)
        if live:
            out["live_call"] = _live_call(model)
            if not out["live_call"]["ok"]:
                problems.append("La llamada real a OpenAI falla (ver live_call.error).")
    out["problems"] = problems
    out["ok"] = not problems and (not live or bool(out["live_call"] and out["live_call"]["ok"]))
    return out
