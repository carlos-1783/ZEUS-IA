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

"""
Static site serving strategy:
 - Mount the built frontend at '/'
 - This lets Starlette serve assets with correct MIME types
 - API remains available under '/api/...'
"""
if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="site")

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "zeus-ia"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)