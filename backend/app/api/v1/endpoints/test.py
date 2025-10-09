from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional

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
