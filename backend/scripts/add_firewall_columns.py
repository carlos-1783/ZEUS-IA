"""
Script para agregar columnas del Legal-Fiscal Firewall a la tabla users
"""
import sqlite3
import os
from pathlib import Path
from app.core.config import settings

def migrate_database():
    """Agregar columnas faltantes a la tabla users"""
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    
    # Si es una ruta absoluta, usarla directamente
    if not os.path.isabs(db_path):
        # Si es relativa, buscar en el directorio backend
        backend_dir = Path(__file__).parent.parent
        db_path = backend_dir / db_path
    
    print(f"[MIGRATION] Conectando a: {db_path}")
    
    if not os.path.exists(db_path):
        print(f"[MIGRATION] ❌ Base de datos no encontrada: {db_path}")
        print("[MIGRATION] La base de datos se creará automáticamente al iniciar el servidor")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Verificar qué columnas existen
        cursor.execute("PRAGMA table_info(users)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        print(f"[MIGRATION] Columnas existentes: {existing_columns}")
        
        # Columnas a agregar
        columns_to_add = [
            ("email_gestor_fiscal", "TEXT"),
            ("email_asesor_legal", "TEXT"),
            ("autoriza_envio_documentos_a_asesores", "BOOLEAN DEFAULT 0")
        ]
        
        added_columns = []
        for column_name, column_type in columns_to_add:
            if column_name not in existing_columns:
                try:
                    # SQLite no soporta ALTER TABLE ADD COLUMN con DEFAULT directamente
                    # Necesitamos agregar la columna y luego actualizar los valores
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}")
                    
                    # Si es BOOLEAN, establecer el valor por defecto para filas existentes
                    if "BOOLEAN" in column_type:
                        cursor.execute(f"UPDATE users SET {column_name} = 0 WHERE {column_name} IS NULL")
                    
                    added_columns.append(column_name)
                    print(f"[MIGRATION] ✅ Columna '{column_name}' agregada")
                except sqlite3.OperationalError as e:
                    print(f"[MIGRATION] ⚠️ Error agregando columna '{column_name}': {e}")
            else:
                print(f"[MIGRATION] ℹ️ Columna '{column_name}' ya existe")
        
        conn.commit()
        
        if added_columns:
            print(f"[MIGRATION] ✅ Migración completada. Columnas agregadas: {', '.join(added_columns)}")
        else:
            print("[MIGRATION] ✅ Todas las columnas ya existen. No se requiere migración.")
            
    except Exception as e:
        conn.rollback()
        print(f"[MIGRATION] ❌ Error durante la migración: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()

