# ========================================
# ZEUS-IA MAIN APPLICATION
# ========================================

import logging
import sys
import os
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.core.security_middleware import SecurityMiddleware

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


def _configure_zeus_startup_logger() -> logging.Logger:
    """
    INFO en stdout: agregadores (Railway, drains, etc.) suelen marcar como 'error' todo stderr,
    aunque el nivel sea INFO. ZEUS_LOG_INFO_TO_STDOUT=false desactiva este comportamiento.
    """
    log = logging.getLogger("zeus.startup")
    if os.getenv("ZEUS_LOG_INFO_TO_STDOUT", "true").lower() not in ("1", "true", "yes", "on"):
        return log
    if getattr(log, "_zeus_stdout_configured", False):
        return log
    log._zeus_stdout_configured = True  # type: ignore[attr-defined]
    log.handlers.clear()
    log.setLevel(logging.INFO)
    log.propagate = False
    fmt = logging.Formatter("%(levelname)s:%(name)s:%(message)s")
    h_info = logging.StreamHandler(sys.stdout)
    h_info.setLevel(logging.DEBUG)
    h_info.addFilter(lambda r: r.levelno < logging.ERROR)
    h_info.setFormatter(fmt)
    h_err = logging.StreamHandler(sys.stderr)
    h_err.setLevel(logging.ERROR)
    h_err.setFormatter(fmt)
    log.addHandler(h_info)
    log.addHandler(h_err)
    return log


# Create FastAPI app
app = FastAPI(
    title="ZEUS-IA API",
    description="Intelligent Assistant API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS: orígenes desde config. OPTIONS (preflight) responde 200 desde el middleware.
# ZEUS_LOCAL_CORS_FIX_001: allow_headers y max_age desde config para compatibilidad local.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=getattr(settings, "CORS_ALLOW_METHODS", ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]),
    allow_headers=getattr(settings, "CORS_ALLOW_HEADERS", ["Content-Type", "Authorization", "Accept", "Origin", "X-Requested-With"]),
    expose_headers=getattr(settings, "CORS_EXPOSE_HEADERS", ["Content-Disposition", "Content-Length", "Content-Type"]),
    max_age=getattr(settings, "CORS_MAX_AGE", 600),
)
app.add_middleware(SecurityMiddleware)


@app.middleware("http")
async def uncaught_exception_guard(request: Request, call_next):
    """Última red: respuesta JSON 500 sin tumbar el proceso ante bugs inesperados."""
    try:
        return await call_next(request)
    except StarletteHTTPException:
        raise
    except Exception:
        logging.getLogger("zeus.api").exception("uncaught path=%s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Error interno del servidor. El servicio sigue activo; reintenta."},
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
logger = _configure_zeus_startup_logger()


def _is_railway_runtime() -> bool:
    """Railway inyecta estas variables; el nombre del entorno puede no ser literal 'production'."""
    return bool(
        os.getenv("RAILWAY_PROJECT_ID")
        or os.getenv("RAILWAY_SERVICE_ID")
        or os.getenv("RAILWAY_PUBLIC_DOMAIN")
        or os.getenv("RAILWAY_GIT_COMMIT_SHA")
        or os.getenv("RAILWAY_ENVIRONMENT")
    )


def _should_run_startup_launch_activity() -> bool:
    """
    En Railway (cualquier entorno con nombre) no ejecutar por defecto: evita actividad + WhatsApp en cada deploy.
    Activa con ZEUS_STARTUP_LAUNCH_ACTIVITY=true. Desactiva explícitamente con =false.
    """
    raw = (os.getenv("ZEUS_STARTUP_LAUNCH_ACTIVITY") or "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    if _is_railway_runtime():
        return False
    return True


def _execute_zeus_launch_started():
    """
    Opcional: actividad interna + WhatsApp al superusuario (solo si ZEUS_LAUNCH_WHATSAPP=true).
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
            visible_to_client=False,
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
    # Por defecto SÍ: sin tablas/superuser el API cae en cascada. Solo omitir si se pide explícitamente.
    skip_db = os.getenv("ZEUS_SKIP_STARTUP_DB_INIT", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    if not skip_db:
        create_tables()
        ensure_initial_superuser()
    else:
        logger.warning(
            "ZEUS_SKIP_STARTUP_DB_INIT activo: no se ejecutan create_tables ni ensure_initial_superuser."
        )
    await start_agent_automation()
    if _should_run_startup_launch_activity():
        _execute_zeus_launch_started()
    else:
        logger.info(
            "Omitido zeus_launch_started (producción por defecto). "
            "Pon ZEUS_STARTUP_LAUNCH_ACTIVITY=true para activarlo."
        )
    logger.info("ZEUS-IA backend ready")


@app.on_event("shutdown")
async def shutdown_event():
    await stop_agent_automation()

# Serve static files: misma ruta absoluta que upload.py (settings.STATIC_DIR).
# Antes se usaba directory="static" relativo al CWD; si uvicorn no arranca desde /app/backend,
# las subidas escribían en un sitio y /static leía otro → 404 en vídeos/imágenes.
static_root = os.path.abspath(settings.STATIC_DIR)
os.makedirs(static_root, exist_ok=True)
for _sub in ("images", "videos", "documents", "media"):
    os.makedirs(os.path.join(static_root, "uploads", _sub), exist_ok=True)

if settings.ENVIRONMENT.lower() in ("production", "staging"):
    logger.warning(
        "Archivos en %s: sin volumen persistente (Railway/VPS) las subidas se pierden al redeploy; "
        "monta un volumen en STATIC_DIR o usa almacenamiento externo.",
        static_root,
    )

print(f"[DEBUG] Serving /static from: {static_root}")
try:
    print(f"[DEBUG] Static top-level: {os.listdir(static_root)[:20]}")
except OSError:
    pass

app.mount("/static", StaticFiles(directory=static_root), name="static")

assets_dir = os.path.join(static_root, "assets")
if os.path.isdir(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    print("[DEBUG] Assets mounted at /assets")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "zeus-ia"}


@app.get("/debug")
async def debug_info():
    return {
        "status": "debug",
        "database_url": "SET" if os.getenv("DATABASE_URL") else "NOT_SET",
        "secret_key": "SET" if os.getenv("SECRET_KEY") else "NOT_SET",
        "jwt_secret": "SET" if os.getenv("JWT_SECRET_KEY") else "NOT_SET",
        "environment": os.getenv("ENVIRONMENT", "NOT_SET"),
        "debug": os.getenv("DEBUG", "NOT_SET"),
        "websocket_support": "ENABLED",
        "cors_origins": settings.BACKEND_CORS_ORIGINS,
        "static_dir": static_root,
    }


@app.get("/ws-test")
async def websocket_test():
    return {
        "message": "WebSocket endpoint available",
        "endpoint": "/api/v1/ws/{client_id}",
        "protocol": "wss://" if os.getenv("RAILWAY_ENVIRONMENT") else "ws://",
        "status": "ready",
        "railway_environment": os.getenv("RAILWAY_ENVIRONMENT", "NOT_SET"),
        "port": os.getenv("PORT", "8000"),
        "host": "0.0.0.0",
        "websocket_support": "ENABLED",
    }


_BUNDLED_CLEAR_PWA = Path(__file__).resolve().parent / "static_pages" / "clear_pwa_cache.html"


@app.get("/clear-pwa-cache.html", include_in_schema=False)
async def serve_clear_pwa_cache_bundled():
    """PWA: siempre disponible (Nixpacks sin dist / caché rota)."""
    try:
        if _BUNDLED_CLEAR_PWA.is_file():
            return HTMLResponse(_BUNDLED_CLEAR_PWA.read_text(encoding="utf-8"))
    except OSError:
        pass
    return HTMLResponse(
        "<!DOCTYPE html><html><body><p>Limpiar caché: usa herramientas del navegador (borrar datos del sitio).</p></body></html>",
        status_code=200,
    )


@app.get("/railway-ws-diagnostic")
async def railway_ws_diagnostic():
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
        "middleware_configured": True,
    }


def _frontend_missing_html(full_path: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"/><title>ZEUS-IA</title></head>
<body style="font-family:system-ui,sans-serif;max-width:36rem;margin:2rem auto;padding:1rem;">
<h1>API activa; SPA no encontrado</h1>
<p>No hay <code>index.html</code> en <code>{static_root}</code>. En Railway usa el <strong>Dockerfile de la raíz</strong>
(Root directory del servicio = raíz del repo, no solo <code>backend/</code>).</p>
<p>Ruta: <code>/{full_path}</code></p>
<p><a href="/api/docs">API docs</a> · <a href="/api/v1/health">Health</a> ·
<a href="/clear-pwa-cache.html">Limpiar PWA</a></p>
</body></html>"""


@app.get("/{full_path:path}")
async def serve_frontend(request: Request, full_path: str):
    """SPA fallback; no debe interceptar /static (montaje anterior)."""
    if full_path.startswith("api/"):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": "API endpoint not found",
                "path": f"/{full_path}",
                "message": "The requested API endpoint does not exist. Check /api/docs for available endpoints.",
            },
        )

    static_path = os.path.join(static_root, full_path)
    if os.path.isfile(static_path):
        return FileResponse(static_path)

    index_path = os.path.join(static_root, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)

    accept = (request.headers.get("accept") or "").lower()
    if "text/html" in accept:
        return HTMLResponse(_frontend_missing_html(full_path), status_code=200)
    return JSONResponse(
        status_code=503,
        content={
            "error": "Frontend not built",
            "path": full_path,
            "hint": "Deploy with root Dockerfile; Railway root dir must be repo root, not backend/ only.",
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)