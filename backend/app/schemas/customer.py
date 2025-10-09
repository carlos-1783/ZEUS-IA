from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, EmailStr, Field, validator

# Base schemas
class ContactPersonBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Full name of the contact person")
    position: Optional[str] = Field(None, max_length=100, description="Job position or role")
    email: Optional[EmailStr] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, max_length=20, description="Phone number")
    mobile: Optional[str] = Field(None, max_length=20, description="Mobile number")
    is_primary: bool = Field(False, description="Whether this is the primary contact person")

class CustomerBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Customer/Company name")
    email: Optional[EmailStr] = Field(None, description="Primary email address")
    phone: Optional[str] = Field(None, max_length=20, description="Primary phone number")
    address: Optional[str] = Field(None, description="Physical address")
    tax_id: Optional[str] = Field(None, max_length=50, description="Tax identification number")
    notes: Optional[str] = Field(None, description="Additional notes or comments")
    is_company: bool = Field(True, description="Whether the customer is a company (True) or individual (False)")
    is_active: bool = Field(True, description="Whether the customer is active")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata as key-value pairs")

# Create schemas
class ContactPersonCreate(ContactPersonBase):
    pass

class CustomerCreate(CustomerBase):
    contacts: Optional[List[ContactPersonCreate]] = Field(
        None, 
        description="List of contact persons for this customer"
    )
    
    @validator('tax_id')
    def validate_tax_id(cls, v):
        if v and not v.isalnum():
            raise ValueError("Tax ID must contain only alphanumeric characters")
        return v

# Update schemas
class ContactPersonUpdate(ContactPersonBase):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    is_primary: Optional[bool] = None

class CustomerUpdate(CustomerBase):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    is_company: Optional[bool] = None
    is_active: Optional[bool] = None

# Response schemas
class ContactPersonInDB(ContactPersonBase):
    id: int
    customer_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }

class CustomerInDB(CustomerBase):
    id: int
    created_at: datetime
    updated_at: datetime
    contacts: List[ContactPersonInDB] = []

    model_config = {
        "from_attributes": True
    }

# Output models for API responses
class ContactPersonOut(ContactPersonBase):
    id: int
    customer_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }

class CustomerOut(CustomerBase):
    id: int
    created_at: datetime
    updated_at: datetime
    contacts: List[ContactPersonOut] = []

    model_config = {
        "from_attributes": True
    }

# Response models for API endpoints
class CustomerResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None
    data: CustomerOut

class ContactPersonResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None
    data: ContactPersonOut

class CustomerListResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None
    data: List[CustomerOut] = []
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
