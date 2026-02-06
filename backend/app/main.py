# ========================================
# ZEUS-IA MAIN APPLICATION
# ========================================

import logging
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os

# Import your existing app
from app.core.config import settings
from app.api.v1 import api_router
from app.db.base import create_tables
from services.automation import start_agent_automation, stop_agent_automation
from app.db.initial_superuser import ensure_initial_superuser
from app.db.session import SessionLocal
from app.models.user import User
from app.models.agent_activity import AgentActivity
from services.activity_logger import ActivityLogger
from services.automation.handlers import resolve_handler
from services.automation.utils import merge_dict
from services.unified_agent_runtime import run_workspace_task
from datetime import datetime

# Create FastAPI app
app = FastAPI(
    title="ZEUS-IA API",
    description="Intelligent Assistant API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS seguro para producción: orígenes desde config, métodos y cabeceras explícitos
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
    allow_headers=["Content-Type", "Authorization", "Accept", "Origin", "X-Requested-With"],
    expose_headers=["Content-Disposition", "Content-Length", "Content-Type"],
)

# Middleware específico para WebSockets en Railway
# @app.middleware("http")
# async def websocket_middleware(request: Request, call_next):
#     # Permitir WebSocket upgrades
#     if request.headers.get("upgrade") == "websocket":
#         # Asegurar que las cabeceras necesarias estén presentes
#         response = await call_next(request)
#         response.headers["Upgrade"] = "websocket"
#         response.headers["Connection"] = "Upgrade"
#         return response
#     
#     return await call_next(request)

# Include API routes - IMPORTANTE: Debe estar ANTES del catch-all
app.include_router(api_router, prefix="/api/v1")

# Crear tablas al iniciar la aplicación
logger = logging.getLogger("zeus.startup")


def _execute_zeus_launch_started():
    """
    Ejecuta acción zeus_launch_started al arranque: crea AgentActivity y envía WhatsApp.
    """
    session = SessionLocal()
    try:
        # Obtener superusuario
        superuser = session.query(User).filter(User.is_superuser == True).first()
        if not superuser:
            logger.warning("No superuser found. Skipping zeus_launch_started action.")
            return
        
        # Crear actividad
        activity = ActivityLogger.log_activity(
            agent_name="ZEUS",
            action_type="zeus_launch_started",
            action_description="ZEUS launch started - sistema iniciado",
            details={
                "trigger": "startup",
                "requested_by": "system",
                "superuser_email": superuser.email,
            },
            user_email=superuser.email,
            status="pending",
            priority="high",
            visible_to_client=True,
        )
        if not activity:
            logger.error("Failed to create zeus_launch_started activity.")
            return
        
        # Ejecutar handler
        activity = session.query(AgentActivity).filter(AgentActivity.id == activity.id).first()
        if not activity:
            logger.error("Activity not found after creation.")
            return
        
        handler = resolve_handler(activity.agent_name, activity.action_type or "")
        if handler is None:
            logger.warning(f"No handler found for ZEUS:zeus_launch_started. Status: blocked_missing_handler")
            activity.status = "blocked_missing_handler"
            session.add(activity)
            session.commit()
            return
        
        result = run_workspace_task(activity)
        status_val = result.get("status", "completed")
        
        activity.status = status_val
        if "details_update" in result:
            activity.details = merge_dict(activity.details, result["details_update"])
        if "metrics_update" in result:
            activity.metrics = merge_dict(activity.metrics, result["metrics_update"])
        if result.get("executed_handler") is not None:
            activity.metrics = merge_dict(activity.metrics or {}, {"executed_handler": result["executed_handler"]})
        if status_val in ("completed", "executed_internal", "failed"):
            activity.completed_at = datetime.utcnow()
        
        session.add(activity)
        session.commit()
        
        logger.info(f"ZEUS launch started action executed. Status: {status_val}, Handler: {result.get('executed_handler')}")
    except Exception as e:
        logger.error(f"Error executing zeus_launch_started: {e}", exc_info=True)
    finally:
        session.close()


@app.on_event("startup")
async def startup_event():
    logger.info("Starting ZEUS-IA backend")
    create_tables()
    ensure_initial_superuser()
    await start_agent_automation()
    # Ejecutar acción de lanzamiento
    _execute_zeus_launch_started()
    logger.info("ZEUS-IA backend ready")


@app.on_event("shutdown")
async def shutdown_event():
    await stop_agent_automation()

# Serve static files (frontend) - FIXED
if os.path.exists("static"):
    static_abs = os.path.abspath("static")
    print(f"[DEBUG] Serving static files from: {static_abs}")
    try:
        print(f"[DEBUG] Static files: {os.listdir('static')}")
    except OSError:
        pass

    app.mount("/static", StaticFiles(directory="static"), name="static")

    # Mount assets directory for JS/CSS files
    if os.path.exists("static/assets"):
        app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")
        print("[DEBUG] Assets mounted at /assets")

    # Serve frontend for all non-API routes
    # IMPORTANTE: Este catch-all debe ejecutarse DESPUÉS de que FastAPI evalúe las rutas del router
    # FastAPI evalúa rutas en orden: primero rutas específicas, luego catch-alls
    # El problema es que el catch-all puede capturar antes. Solución: usar un regex que excluya "/api"
    from fastapi.routing import APIRoute
    
    @app.get("/{full_path:path}")
    async def serve_frontend(request: Request, full_path: str):
        # Si llegamos aquí y la ruta es de API, significa que no existe en el router
        # Pero NO debemos servir el frontend, sino devolver un 404 apropiado
        if full_path.startswith("api/"):
            from fastapi.responses import JSONResponse
            from fastapi import status
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "error": "API endpoint not found",
                    "path": f"/{full_path}",
                    "message": "The requested API endpoint does not exist. Check /api/docs for available endpoints."
                }
            )

        static_path = os.path.join("static", full_path)
        if os.path.isfile(static_path):
            return FileResponse(static_path)

        index_path = os.path.join("static", "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"error": "Frontend not built", "path": full_path}
else:
    print("[ERROR] Static directory not found!")

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "zeus-ia"}

# Debug endpoint para Railway
@app.get("/debug")
async def debug_info():
    import os
    return {
        "status": "debug",
        "database_url": "SET" if os.getenv("DATABASE_URL") else "NOT_SET",
        "secret_key": "SET" if os.getenv("SECRET_KEY") else "NOT_SET",
        "jwt_secret": "SET" if os.getenv("JWT_SECRET_KEY") else "NOT_SET",
        "environment": os.getenv("ENVIRONMENT", "NOT_SET"),
        "debug": os.getenv("DEBUG", "NOT_SET"),
        "websocket_support": "ENABLED",
        "cors_origins": settings.BACKEND_CORS_ORIGINS
    }

# WebSocket test endpoint
@app.get("/ws-test")
async def websocket_test():
    import os
    return {
        "message": "WebSocket endpoint available",
        "endpoint": "/api/v1/ws/{client_id}",
        "protocol": "wss://" if os.getenv("RAILWAY_ENVIRONMENT") else "ws://",
        "status": "ready",
        "railway_environment": os.getenv("RAILWAY_ENVIRONMENT", "NOT_SET"),
        "port": os.getenv("PORT", "8000"),
        "host": "0.0.0.0",
        "websocket_support": "ENABLED"
    }

# Railway WebSocket diagnostic
@app.get("/railway-ws-diagnostic")
async def railway_ws_diagnostic():
    import os
    import platform
    return {
        "platform": platform.system(),
        "python_version": platform.python_version(),
        "railway_environment": os.getenv("RAILWAY_ENVIRONMENT", "NOT_SET"),
        "port": os.getenv("PORT", "8000"),
        "host": "0.0.0.0",
        "websocket_endpoint": "/api/v1/ws/{client_id}",
        "cors_origins": settings.BACKEND_CORS_ORIGINS,
        "fastapi_version": "0.104.1",
        "uvicorn_version": "0.24.0",
        "websocket_support": "ENABLED",
        "middleware_configured": True
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)