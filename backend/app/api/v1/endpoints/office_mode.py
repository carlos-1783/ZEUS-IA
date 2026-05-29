"""ZEUS Office Mode v1 — estado del modo oficina y exportaciones unificadas."""

from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from services import crm_office_service as crm_svc
from services.zeus_office_mode import OFFICE_MODE_V1

router = APIRouter()


@router.get("/mode")
def get_office_mode(
    current_user: User = Depends(get_current_active_user),
):
    """Configuración activa del modo oficina (módulos, reglas, UI)."""
    _ = current_user
    return {"success": True, "data": OFFICE_MODE_V1}


@router.get("/export/{entity}/excel")
def export_entity_excel(
    entity: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Exportación Excel estandarizada (clientes, expedientes, cobros)."""
    try:
        from openpyxl import Workbook  # pyright: ignore[reportMissingModuleSource]
    except ImportError as exc:
        raise RuntimeError("openpyxl no disponible") from exc

    wb = Workbook()
    ws = wb.active
    if entity == "clients":
        ws.title = "clients"
        ws.append(["id", "name", "email", "phone", "status", "created_at"])
        for row in crm_svc.list_customers(db, current_user):
            ws.append(
                [
                    row.id,
                    row.name,
                    row.email or "",
                    row.phone or "",
                    "active" if row.is_active else "inactive",
                    row.created_at.isoformat() if row.created_at else "",
                ]
            )
    elif entity == "cases":
        ws.title = "cases"
        ws.append(["id", "client_id", "title", "status", "amount", "paid", "created_at"])
        for row in crm_svc.list_cases_table(db, current_user):
            ws.append(
                [
                    row["id"],
                    row["client_id"],
                    row["title"],
                    row["status"],
                    row["amount"],
                    row["paid"],
                    row["created_at"].isoformat() if row.get("created_at") else "",
                ]
            )
    elif entity == "payments":
        ws.title = "payments"
        ws.append(["id", "case_id", "amount", "method", "status", "created_at"])
        for row in crm_svc.list_payments_table(db, current_user):
            ws.append(
                [
                    row["id"],
                    row["case_id"],
                    row["amount"],
                    row["method"],
                    row["status"],
                    row["created_at"].isoformat() if row.get("created_at") else "",
                ]
            )
    else:
        raise HTTPException(status_code=404, detail="Entidad no exportable")

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={entity}.xlsx"},
    )
