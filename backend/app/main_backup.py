import os
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.core.config import settings
from app.core.middlewares import setup_middlewares
from app.core.routes import setup_routes
from app.core.docs import setup_docs, set_custom_openapi

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestor del ciclo de vida de la aplicación.
    
    Args:
        app: Instancia de FastAPI
    """
    # Inicio de la aplicación
    print(f"Iniciando {settings.PROJECT_NAME} v{settings.VERSION}")
    print(f"Entorno: {'Desarrollo' if settings.DEBUG else 'Producción'}")
    print(f"Servidor ejecutándose en http://{settings.HOST}:{settings.PORT}")
    
    # Crear directorios necesarios
    os.makedirs(settings.STATIC_DIR, exist_ok=True)
    
    yield
    
    # Limpieza al cerrar
    print("Deteniendo la aplicación...")

# Configuración de metadatos de la API
api_metadata = {
    "title": settings.PROJECT_NAME,
    "description": """
    # ZEUS-IA API
    
    Bienvenido a la documentación de la API de ZEUS-IA.
    
    ## Autenticación
    
    La mayoría de los endpoints requieren autenticación. Para autenticarse, use el endpoint `/api/v1/auth/login`
    con sus credenciales para obtener un token de acceso.
    
    Incluya el token en el encabezado `Authorization: Bearer <token>` para las solicitudes autenticadas.
    """,
    "version": settings.VERSION,
    "debug": settings.DEBUG,
    "docs_url": "/api/docs" if settings.DEBUG else None,
    "redoc_url": "/api/redoc" if settings.DEBUG else None,
    "openapi_url": "/api/openapi.json" if settings.DEBUG else None,
    "openapi_tags": [
        {
            "name": "auth",
            "description": "Operaciones de autenticación y usuarios"
        },
        {
            "name": "system",
            "description": "Operaciones del sistema"
        },
        {
            "name": "commands",
            "description": "Ejecución de comandos"
        },
        {
            "name": "customers",
            "description": "Gestión de clientes"
        }
    ]
}

# Crear instancia de FastAPI
app = FastAPI(
    **{k: v for k, v in api_metadata.items() if k not in ['debug']},
    lifespan=lifespan
)

# Configurar middlewares
setup_middlewares(app)

# Configurar rutas
setup_routes(app)

# Configurar documentación
setup_docs(app)

# Aplicar esquema OpenAPI personalizado
app.openapi = lambda: set_custom_openapi(app)
        if not settings.DEBUG:
            csp_parts = [
                "default-src 'self';",
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://www.google-analytics.com https://www.gstatic.com https://www.recaptcha.net;",
                "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://fonts.googleapis.com;",
                "style-src-elem 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://fonts.googleapis.com;",
                "img-src 'self' data: https:;",
                "font-src 'self' data: https://cdnjs.cloudflare.com https://fonts.gstatic.com;",
                "connect-src 'self' https://api.example.com https://www.google-analytics.com;",
                "frame-src 'self' https://www.google.com https://www.recaptcha.net;",
                "object-src 'none';",
                "form-action 'self';",
                "base-uri 'self';"
            ]

        # Configuración de seguridad base
        security_headers = {
            'X-Content-Type-Options': 'nosniff',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
            'Cross-Origin-Opener-Policy': 'same-origin',
            'Cross-Origin-Resource-Policy': 'cross-origin',
            'Access-Control-Allow-Credentials': 'true',
            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Requested-With'
        }
        
        # Configuración de caché para recursos estáticos
        if path.startswith(settings.STATIC_URL):
            security_headers = {
                'Cache-Control': 'public, max-age=31536000, immutable',
                'Cross-Origin-Resource-Policy': 'cross-origin',
                'Content-Security-Policy': ' '.join(csp_parts)
            }
            # Eliminar cabeceras de no-cache para estáticos
            response.headers.pop('Pragma', None)
            response.headers.pop('Expires', None)
        else:
            # Configuración para rutas dinámicas
            security_headers = {
                'Cache-Control': 'no-store, max-age=0',
                'Content-Security-Policy': ' '.join(csp_parts)
            }
        
        # Configuración de tipo de contenido con charset
        content_type = response.headers.get('Content-Type', '').lower()
        if 'text/html' in content_type and 'charset=' not in content_type:
            response.headers['Content-Type'] = 'text/html; charset=utf-8'
        elif 'application/json' in content_type and 'charset=' not in content_type:
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
        elif 'text/css' in content_type:
            response.headers['Content-Type'] = 'text/css; charset=utf-8'
        elif 'javascript' in content_type or 'application/javascript' in content_type or 'text/javascript' in content_type:
            response.headers['Content-Type'] = 'application/javascript; charset=utf-8'
        
        # Otras cabeceras de seguridad
        security_headers.update({
            'X-Content-Type-Options': 'nosniff',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
            'Cross-Origin-Opener-Policy': 'same-origin',
            'Cross-Origin-Resource-Policy': 'cross-origin',
            'Access-Control-Allow-Origin': ', '.join(settings.BACKEND_CORS_ORIGINS) if settings.BACKEND_CORS_ORIGINS else '*',
            'Access-Control-Allow-Credentials': 'true',
            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Requested-With'
        })
        
        # Eliminar cabeceras obsoletas de forma segura
        for header in ['X-Frame-Options', 'X-XSS-Protection']:
            if header in response.headers:
                del response.headers[header]

        # AÃ±adir cabeceras CORP especÃ­ficas para recursos estÃ¡ticos
        if request.url.path.startswith(settings.STATIC_URL):
            response.headers['Cross-Origin-Resource-Policy'] = 'cross-origin'
            response.headers['Cross-Origin-Embedder-Policy'] = 'credentialless'
            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
            
            # AÃ±adir tipos de contenido especÃ­ficos para recursos estÃ¡ticos
            if request.url.path.endswith(('.js', '.mjs')):
                response.headers['Content-Type'] = 'application/javascript; charset=utf-8'
            elif request.url.path.endswith(('.css')):
                response.headers['Content-Type'] = 'text/css; charset=utf-8'
            elif request.url.path.endswith(('.woff2', '.woff', '.ttf')):
                response.headers['Content-Type'] = 'font/woff2'
            elif request.url.path.endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg')):
                response.headers['Content-Type'] = 'image/png'  # Ajustar segÃºn el tipo de imagen
        
        # AÃ±adir cabeceras CORP para endpoints API
        elif request.url.path.startswith(settings.API_V1_STR):
            response.headers['Cross-Origin-Resource-Policy'] = 'cross-origin'
            response.headers['Cross-Origin-Embedder-Policy'] = 'require-corp'
            response.headers['Cache-Control'] = 'no-store, max-age=0'
        
        # AÃ±adir cabeceras CORP para docs y endpoints pÃºblicos
        elif request.url.path in ['/docs', '/redoc', '/openapi.json']:
            response.headers['Cross-Origin-Resource-Policy'] = 'cross-origin'
            response.headers['Cross-Origin-Embedder-Policy'] = 'credentialless'
            response.headers['Cache-Control'] = 'no-store, max-age=0'
        
        # AÃ±adir cabeceras CORP para el resto de endpoints
        else:
            response.headers['Cross-Origin-Resource-Policy'] = 'same-site'
            response.headers['Cross-Origin-Embedder-Policy'] = 'require-corp'
            response.headers['Cache-Control'] = 'no-store, max-age=0'
        
        # AÃ±adir todas las demÃ¡s cabeceras de seguridad
        for header, value in security_headers.items():
            if value:
                response.headers[header] = value

        # Forzar charset=utf-8 en Content-Type de HTML y JS
        if request.url.path.endswith('.js') or request.url.path.endswith('.mjs'):
            response.headers['Content-Type'] = 'application/javascript; charset=utf-8'
        elif request.url.path.endswith('.css'):
            response.headers['Content-Type'] = 'text/css; charset=utf-8'
        elif request.url.path.endswith('.html'):
            response.headers['Content-Type'] = 'text/html; charset=utf-8'
        # Eliminar Expires si existe
        if 'Expires' in response.headers:
            del response.headers['Expires']

        return response

# Configuración de CORS
# Usamos los orígenes definidos en settings.BACKEND_CORS_ORIGINS
# que ya incluyen los puertos 5173 (frontend) y 8000 (backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],  # Expose all headers to the client
    max_age=600
)

# Middleware para asegurar que los encabezados CORS estén presentes
# y manejar correctamente las solicitudes OPTIONS (preflight)
@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    # Handle WebSocket upgrade requests
    if "upgrade" in request.headers.get("connection", "").lower() and \
       request.headers.get("upgrade", "").lower() == "websocket":
        # For WebSocket connections, we need to handle CORS manually
        origin = request.headers.get("origin")
        if origin and origin in settings.BACKEND_CORS_ORIGINS:
            response = await call_next(request)
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Headers"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            return response
        else:
            return Response(
                content=json.dumps({"detail": "Not allowed by CORS"}),
                status_code=403,
                media_type="application/json"
            )
        
    # Handle OPTIONS (preflight) requests
    if request.method == "OPTIONS":
        origin = request.headers.get("origin")
        if origin and origin in settings.BACKEND_CORS_ORIGINS:
            response = Response(
                status_code=200,
                headers={
                    "Access-Control-Allow-Origin": origin,
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With",
                    "Access-Control-Allow-Credentials": "true",
                    "Access-Control-Max-Age": "600"
                }
            )
            return response
    
    # For normal requests, continue with the normal flow
    response = await call_next(request)
    
    # Ensure CORS headers are present for allowed origins
    origin = request.headers.get("origin")
    if origin and origin in settings.BACKEND_CORS_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    
    return response

# Add CSP middleware at the application level
@app.middleware("http")
async def add_csp_header(request: Request, call_next):
    # First, get the response
    response = await call_next(request)
    
    # Only add CSP for HTML responses
    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type:
        return response
    
    # Create a new response with the same content
    from fastapi.responses import HTMLResponse
    from copy import deepcopy
    
    # Get the response content
    if hasattr(response, 'body'):
        content = response.body
    elif hasattr(response, 'body_iterator'):
        content = b''.join([chunk async for chunk in response.body_iterator])
    else:
        content = b''
    
    # Create a new response with the same content and status code
    new_response = HTMLResponse(
        content=content,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.media_type
    )
    
    # Create a very permissive CSP for development
    csp = (
        "default-src * 'unsafe-inline' 'unsafe-eval' data: blob:; "
        "script-src * 'unsafe-inline' 'unsafe-eval' data: blob:; "
        "style-src * 'unsafe-inline' 'unsafe-eval' data: blob:; "
        "img-src * data: blob: 'unsafe-inline' 'unsafe-eval'; "
        "font-src * data: blob: 'unsafe-inline' 'unsafe-eval'; "
        "connect-src * 'unsafe-inline' 'unsafe-eval' data: blob:; "
        "frame-src * 'unsafe-inline' 'unsafe-eval' data: blob:; "
        "media-src * 'unsafe-inline' 'unsafe-eval' data: blob:; "
        "object-src * 'unsafe-inline' 'unsafe-eval' data: blob:; "
        "form-action * 'unsafe-inline' 'unsafe-eval' data: blob:; "
        "base-uri * 'unsafe-inline' 'unsafe-eval' data: blob:; "
        "worker-src * 'unsafe-inline' 'unsafe-eval' data: blob:;"
    )
    
    # Set the CSP header
    new_response.headers["Content-Security-Policy"] = csp
    
    # Remove other CSP headers if they exist
    if "X-Content-Security-Policy" in new_response.headers:
        del new_response.headers["X-Content-Security-Policy"]
    if "X-WebKit-CSP" in new_response.headers:
        del new_response.headers["X-WebKit-CSP"]
    
    return new_response

# Then add other middleware
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

if not settings.DEBUG:
    app.add_middleware(HTTPSRedirectMiddleware)
    
    # Solo en producciÃ³n, forzar HTTPS y otras polÃ­ticas de seguridad
    security_headers = {
        "Strict-Transport-Security": f"max-age={settings.SECURE_HSTS_SECONDS}; includeSubDomains; preload",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Embedder-Policy": "require-corp",
        "Cross-Origin-Resource-Policy": "same-site"
    }

# Health check endpoint
@app.get("/health", include_in_schema=False)
async def health_check():
    return {"status": "ok", "service": "ZEUS-IA", "version": "1.0"}

# Favicon handler
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    favicon_path = os.path.join("static", 'favicon.ico')
    if not os.path.exists(favicon_path):
        with open(favicon_path, 'wb') as f:
            f.write(b'\x00\x00\x01\x00\x01\x00\x10\x10\x00\x00\x01\x00\x20\x00\x68\x04\x00\x00\x16\x00\x00\x00\x28\x00\x00\x00\x10\x00\x00\x00\x20\x00\x00\x00\x01\x00\x20\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')
    return FileResponse(favicon_path, media_type='image/x-icon')

# Configuración de archivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configuración de Swagger UI
templates = Jinja2Templates(directory="templates")

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html(request: Request):
    return templates.TemplateResponse(
        "swagger_ui.html",
        {
            "request": request,
            "openapi_url": "/openapi.json",
            "title": "ZEUS-IA - Swagger UI",
            "favicon_url": "/static/favicon.ico",
            "swagger_css_url": "/static/swagger-ui.css",
            "swagger_js_url": "/static/swagger-ui-bundle.js",
            "swagger_standalone_preset_js_url": "/static/swagger-ui-standalone-preset.js"
        }
    )

# Configuración de OpenAPI
@app.get("/openapi.json", include_in_schema=False)
async def get_openapi_endpoint():
    return JSONResponse(app.openapi())

# Root redirect to docs
@app.get("/", include_in_schema=False)
async def root():
    """Redirect root to API documentation"""
    return RedirectResponse(
        url="/api/docs",
        status_code=status.HTTP_308_PERMANENT_REDIRECT
    )

# Redirect /docs to /api/docs for easier access
@app.get("/docs", include_in_schema=False)
async def redirect_docs():
    """Redirect /docs to /api/docs"""
    return RedirectResponse(url="/api/docs", status_code=status.HTTP_308_PERMANENT_REDIRECT)

# Swagger UI initialization script
@app.get("/docs/swagger-ui-init.js", include_in_schema=False)
async def swagger_ui_init_js():
    """Serve the Swagger UI initialization script"""
    ensure_static_files()
    return FileResponse(
        os.path.join(settings.STATIC_DIR, "swagger-ui-init.js"),
        media_type="application/javascript; charset=utf-8",
        headers={
            "Cache-Control": "public, max-age=86400",
            "Cross-Origin-Resource-Policy": "cross-origin"
        }
    )

if __name__ == "__main__":
    # Importar uvicorn aquí para evitar cargarlo durante las pruebas
    import uvicorn
    
    # Ejecutar la aplicación
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else 4,
        log_level="info" if settings.DEBUG else "warning",
        proxy_headers=True,
        forwarded_allow_ips="*" if settings.DEBUG else settings.TRUSTED_HOSTS,
    )