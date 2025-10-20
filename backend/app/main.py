# ========================================
# ZEUS-IA MAIN APPLICATION
# ========================================

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os

# Import your existing app
from app.core.config import settings
from app.api.v1 import api_router

# Create FastAPI app
app = FastAPI(
    title="ZEUS-IA API",
    description="Intelligent Assistant API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api/v1")

# Serve static files (frontend)
if os.path.exists("static"):
    app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve frontend for all non-API routes
@app.get("/{full_path:path}")
async def serve_frontend(request: Request, full_path: str):
    # Don't serve frontend for API routes
    if full_path.startswith("api/"):
        return {"error": "Not found"}
    
    # Serve static files directly
    static_path = f"static/{full_path}"
    if os.path.exists(static_path) and os.path.isfile(static_path):
        return FileResponse(static_path)
    
    # Serve index.html for all other routes (SPA)
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    else:
        return {"error": "Frontend not built", "path": full_path}

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "zeus-ia"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)