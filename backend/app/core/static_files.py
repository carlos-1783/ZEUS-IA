"""StaticFiles público que NUNCA sirve rutas privadas (ficheros fiscales).

Los ficheros fiscales viven en settings.PRIVATE_FILES_DIR y solo se descargan por el endpoint
autenticado /api/v1/rafael-fiscal/fiscal-files/... Este montaje bloquea además el prefijo legado
``fiscal/`` bajo /static para que ficheros antiguos que aún estén en STATIC_DIR/fiscal no queden
expuestos sin autenticación.
"""

from __future__ import annotations

import posixpath

from fastapi import HTTPException
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

# Primer segmento de ruta (comparado en minúsculas) que nunca se sirve de forma pública.
# "fiscal": ficheros fiscales legados que pudieran quedar bajo STATIC_DIR (ver docstring).
# "private_files": el propio directorio de settings.PRIVATE_FILES_DIR — defensa en profundidad
# para que, aunque algún despliegue lo anide bajo STATIC_DIR o spa_root, nunca se sirva público.
BLOCKED_PUBLIC_PREFIXES = ("fiscal", "private_files")


def is_blocked_public_path(path: str) -> bool:
    """True si la ruta relativa (sin /static) apunta a un prefijo privado."""
    normalized = posixpath.normpath("/" + path.replace("\\", "/")).lstrip("/")
    first = normalized.split("/", 1)[0].strip().lower()
    return first in BLOCKED_PUBLIC_PREFIXES


class PublicStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope):
        if is_blocked_public_path(path):
            raise HTTPException(status_code=404)
        return await super().get_response(path, scope)
