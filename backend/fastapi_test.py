"""
A completely isolated FastAPI test that doesn't depend on the main application.
This helps verify if the basic FastAPI setup is working.
"""
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.testclient import TestClient
from pydantic import BaseModel
from typing import List, Optional

# Create a minimal FastAPI app
app = FastAPI()

# Define a simple Pydantic model
class Item(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    tax: Optional[float] = None

# In-memory database
fake_db = []

# Dependency
def get_db():
    return fake_db

# Test endpoint with dependency injection
@app.post("/items/", status_code=status.HTTP_201_CREATED)
async def create_item(item: Item, db: list = Depends(get_db)):
    db.append(item.dict())
    return {"success": True, "data": item.dict()}

# Test endpoint with query parameters
@app.get("/items/", response_model=dict)
async def read_items(
    skip: int = 0, 
    limit: int = 10,
    db: list = Depends(get_db)
):
    return {
        "success": True,
        "data": db[skip : skip + limit],
        "total": len(db),
        "skip": skip,
        "limit": limit
    }

# Run tests
if __name__ == "__main__":
    import uvicorn
    
    # Run the FastAPI app for manual testing
    print("Starting FastAPI test server on http://127.0.0.1:8000")
    print("Test endpoints:")
    print("  - POST /items/ - Create an item")
    print("  - GET  /items/?skip=0&limit=10 - List items")
    print("\nPress Ctrl+C to stop the server\n")
    
    # Run the server on port 8001
    uvicorn.run(app, host="0.0.0.0", port=8001)
