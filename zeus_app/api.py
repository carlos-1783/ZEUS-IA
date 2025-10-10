from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from app.config import settings
import os

app = FastAPI(title="ZEUS-IA")

# Configuración CORS - Esencial para desarrollo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ruta al frontend
frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))

# Servir frontend si existe
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
    
    @app.get("/", include_in_schema=False)
    async def serve_frontend():
        return FileResponse(os.path.join(frontend_path, "index.html"))
else:
    @app.get("/")
    async def root():
        return {"message": "Frontend no instalado. Coloca los archivos en /frontend"}

# API Endpoints
@app.get("/api/")
async def health_check():
    return {"status": "active", "service": "ZEUS Backend"}

@app.get("/api/config")
async def show_config():
    return {
        "environment": settings.ENVIRONMENT,
        "domain": settings.DOMAIN
    }
