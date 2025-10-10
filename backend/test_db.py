import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = str(Path(__file__).resolve().parent)
if project_root not in sys.path:
    sys.path.append(project_root)

# Import settings after path is set
from app.core.config import settings
from app.db.base import Base, engine

def test_db_creation():
    print("=== Iniciando prueba de creación de base de datos ===")
    print(f"Ruta de la base de datos: {settings.DATABASE_URL}")
    
    # Verificar si el directorio existe
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'zeus.db'))
    print(f"Ruta absoluta de la base de datos: {db_path}")
    
    # Intentar crear la base de datos
    try:
        print("\nIntentando crear tablas...")
        Base.metadata.create_all(bind=engine)
        print("¡Tablas creadas exitosamente!")
        
        # Verificar si el archivo se creó
        if os.path.exists('zeus.db'):
            print(f"\n¡Archivo de base de datos creado en: {os.path.abspath('zeus.db')}")
        else:
            print("\nADVERTENCIA: No se pudo encontrar el archivo de la base de datos después de crearlo.")
            
    except Exception as e:
        print(f"\nERROR al crear las tablas: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_db_creation()
