from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional

# Create a minimal FastAPI app
app = FastAPI()

# Define a response model
class TestResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None

# Define a test endpoint directly in the app
@app.get("/api/v1/test-direct", response_model=TestResponse)
async def test_direct_endpoint():
    """Direct test endpoint without router"""
    return {
        "success": True,
        "message": "Direct endpoint working correctly",
        "data": {"test": "value"}
    }

# Root endpoint
@app.get("/")
async def root():
    return {"message": "Direct FastAPI application"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("direct_fastapi:app", host="0.0.0.0", port=8001, reload=True)
