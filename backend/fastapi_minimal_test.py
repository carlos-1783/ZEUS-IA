from fastapi import FastAPI, Depends, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session

# Create a minimal FastAPI app for testing
app = FastAPI()

# Minimal Pydantic models
class ItemBase(BaseModel):
    name: str
    description: Optional[str] = None

class ItemCreate(ItemBase):
    pass

class Item(ItemBase):
    id: int
    
    class Config:
        from_attributes = True

# In-memory database for testing
fake_db = {}

# Minimal endpoint without database dependency
@app.get("/test-minimal", response_model=dict)
async def test_minimal():
    return {"status": "success", "message": "Minimal test endpoint is working"}

# Endpoint with a simple dependency
@app.get("/test-dependency", response_model=dict)
async def test_with_dependency(skip: int = 0, limit: int = 10):
    return {
        "status": "success",
        "message": "Test with query parameters",
        "skip": skip,
        "limit": limit
    }

# Create a test client
client = TestClient(app)

def test_minimal_endpoint():
    response = client.get("/test-minimal")
    assert response.status_code == 200
    assert response.json() == {"status": "success", "message": "Minimal test endpoint is working"}

def test_dependency_endpoint():
    response = client.get("/test-dependency?skip=5&limit=20")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["skip"] == 5
    assert data["limit"] == 20

if __name__ == "__main__":
    import uvicorn
    print("Running minimal FastAPI server on http://localhost:8001")
    print("Test endpoints:")
    print("  - GET /test-minimal")
    print("  - GET /test-dependency?skip=0&limit=10")
    uvicorn.run(app, host="0.0.0.0", port=8001)
