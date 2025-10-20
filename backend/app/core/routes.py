from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os
from app.core.config import settings

class CustomStaticFiles(StaticFiles):
    """Clase personalizada para servir archivos estáticos con configuración adicional."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Asegurar que el directorio de archivos estáticos exista
        os.makedirs(self.directory, exist_ok=True)
        
        # Crear archivos estáticos esenciales si no existen
        self._ensure_essential_files()
    
    def _ensure_essential_files(self):
        """Asegura que los archivos estáticos esenciales existan."""
        # Favicon
        favicon_path = os.path.join(self.directory, 'favicon.ico')
        if not os.path.exists(favicon_path):
            with open(favicon_path, 'wb') as f:
                f.write(b'\x00\x00\x01\x00\x01\x00\x10\x10\x00\x00\x01\x00\x20\x00\x68\x04\x00\x00\x16\x00\x00\x00\x28\x00\x00\x00\x10\x00\x00\x00\x20\x00\x00\x00\x01\x00\x20\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')

def setup_routes(app: FastAPI):
    """Configura todas las rutas de la aplicación."""
    # Importar routers de la API
    from ..api.v1 import api_router
    
    # Incluir el router de la API
    app.include_router(api_router, prefix=settings.API_V1_STR)
    
    # Configurar archivos estáticos
    app.mount(
        settings.STATIC_URL,
        CustomStaticFiles(directory=settings.STATIC_DIR),
        name="static"
    )
    
    # Configurar redirecciones y rutas especiales
    @app.get("/", include_in_schema=False)
    async def root():
        return {"message": "Bienvenido a ZEUS-IA API"}
    
    # Nota: /health está definido en main.py, no duplicar aquí
    
    return app
