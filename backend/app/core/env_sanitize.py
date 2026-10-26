"""Saneado CENTRAL del entorno del proceso: un solo punto para todas las variables.

Railway (y otros paneles) permiten pegar valores con comillas literales o con espacios/saltos de linea
al principio o al final: `AFRODITA_EXECUTION_ENABLED="true"` llega al proceso como la cadena `"true"`
(con las comillas), que ningun `.lower() in ("true", "1", "yes")` reconoce -> el flag se evaluaba False
en silencio. Lo mismo con `  /data/static  ` en STATIC_DIR o un token con `\\n` final.

Regla (la misma que aplica python-dotenv a un `.env`), para CADA valor:
  1. recortar espacios y saltos de linea al principio y al final;
  2. quitar UN par de comillas envolventes ("..." o '...') solo si el valor empieza y termina con la
     MISMA comilla. Las comillas internas nunca se tocan: `{"a":"b"}` queda igual; `"{"a":"b"}"` pierde
     solo el par exterior.

No arregla (a proposito) una variable con OTRA variable pegada dentro (p. ej. STATIC_DIR con
`\\nR2_ACCOUNT_ID=...` en medio): eso es configuracion rota que se corrige en Railway; aqui solo se
recortan los extremos, el contenido interior se conserva y los detectores existentes lo siguen viendo.

Se aplica sobre `os.environ` (no solo sobre Settings) para que tambien los `os.getenv` sueltos del codigo
y los subprocesos lanzados despues reciban el valor limpio. Lo invocan los modulos de configuracion al
importarse (app/core/config.py y config/settings.py), antes de leer ninguna variable. Es idempotente.
"""
from __future__ import annotations

import logging
import os
from typing import List, MutableMapping, Optional

logger = logging.getLogger("zeus.config")

_QUOTES = ('"', "'")


def clean_env_value(value: str) -> str:
    """Recorta los extremos y quita UN par de comillas envolventes iguales (como python-dotenv)."""
    s = value.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in _QUOTES:
        s = s[1:-1]
    return s


def sanitize_environ(environ: Optional[MutableMapping[str, str]] = None) -> List[str]:
    """Sanea en sitio cada valor de `environ` (por defecto `os.environ`). Devuelve los NOMBRES cambiados.

    Solo se registran nombres, nunca valores (pueden ser secretos)."""
    env = os.environ if environ is None else environ
    changed: List[str] = []
    for key in list(env.keys()):
        raw = env.get(key)
        if raw is None:
            continue
        clean = clean_env_value(raw)
        if clean != raw:
            env[key] = clean
            changed.append(key)
    if changed:
        logger.warning(
            "[ENV] %d variable(s) con comillas o espacios en los extremos saneadas al arrancar "
            "(corrigelas en el panel de variables): %s",
            len(changed),
            ", ".join(sorted(changed)),
        )
    return changed
