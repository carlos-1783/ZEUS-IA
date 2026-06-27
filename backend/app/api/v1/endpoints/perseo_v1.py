"""PERSEO v1 API — audit, status, video edit."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from services.perseo_audit_service_v1 import build_audit_report, build_feature_status_map
from services.perseo_video_engine_v1 import create_video_edit_job, get_video_job
from services.zeus_execution_controller_v1 import get_execution_status

router = APIRouter(prefix="/perseo", tags=["perseo"])


class VideoEditOperation(BaseModel):
    type: str
    start_sec: Optional[float] = None
    end_sec: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None


class VideoEditRequest(BaseModel):
    input_url: str = Field(..., min_length=1)
    operations: List[VideoEditOperation] = Field(default_factory=list)
    transaction_id: Optional[str] = None


@router.get("/status")
def perseo_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ = current_user
    execution = get_execution_status(db)
    features = build_feature_status_map(db)
    return {
        "success": True,
        "agent": "PERSEO",
        "execution_mode": execution["execution_mode"],
        "writes_enabled": execution["writes_enabled"],
        "feature_status_map": features,
        "zeus_module": "PERSEO",
    }


@router.get("/audit")
def perseo_audit(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ = current_user
    return {"success": True, **build_audit_report(db)}


@router.post("/video/edit")
def perseo_video_edit(
    body: VideoEditRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    ops = [o.model_dump(exclude_none=True) for o in body.operations]
    result = create_video_edit_job(
        db,
        current_user,
        input_url=body.input_url,
        operations=ops or None,
        transaction_id=body.transaction_id,
    )
    return {"success": True, **result}


@router.get("/video/jobs/{job_id}")
def perseo_video_job_status(
    job_id: str,
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    job = get_video_job(job_id, current_user.id)
    return {"success": job["status"] == "completed", **job}
