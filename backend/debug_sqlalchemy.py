"""
Debug script to test SQLAlchemy session and FastAPI integration.
This script helps isolate the issue with SQLAlchemy session in FastAPI.
"""
import sys
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

# Add the project root to the Python path
project_root = str(Path(__file__).resolve().parent)
sys.path.append(project_root)

# Import only the minimum required SQLAlchemy components
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

# Create a simple in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

# Create engine and session
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Create a simple model
class Customer(Base):
    __tablename__ = "customers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    phone = Column(String, nullable=True)
    address = Column(String, nullable=True)
    tax_id = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    is_company = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

# Pydantic models
class CustomerBase(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    address: Optional[str] = None
    tax_id: Optional[str] = None
    notes: Optional[str] = None
    is_company: bool = False
    is_active: bool = True

class CustomerCreate(CustomerBase):
    pass

class CustomerInDB(CustomerBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    model_config = {
        "from_attributes": True
    }

class CustomerListResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None
    data: List[CustomerInDB] = []
    total: int = 0
    page: int = 1
    limit: int = 100
    total_pages: int = 1
    
    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat()
        },
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "success": True,
                "message": "Customers retrieved successfully",
                "data": [],
                "total": 0,
                "page": 1,
                "limit": 100,
                "total_pages": 1
            }
        }
    }

# Create FastAPI app
app = FastAPI()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Test endpoint with SQLAlchemy session
@app.get("/test-db", response_model=CustomerListResponse)
def test_db_endpoint(
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    try:
        # Simple query to test the database connection
        customers = db.query(Customer).offset(skip).limit(limit).all()
        
        # Convert to Pydantic models
        customers_data = [
            CustomerInDB(
                id=customer.id,
                name=customer.name,
                email=customer.email,
                phone=customer.phone,
                address=customer.address,
                tax_id=customer.tax_id,
                notes=customer.notes,
                is_company=customer.is_company,
                is_active=customer.is_active,
                created_at=customer.created_at,
                updated_at=customer.updated_at
            ) for customer in customers
        ]
        
        return CustomerListResponse(
            success=True,
            message="Test endpoint working with database",
            data=customers_data,
            total=len(customers_data),
            page=1,
            limit=limit,
            total_pages=1
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Run the server
if __name__ == "__main__":
    import uvicorn
    
    # Add some test data
    db = SessionLocal()
    try:
        # Check if we already have test data
        if not db.query(Customer).first():
            test_customer = Customer(
                name="Test Customer",
                email="test@example.com",
                phone="1234567890",
                is_company=False,
                is_active=True
            )
            db.add(test_customer)
            db.commit()
    except Exception as e:
        print(f"Error creating test data: {e}")
        db.rollback()
    finally:
        db.close()
    
    # Run the server
    print("\nStarting FastAPI test server with SQLAlchemy on http://127.0.0.1:8002")
    print("Test endpoint:")
    print("  - GET /test-db - Test database connection and query")
    print("\nPress Ctrl+C to stop the server\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8002)
