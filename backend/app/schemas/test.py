from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional

class TestTokenResponse(BaseModel):
    """Response model for the test token endpoint"""
    success: bool = Field(True, description="Indicates if the request was successful")
    message: str = Field(..., description="Status message")
    user: str = Field(..., description="Email of the authenticated user")

class ProtectedTestResponse(BaseModel):
    """Response model for the protected test endpoint"""
    success: bool = Field(True, description="Indicates if the request was successful")
    message: str = Field(..., description="Status message")
    user_id: int = Field(..., description="ID of the authenticated user")
    email: str = Field(..., description="Email of the authenticated user")
    is_active: bool = Field(..., description="Whether the user is active")
    is_superuser: bool = Field(..., description="Whether the user is a superuser")
    scopes: List[str] = Field(..., description="List of scopes the user has access to")
    permissions: List[str] = Field(..., description="List of permissions the user has")
