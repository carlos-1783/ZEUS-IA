"""
📋 Payroll Drafts - Listar y descargar borradores de nómina
"""
from pathlib import Path
import os

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from app.models.payroll_draft import PayrollDraft

router = APIRouter(prefix="/payroll", tags=["payroll"])

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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Lista borradores de nómina del usuario/empresa. Solo owner o superuser."""
    _require_owner_or_superuser(current_user)
    drafts = (
        db.query(PayrollDraft)
        .filter(PayrollDraft.company_id == current_user.id)
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
    if draft.company_id != current_user.id and not current_user.is_superuser:
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
