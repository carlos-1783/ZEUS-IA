"""Entradas de los motores PERSEO desde el almacenamiento comun (Fase 2 / Step 1).

ffmpeg necesita ficheros en disco para procesar: se descargan a un directorio temporal
del proceso (se borra al terminar), nunca a STATIC_DIR. La referencia de entrada solo
se resuelve entre los ficheros de las empresas del usuario: antes `_resolve_input_path`
aceptaba cualquier ruta bajo /static aunque fuera de otra empresa.

Formatos aceptados:
- /api/v1/files/{id}  (o la misma ruta en una URL absoluta de este host)
- /static/uploads/...  (URL antigua de un fichero migrado: se busca por legacy_path)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from fastapi import HTTPException

from services import object_storage

_FILES_RE = re.compile(r"^/api/v1/files/([0-9a-f]{32})/?$")
_LEGACY_RE = re.compile(r"^/static/(uploads/[A-Za-z0-9._/-]+)$")


def _path_of(ref: str) -> str:
    raw = (ref or "").strip()
    if raw.startswith(("http://", "https://")):
        return urlparse(raw).path
    return raw.split("?", 1)[0]


def find_input(db, ref: str, user_id: Optional[int]):
    """StoredFile referenciado por `ref`, solo si es de una empresa del usuario."""
    import services.crm_office_service as crm_svc
    from app.models.user import User

    if not (ref or "").strip():
        raise HTTPException(status_code=422, detail="input_url required")
    user = db.get(User, int(user_id)) if user_id else None
    company_ids = crm_svc.company_ids_for_user(db, user) if user is not None else []
    path = _path_of(ref)
    m = _FILES_RE.match(path)
    row = None
    if m:
        row = object_storage.get_for_companies(db, m.group(1), company_ids)
    else:
        legacy = _LEGACY_RE.match(path)
        if legacy and ".." not in legacy.group(1):
            row = object_storage.get_legacy_for_companies(db, legacy.group(1), company_ids)
        elif not legacy:
            raise HTTPException(
                status_code=422,
                detail="La entrada debe ser un fichero subido a ZEUS (/api/v1/files/{id}).",
            )
    if row is None:
        raise HTTPException(status_code=404, detail=f"Fichero de entrada no encontrado: {path}")
    return row


def download_input(db, ref: str, user_id: Optional[int], dest_dir: Path) -> Path:
    """Descarga la entrada a `dest_dir` (temporal del llamador) y devuelve la ruta."""
    row = find_input(db, ref, user_id)
    try:
        data = object_storage.read_bytes(row)
    except object_storage.StorageNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except object_storage.StorageError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / f"input_{row.id}{Path(row.original_filename).suffix.lower()[:8]}"
    out.write_bytes(data)
    return out
