import sys
import os
from pathlib import Path

# Asegurar que el directorio raíz del proyecto esté en el path
project_root = str(Path(__file__).resolve().parent)
if project_root not in sys.path:
    sys.path.append(project_root)

# Configurar logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Importar después de configurar el logging
from sqlalchemy import create_engine, inspect
from app.core.config import settings
from app.db.base import Base, engine
from app.models.user import User, RefreshToken

def test_database_connection():
    """Prueba la conexión a la base de datos."""
    try:
        # Crear una conexión directa a la base de datos
        test_engine = create_engine(settings.DATABASE_URL)
        with test_engine.connect() as conn:
            logger.info("✓ Conexión a la base de datos exitosa")
            return True
    except Exception as e:
        logger.error(f"✗ Error al conectar a la base de datos: {e}")
        return False

def test_create_tables():
    """Prueba la creación de tablas."""
    try:
        # Crear todas las tablas
        logger.info("Creando tablas...")
        Base.metadata.create_all(bind=engine)
        
        # Verificar que las tablas se crearon
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        logger.info(f"Tablas en la base de datos: {tables}")
        
        # Verificar tablas específicas
        required_tables = ["users", "refresh_tokens"]
        missing_tables = [t for t in required_tables if t not in tables]
        
        if missing_tables:
            logger.error(f"✗ Faltan tablas: {missing_tables}")
            return False
        
        logger.info("✓ Todas las tablas se crearon correctamente")
        return True
        
    except Exception as e:
        logger.error(f"✗ Error al crear tablas: {e}", exc_info=True)
        return False

def main():
    logger.info("=== Iniciando prueba de SQLAlchemy y tablas ===")
    
    # Imprimir configuración de la base de datos
    logger.info(f"URL de la base de datos: {settings.DATABASE_URL}")
    
    # Probar conexión
    if not test_database_connection():
        logger.error("No se pudo conectar a la base de datos")
        return
    
    # Probar creación de tablas
    if not test_create_tables():
        logger.error("Error al crear las tablas")
        return
    
    logger.info("=== Prueba completada exitosamente ===")

if __name__ == "__main__":
    main()
