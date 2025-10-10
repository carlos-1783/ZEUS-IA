from fastapi import FastAPI
from pydantic import BaseModel

# Create a minimal FastAPI app
app = FastAPI()

class TestResponse(BaseModel):
    success: bool
    message: str

@app.get("/test-minimal", response_model=TestResponse)
async def test_minimal():
    """Minimal test endpoint with no dependencies"""
    return {"success": True, "message": "Minimal test endpoint working"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("minimal_test:app", host="0.0.0.0", port=8000, reload=True)
