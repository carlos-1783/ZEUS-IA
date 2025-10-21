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
from app.db.base import create_tables

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

# Crear tablas al iniciar la aplicación
@app.on_event("startup")
async def startup_event():
    print("[STARTUP] Iniciando ZEUS-IA...")
    
    # MOSTRAR DATABASE_URL CONFIGURADA
    import os
    db_url = os.getenv("DATABASE_URL", "NO CONFIGURADA")
    print(f"[STARTUP] 🔍 DATABASE_URL: {db_url[:50]}...")  # Mostrar solo los primeros 50 caracteres
    
    create_tables()
    
    # Crear usuario de prueba si no existe
    from app.db.base import SessionLocal
    from app.models.user import User
    from app.core.security import get_password_hash
    
    db = SessionLocal()
    try:
        print("[STARTUP] 🔍 Verificando usuarios en la base de datos...")
        # Contar usuarios existentes
        user_count = db.query(User).count()
        print(f"[STARTUP] 📊 Usuarios en la base de datos: {user_count}")
        
        # Verificar si ya existe un usuario
        existing_user = db.query(User).filter(User.email == "marketingdigitalper.seo@gmail.com").first()
        if not existing_user:
            print("[STARTUP] 🆕 Creando usuario de prueba...")
            test_user = User(
                email="marketingdigitalper.seo@gmail.com",
                full_name="Usuario de Prueba",
                hashed_password=get_password_hash("Carnay19"),
                is_active=True,
                is_superuser=True
            )
            db.add(test_user)
            db.commit()
            db.refresh(test_user)
            print(f"[STARTUP] ✅ Usuario de prueba creado con ID: {test_user.id}")
            print(f"[STARTUP] 📧 Email: {test_user.email}")
            print(f"[STARTUP] 🔐 Contraseña: Carnay19")
        else:
            print(f"[STARTUP] ✅ Usuario ya existe con ID: {existing_user.id}")
            print("[STARTUP] 🔄 Actualizando contraseña...")
            # Actualizar contraseña para asegurar que sea "Carnay19"
            existing_user.hashed_password = get_password_hash("Carnay19")
            existing_user.is_active = True
            existing_user.is_superuser = True
            db.commit()
            print("[STARTUP] ✅ Contraseña y permisos actualizados")
            print(f"[STARTUP] 📧 Email: {existing_user.email}")
            print(f"[STARTUP] 🔐 Contraseña: Carnay19")
        
        # Verificar el usuario fue creado/actualizado
        final_count = db.query(User).count()
        print(f"[STARTUP] 📊 Usuarios finales en la base de datos: {final_count}")
        
    except Exception as e:
        print(f"[STARTUP] ❌ Error al crear usuario: {e}")
        print(f"[STARTUP] 🔍 Tipo de error: {type(e).__name__}")
        import traceback
        print(f"[STARTUP] 📋 Traceback completo:")
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

    print("[STARTUP] ✅ Aplicación lista")

# Serve static files (frontend) - FIXED
if os.path.exists("static"):
    print(f"[DEBUG] Serving static files from: {os.path.abspath('static')}")
    print(f"[DEBUG] Static files: {os.listdir('static')}")
    
    # Mount assets directory for JS/CSS files
    if os.path.exists("static/assets"):
        app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")
        print(f"[DEBUG] Assets mounted at /assets")
    
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
        "debug": os.getenv("DEBUG", "NOT_SET")
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)