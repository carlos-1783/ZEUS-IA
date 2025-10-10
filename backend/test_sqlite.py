import sqlite3
import os
import sys
from pathlib import Path

print("=== Iniciando prueba de SQLite directa ===")

try:
    # Ruta a la base de datos
    db_path = Path("test_sqlite.db")
    print(f"Ruta de la base de datos: {db_path.absolute()}")
    
    # Eliminar la base de datos si ya existe
    if db_path.exists():
        db_path.unlink()
    
    # Conectar a la base de datos (se crea si no existe)
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    print("1. Conexión a SQLite establecida correctamente")
    
    # Crear una tabla
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS test (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    print("2. Tabla 'test' creada correctamente")
    
    # Insertar datos
    cursor.execute("INSERT INTO test (name) VALUES (?)", ("Prueba 1",))
    conn.commit()
    
    print("3. Datos insertados correctamente")
    
    # Consultar datos
    cursor.execute("SELECT * FROM test")
    rows = cursor.fetchall()
    
    print("4. Datos en la tabla 'test':")
    for row in rows:
        print(f"   - {row}")
    
    # Cerrar la conexión
    conn.close()
    
    # Verificar que el archivo se creó
    if db_path.exists():
        print(f"\n✓ Archivo de base de datos creado en: {db_path.absolute()}")
        print(f"   Tamaño: {db_path.stat().st_size} bytes")
    else:
        print("\n✗ No se pudo crear el archivo de base de datos")
    
except Exception as e:
    print(f"\n✗ Error durante la prueba: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n=== Prueba de SQLite completada ===")
