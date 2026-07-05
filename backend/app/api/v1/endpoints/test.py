from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from services.zeus_phase_b_test_v1 import check_phase_b_env, run_test_contract_flow

router = APIRouter()

class TestResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None

@router.get("/test-minimal", response_model=TestResponse)
async def test_minimal_endpoint():
    """
    Minimal test endpoint with no dependencies
    """
    return {
        "success": True,
        "message": "Minimal test endpoint working",
        "data": {"test": "value"}
    }


@router.get("/phase-b-env")
async def phase_b_env_status(
    current_user: User = Depends(get_current_active_user),
):
    """Read-only Phase B flag check (no side effects)."""
    return {"success": True, **check_phase_b_env()}


@router.post("/contract-flow")
async def test_contract_flow(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Safe Phase B test: emit contract_rrhh_created on real event bus.
    Synthetic payload only — does not require employee in company_employees.
    """
    result = run_test_contract_flow(db, current_user)
    return result
