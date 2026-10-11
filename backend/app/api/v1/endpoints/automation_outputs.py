"""
Entregables generados por los agentes (JSON, Markdown, video).

Fase 2 / Step 1: antes se listaban y descargaban desde storage/outputs (disco efimero)
SIN filtro de empresa: cualquier usuario autenticado veia y bajaba los entregables de
todas las empresas. Ahora viven en R2 (`stored_files`, categoria "outputs") y solo se
listan y sirven los de las empresas del usuario.
"""

from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.stored_file import StoredFile
from app.models.user import User
from services import object_storage
from services.upload_intake import storage_http_error

router = APIRouter()

_AGENT_RE = re.compile(r"^[a-z_ ]{1,32}$")
_MAX_LIST = 200
_INLINE_TEXT = frozenset({"application/json", "text/markdown"})


def _company_ids(db: Session, user: User):
    import services.crm_office_service as crm_svc

    return crm_svc.company_ids_for_user(db, user)


def _outputs_query(db: Session, user: User):
    ids = _company_ids(db, user)
    if not ids:
        return None
    return db.query(StoredFile).filter(
        StoredFile.category == "outputs",
        StoredFile.company_id.in_(ids),
        StoredFile.deleted_at.is_(None),
    )


@router.options("/outputs", include_in_schema=False)
async def outputs_preflight() -> Response:
    """Preflight sin dependencias de autenticacion."""
    return Response(status_code=204)


@router.get("/outputs")
def list_outputs(
    agent: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Entregables de las empresas del usuario (mas recientes primero)."""
    q = _outputs_query(db, current_user)
    if q is None:
        return {"success": True, "total": 0, "outputs": []}
    if agent:
        if not _AGENT_RE.match(agent.lower()):
            raise HTTPException(status_code=422, detail="Agente no valido")
        q = q.filter(StoredFile.agent_name == agent.upper())
    rows = q.order_by(StoredFile.created_at.desc()).limit(_MAX_LIST).all()
    outputs = [
        {
            "agent": (r.agent_name or "").upper(),
            "filename": r.original_filename,
            "path": f"{(r.agent_name or '').lower()}/{r.original_filename}",
            "file_id": r.id,
            "size_bytes": r.size_bytes,
            "content_type": r.content_type,
            "created_at": r.created_at.timestamp() if r.created_at else None,
        }
        for r in rows
    ]
    return {"success": True, "total": len(outputs), "outputs": outputs}


@router.options("/outputs/{agent}/{filename}", include_in_schema=False)
async def download_preflight(agent: str, filename: str) -> Response:
    return Response(status_code=204)


@router.get("/outputs/{agent}/{filename}")
def download_output(
    agent: str,
    filename: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Descarga (302 a URL firmada corta) de un entregable de una empresa del usuario."""
    q = _outputs_query(db, current_user)
    if q is None or not _AGENT_RE.match(agent.lower()):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    row = (
        q.filter(StoredFile.agent_name == agent.upper(), StoredFile.original_filename == filename)
        .order_by(StoredFile.created_at.desc())
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    if row.content_type in _INLINE_TEXT:
        # JSON/Markdown pequenos: se sirven desde la API (el frontend los lee con fetch; una
        # redireccion a otro dominio exigiria CORS en el bucket).
        try:
            data = object_storage.read_bytes(row)
        except (object_storage.StorageNotConfigured, object_storage.StorageError) as exc:
            raise storage_http_error(exc) from exc
        return Response(
            content=data,
            media_type=row.content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{object_storage.safe_filename(row.original_filename)}"',
                "Cache-Control": "no-store",
            },
        )
    try:
        url = object_storage.signed_url(row)
    except (object_storage.StorageNotConfigured, object_storage.StorageError) as exc:
        raise storage_http_error(exc) from exc
    return RedirectResponse(url, status_code=302, headers={"Cache-Control": "no-store"})
