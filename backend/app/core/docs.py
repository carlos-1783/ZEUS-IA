from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
from typing import Dict, Any
import json

def set_custom_openapi(app: FastAPI) -> Dict[str, Any]:
    """Genera un esquema OpenAPI personalizado para la documentación."""
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Personalización del esquema OpenAPI
    openapi_schema["info"]["x-logo"] = {
        "url": "/static/logo.png"
    }
    
    # Configuración de seguridad
    openapi_schema["components"]["securitySchemes"] = {
        "OAuth2PasswordBearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Ingrese el token JWT con el prefijo `Bearer `"
        }
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

def setup_docs(app: FastAPI):
    """Configura la documentación de la API (Swagger UI y ReDoc)."""
    # Solo habilitar documentación en desarrollo
    if not app.debug:
        return app
    
    # Configuración personalizada de Swagger UI
    @app.get("/api/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        return get_swagger_ui_html(
            openapi_url="/api/openapi.json",
            title=f"{app.title} - Swagger UI",
            oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
            # Usar CDN para cargar los recursos de Swagger UI
            swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
            swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
            swagger_favicon_url="/static/favicon.ico",
        )
    
    # Configuración personalizada de ReDoc
    @app.get("/api/redoc", include_in_schema=False)
    async def redoc_html():
        return get_redoc_html(
            openapi_url="/api/openapi.json",
            title=f"{app.title} - ReDoc",
            redoc_js_url="/static/redoc.standalone.js",
            with_google_fonts=False,
        )
    
    # Endpoint para el esquema OpenAPI
    @app.get("/api/openapi.json", include_in_schema=False)
    async def get_openapi_endpoint():
        return app.openapi()
    
    return app
