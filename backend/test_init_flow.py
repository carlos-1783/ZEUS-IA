import sys
import os
import logging
from pathlib import Path

# Configurar logging para redirigir a archivo
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('test_init_flow.log', mode='w', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Añadir el directorio raíz al path
project_root = str(Path(__file__).resolve().parent)
if project_root not in sys.path:
    sys.path.append(project_root)

try:
    logger.info("=== INICIO DE PRUEBA DE INICIALIZACIÓN ===")
    
    # Importar configuración y dependencias
    from app.core.config import settings
    from app.db.base import Base, engine, SessionLocal
    from app.models.user import User
    from app.core.security import get_password_hash
    
    logger.info("1. Importaciones exitosas")
    logger.info(f"URL de la base de datos: {settings.DATABASE_URL}")
    
    # Verificar si la base de datos existe
    db_path = Path("zeus.db")
    if db_path.exists():
        logger.info(f"2. Base de datos encontrada en: {db_path.absolute()}")
    else:
        logger.warning("2. No se encontró la base de datos, se creará una nueva")
    
    # Ejecutar la inicialización
    try:
        logger.info("3. Ejecutando inicialización de la base de datos...")
        from app.scripts.init_db import init_db
        init_db()
        logger.info("3. Inicialización completada")
    except Exception as e:
        logger.error(f"Error durante la inicialización: {e}", exc_info=True)
        raise
    
    # Verificar tablas
    try:
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        logger.info(f"4. Tablas en la base de datos: {tables}")
        
        required_tables = ["users", "refresh_tokens"]
        for table in required_tables:
            exists = table in tables
            logger.info(f"   - Tabla {table}: {'EXISTE' if exists else 'NO EXISTE'}")
    except Exception as e:
        logger.error(f"Error al verificar tablas: {e}")
    
    # Verificar superusuario
    try:
        db = SessionLocal()
        user = db.query(User).filter(User.email == settings.FIRST_SUPERUSER_EMAIL).first()
        if user:
            logger.info(f"5. Superusuario verificado: {user.email} (ID: {user.id})")
        else:
            logger.warning("5. No se encontró el superusuario")
        db.close()
    except Exception as e:
        logger.error(f"Error al verificar superusuario: {e}")
    
    logger.info("=== PRUEBA DE INICIALIZACIÓN COMPLETADA ===")
    print("\nPrueba completada. Ver 'test_init_flow.log' para más detalles.")

except Exception as e:
    logger.error("Error en la prueba de inicialización:", exc_info=True)
    print(f"\nError durante la prueba. Ver 'test_init_flow.log' para más detalles.")
