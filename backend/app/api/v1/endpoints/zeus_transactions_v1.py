"""ZEUS transaction orchestration API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from services.zeus_transaction_system_v1 import (
    create_transaction,
    execute_transaction,
    get_health,
    get_transaction,
)

router = APIRouter(prefix="/zeus", tags=["zeus-transactions"])


class TransactionInitiator(BaseModel):
    type: str = Field(default="USER")
    id: str = ""
    source: str = Field(default="API")


class TransactionContextBody(BaseModel):
    workspace_id: Optional[str] = None
    correlation_id: Optional[str] = None
    request_id: Optional[str] = None


class TransactionStepBody(BaseModel):
    module: str
    action: str
    input: Dict[str, Any] = Field(default_factory=dict)
    max_retries: int = 3


class TransactionCreateRequest(BaseModel):
    initiator: TransactionInitiator = Field(default_factory=TransactionInitiator)
    context: TransactionContextBody = Field(default_factory=TransactionContextBody)
    steps: List[TransactionStepBody] = Field(..., min_length=1)
    idempotency_key: Optional[str] = None


@router.post("/transactions")
def zeus_transaction_create(
    body: TransactionCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    initiator = body.initiator.model_dump()
    initiator.setdefault("id", str(current_user.id))
    return {
        "success": True,
        **create_transaction(
            db,
            current_user,
            initiator=initiator,
            context=body.context.model_dump(),
            steps=[s.model_dump() for s in body.steps],
            idempotency_key=body.idempotency_key,
        ),
    }


@router.get("/transactions/{transaction_id}")
def zeus_transaction_get(
    transaction_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ = current_user
    return {"success": True, **get_transaction(db, transaction_id)}


@router.post("/transactions/{transaction_id}/execute")
def zeus_transaction_execute(
    transaction_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return {"success": True, **execute_transaction(db, current_user, transaction_id)}


@router.get("/health")
def zeus_orchestrator_health(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ = current_user
    return {"success": True, **get_health(db)}
