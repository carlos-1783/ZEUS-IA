import sys
import os
import logging
from pathlib import Path

# Configurar logging para redirigir a archivo
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('debug_sqlalchemy.log', mode='w', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Añadir el directorio raíz al path
project_root = str(Path(__file__).resolve().parent)
if project_root not in sys.path:
    sys.path.append(project_root)

try:
    logger.info("=== INICIO DE DEPURACIÓN SQLALCHEMY ===")
    logger.info(f"Directorio de trabajo: {os.getcwd()}")
    logger.info(f"Python path: {sys.path}")
    
    # Importar configuración y modelos
    from app.core.config import settings
    from app.db.base import Base, engine
    from app.models.user import User, RefreshToken
    
    logger.info("Importaciones exitosas")
    logger.info(f"URL de la base de datos: {settings.DATABASE_URL}")
    
    # Verificar si el motor está configurado correctamente
    logger.info(f"Configuración del motor: {engine}")
    
    # Listar tablas antes de crear
    inspector = type('', (), {'get_table_names': lambda: []})()
    try:
        from sqlalchemy import inspect
        inspector = inspect(engine)
        logger.info(f"Tablas existentes: {inspector.get_table_names()}")
    except Exception as e:
        logger.error(f"Error al listar tablas: {e}")
    
    # Crear tablas
    try:
        logger.info("Creando tablas...")
        Base.metadata.create_all(bind=engine)
        logger.info("Tablas creadas (si no existían)")
    except Exception as e:
        logger.error(f"Error al crear tablas: {e}", exc_info=True)
    
    # Listar tablas después de crear
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        logger.info(f"Tablas después de la creación: {tables}")
        
        # Verificar tablas específicas
        required_tables = ["users", "refresh_tokens"]
        for table in required_tables:
            exists = table in tables
            logger.info(f"Tabla {table}: {'EXISTE' if exists else 'NO EXISTE'}")
    except Exception as e:
        logger.error(f"Error al listar tablas después de creación: {e}")
    
    logger.info("=== FIN DE DEPURACIÓN ===")
    
except Exception as e:
    logger.error("Error en la depuración:", exc_info=True)

# Mensaje final para el usuario
print("Depuración completada. Ver el archivo 'debug_sqlalchemy.log' para los resultados.")
