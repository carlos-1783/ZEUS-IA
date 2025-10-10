from fastapi import FastAPI, APIRouter
from pydantic import BaseModel
from typing import Optional

# Create a minimal FastAPI app
app = FastAPI()

# Create a test router
test_router = APIRouter()

class TestResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None

@test_router.get("/test-minimal", response_model=TestResponse)
async def test_minimal_endpoint():
    """Minimal test endpoint with no dependencies"""
    return {
        "success": True,
        "message": "Minimal test endpoint working",
        "data": {"test": "value"}
    }

# Include the router with the API prefix
app.include_router(test_router, prefix="/api/v1/test", tags=["test"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("minimal_app:app", host="0.0.0.0", port=8000, reload=True)
