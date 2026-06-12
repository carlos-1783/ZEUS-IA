"""ZEUS time & cost engine v1 — POST /checkin y analytics."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.company import UserCompany
from app.models.user import User
from services.time_cost_engine_v1 import (
    get_active_sessions,
    get_cost_analytics,
    refresh_partial_costs,
    register_checkin,
)

router = APIRouter()


def _primary_company_id(db: Session, user: User) -> Optional[int]:
    link = (
        db.query(UserCompany)
        .filter(UserCompany.user_id == user.id)
        .order_by(UserCompany.id.asc())
        .first()
    )
    return int(link.company_id) if link else None


class CheckinRequest(BaseModel):
    company_id: int
    employee_id: str
    type: str = Field(..., description="entrada|salida|pausa_inicio|pausa_fin")
    method: str = Field(..., description="qr|pin|geo|device")
    qr_token: Optional[str] = None
    pin: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    device_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


def _metadata_from_request(body: CheckinRequest) -> Dict[str, Any]:
    meta = dict(body.metadata or {})
    if body.qr_token and "qr_token" not in meta:
        meta["qr_token"] = body.qr_token
    if body.pin and "pin" not in meta:
        meta["pin"] = body.pin
    if body.lat is not None and "lat" not in meta:
        meta["lat"] = body.lat
    if body.lng is not None and "lng" not in meta:
        meta["lng"] = body.lng
    if body.device_id and "device_id" not in meta:
        meta["device_id"] = body.device_id
    return meta


@router.post("")
async def post_checkin(
    body: CheckinRequest,
    http_req: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Registrar fichaje real (entrada/salida/pausa) con validación y coste."""
    client_ip = http_req.client.host if http_req.client else None
    user_agent = (http_req.headers.get("user-agent") or "")[:512] or None
    device_id = body.device_id or (http_req.headers.get("x-device-id") or "").strip() or None
    return register_checkin(
        db,
        user=current_user,
        company_id=body.company_id,
        employee_id=body.employee_id,
        checkin_type=body.type,
        method=body.method,
        metadata=_metadata_from_request(body),
        client_ip=client_ip,
        device_id=device_id,
        user_agent=user_agent,
    )


@router.get("/analytics")
async def checkin_analytics(
    company_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    cid = company_id or _primary_company_id(db, current_user)
    if not cid:
        raise HTTPException(status_code=400, detail="company_id requerido.")
    refresh_partial_costs(db, company_id=cid)
    analytics = get_cost_analytics(db, user=current_user, company_id=cid)
    analytics["active_sessions"] = get_active_sessions(db, user=current_user, company_id=cid)
    return {"success": True, **analytics}


@router.get("/sessions/active")
async def active_checkin_sessions(
    company_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    cid = company_id or _primary_company_id(db, current_user)
    if not cid:
        raise HTTPException(status_code=400, detail="company_id requerido.")
    sessions = get_active_sessions(db, user=current_user, company_id=cid)
    return {"success": True, "company_id": cid, "active_sessions": sessions}
