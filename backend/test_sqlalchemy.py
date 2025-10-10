import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = str(Path(__file__).resolve().parent)
if project_root not in sys.path:
    sys.path.append(project_root)

# Configuración básica de logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def test_sqlalchemy():
    print("=== Iniciando prueba de SQLAlchemy ===")
    
    try:
        # Importar configuración de SQLAlchemy
        from app.db.base import Base, engine
        from app.models.user import User
        
        print("\n1. Configuración de SQLAlchemy cargada correctamente")
        print(f"   - URL de la base de datos: {engine.url}")
        
        # Verificar si el motor está conectado
        with engine.connect() as conn:
            print("\n2. Conexión a la base de datos exitosa")
            
            # Verificar si la tabla de usuarios existe
            inspector = engine.dialect.inspector(engine)
            tables = inspector.get_table_names()
            print("\n3. Tablas en la base de datos:")
            for table in tables:
                print(f"   - {table}")
            
            # Si no hay tablas, intentar crearlas
            if not tables:
                print("\n4. No se encontraron tablas. Intentando crearlas...")
                try:
                    Base.metadata.create_all(bind=engine)
                    print("   ✓ Tablas creadas exitosamente")
                    
                    # Verificar nuevamente las tablas
                    tables_after = inspector.get_table_names()
                    print("\n5. Tablas después de crearlas:")
                    for table in tables_after:
                        print(f"   - {table}")
                except Exception as e:
                    print(f"   ✗ Error al crear las tablas: {str(e)}")
            
    except Exception as e:
        print(f"\n✗ Error durante la prueba: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n=== Prueba de SQLAlchemy completada ===")

if __name__ == "__main__":
    test_sqlalchemy()
