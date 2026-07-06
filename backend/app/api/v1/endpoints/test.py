from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from services.zeus_phase_b_test_v1 import check_phase_b_env, run_test_contract_flow
from services.zeus_phase_c_test_v1 import check_phase_c_env, run_test_payment_risk_flow
from services.zeus_core_orchestrator_v1 import check_core_orchestration_env

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


@router.get("/phase-c-env")
async def phase_c_env_status(
    current_user: User = Depends(get_current_active_user),
):
    """Read-only Phase C flag check (no side effects)."""
    return {"success": True, **check_phase_c_env()}


@router.post("/payment-risk")
async def test_payment_risk_flow(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Safe Phase C test: emit payment_due → CRM risk scoring → RAFAEL agents.
    Synthetic demo payload only.
    """
    result = run_test_payment_risk_flow(db, current_user)
    return result


@router.get("/core-orchestration-env")
async def core_orchestration_env_status(
    current_user: User = Depends(get_current_active_user),
):
    """Read-only ZEUS CORE multi-agent flag check."""
    return {"success": True, **check_core_orchestration_env()}
