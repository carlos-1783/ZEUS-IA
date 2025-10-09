from fastapi import APIRouter, HTTPException
from typing import Dict, Any

router = APIRouter(tags=["General"])

@router.get("/", summary="API Root")
async def read_root():
    return {"message": "¡Bienvenido a la API de ZEUS-IA!"}

@router.get("/health", summary="Health Check")
async def health_check():
    return {
        "status": "ok",
        "version": "1.0.0",
        "database_status": {
            "status": "online",
            "type": "sqlite"
        }
    }
