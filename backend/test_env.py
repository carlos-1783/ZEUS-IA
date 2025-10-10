import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = str(Path(__file__).resolve().parent)
if project_root not in sys.path:
    sys.path.append(project_root)

# Import settings after path is set
from app.core.config import settings

def test_environment():
    print("=== Verificando entorno de ejecución ===")
    print(f"Directorio de trabajo actual: {os.getcwd()}")
    print(f"Ruta del proyecto: {project_root}")
    print("\n=== Variables de entorno ===")
    print(f"DATABASE_URL: {os.getenv('DATABASE_URL')}")
    print(f"PYTHONPATH: {os.getenv('PYTHONPATH')}")
    
    print("\n=== Configuración de la aplicación ===")
    print(f"Configuración DATABASE_URL: {settings.DATABASE_URL}")
    print(f"Configuración DEBUG: {settings.DEBUG}")
    
    # Verificar si podemos escribir en el directorio actual
    test_file = 'test_write.txt'
    try:
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        print("\n✓ Permisos de escritura en el directorio actual: OK")
    except Exception as e:
        print(f"\n✗ Error al escribir en el directorio actual: {str(e)}")

if __name__ == "__main__":
    test_environment()
