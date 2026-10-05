"""
📋 Payroll Drafts - Listar y descargar borradores de nómina
"""
import logging
from pathlib import Path
from typing import Optional
import os

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from app.models.payroll_draft import PayrollDraft

router = APIRouter(prefix="/payroll", tags=["payroll"])
logger = logging.getLogger(__name__)

PAYROLL_OUTPUT_DIR = Path(os.getenv("PAYROLL_OUTPUT_DIR", "storage/outputs/payroll_drafts"))


def _require_owner_or_superuser(current_user: User) -> None:
    """Nóminas solo para dueño de empresa o superuser; empleados sin acceso."""
    if getattr(current_user, "is_superuser", False):
        return
    role = getattr(current_user, "role", "owner") or "owner"
    if role == "employee":
        raise HTTPException(status_code=403, detail="Solo el dueño de la empresa puede acceder a Nóminas")


@router.get("/drafts")
async def list_payroll_drafts(
    owner_user_id: Optional[int] = Query(
        None,
        description="Solo superuser: filtrar por empresa/owner concreto. Ignorado para usuarios owner normales.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Lista borradores de nómina.

    - owner (role != employee, no superuser): SOLO ve los borradores de SU PROPIA
      empresa (owner_user_id == su propio id). En este modelo de datos "empresa" es
      el propio usuario owner (ver app/models/payroll_draft.py), por lo que esto es
      el comportamiento correcto para el caso normal de un único propietario.
    - superuser: ve TODOS los borradores de TODAS las empresas por defecto (igual
      alcance que ya tenía el endpoint de descarga, que exime a superuser del
      filtro de propiedad). Puede acotar a una empresa concreta con ?owner_user_id=.
    """
    _require_owner_or_superuser(current_user)
    query = db.query(PayrollDraft)
    if current_user.is_superuser:
        if owner_user_id is not None:
            query = query.filter(PayrollDraft.owner_user_id == owner_user_id)
        logger.info(
            "payroll_drafts_list superuser_id=%s scope=%s",
            current_user.id,
            owner_user_id if owner_user_id is not None else "all_companies",
        )
    else:
        query = query.filter(PayrollDraft.owner_user_id == current_user.id)
    drafts = (
        query
        .order_by(PayrollDraft.generated_at.desc())
        .limit(50)
        .all()
    )
    items = [
        {
            "id": d.id,
            "employee_id": d.employee_id,
            "gross_salary": d.gross_salary,
            "net_salary_estimated": d.net_salary_estimated,
            "month": d.month,
            "year": d.year,
            "status": d.status,
            "generated_at": d.generated_at.isoformat() if d.generated_at else None,
            "download_url": f"/api/v1/payroll/drafts/{d.id}/download",
        }
        for d in drafts
    ]
    return {"success": True, "drafts": items}


@router.get("/drafts/{draft_id}/download")
async def download_payroll_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Descarga el PDF/TXT del borrador de nómina. Solo owner o superuser."""
    _require_owner_or_superuser(current_user)
    draft = db.query(PayrollDraft).filter(PayrollDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Borrador no encontrado")
    if draft.owner_user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="No autorizado")
    if not draft.pdf_path or not Path(draft.pdf_path).exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    filename = os.path.basename(draft.pdf_path)
    media_type = "application/pdf" if filename.lower().endswith(".pdf") else "text/plain"
    return FileResponse(
        draft.pdf_path,
        media_type=media_type,
        filename=filename,
    )
