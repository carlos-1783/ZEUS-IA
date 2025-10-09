"""
OpenAPI configuration for ZEUS-IA API.
"""
from fastapi.openapi.utils import get_openapi
from fastapi import FastAPI
from typing import Dict, Any, List


def set_custom_openapi(app: FastAPI) -> Dict[str, Any]:
    """Generate the OpenAPI schema with proper versioning and configuration."""
    if app.openapi_schema:
        return app.openapi_schema
    
    # Define servers
    servers = [
        {
            "url": "http://localhost:8000",
            "description": "Local development server"
        },
        {
            "url": "https://api.zeus-ia.com",
            "description": "Production server"
        }
    ]
    
    # Let FastAPI generate the schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description or "ZEUS-IA API Documentation",
        routes=app.routes,
        servers=servers,
    )
    
    # Ensure the OpenAPI version is set correctly
    openapi_schema["openapi"] = "3.0.0"
    
    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "OAuth2PasswordBearer": {
            "type": "oauth2",
            "flows": {
                "password": {
                    "tokenUrl": "api/v1/auth/login",
                    "scopes": {}
                }
            }
        }
    }
    
    # Add security requirements
    openapi_schema["security"] = [{"OAuth2PasswordBearer": []}]
    
    # Add tags
    openapi_schema["tags"] = [
        {
            "name": "auth",
            "description": "Authentication and user management"
        },
        {
            "name": "system",
            "description": "System operations and monitoring"
        },
        {
            "name": "commands",
            "description": "Command execution and management"
        },
        {
            "name": "customers",
            "description": "Customer management"
        }
    ]
    
    # Cache the schema
    app.openapi_schema = openapi_schema
    return openapi_schema
