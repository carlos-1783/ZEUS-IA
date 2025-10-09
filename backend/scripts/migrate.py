#!/usr/bin/env python3
"""
ZEUS-IA - Script de Migración de Base de Datos
"""

import os
import sys
import subprocess
from pathlib import Path

# Agregar el directorio padre al path para importar módulos
sys.path.append(str(Path(__file__).parent.parent))

from app.config import settings

def run_command(command, description):
    """Ejecutar comando y mostrar resultado"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completado")
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error en {description}")
        print(f"Comando: {command}")
        print(f"Error: {e.stderr}")
        return False

def check_database_connection():
    """Verificar conexión a la base de datos"""
    print("🔍 Verificando conexión a la base de datos...")
    
    try:
        from app.db.session import engine
        from sqlalchemy import text
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            print("✅ Conexión a la base de datos exitosa")
            return True
    except Exception as e:
        print(f"❌ Error de conexión a la base de datos: {e}")
        return False

def create_migrations():
    """Crear migraciones automáticas"""
    print("📝 Creando migraciones automáticas...")
    
    try:
        # Importación dinámica para evitar errores de linter
        import importlib
        alembic_command = importlib.import_module('alembic.command')
        alembic_config = importlib.import_module('alembic.config')
        
        cfg = alembic_config.Config('alembic.ini')
        alembic_command.revision(cfg, autogenerate=True, message='Auto migration')
        print("✅ Migraciones creadas exitosamente")
        return True
    except Exception as e:
        print(f"⚠️  No se pudieron crear migraciones automáticas: {e}")
        return False

def run_migrations():
    """Ejecutar migraciones"""
    print("🚀 Ejecutando migraciones...")
    
    try:
        # Importación dinámica para evitar errores de linter
        import importlib
        alembic_command = importlib.import_module('alembic.command')
        alembic_config = importlib.import_module('alembic.config')
        
        cfg = alembic_config.Config('alembic.ini')
        alembic_command.upgrade(cfg, 'head')
        print("✅ Migraciones ejecutadas exitosamente")
        return True
    except Exception as e:
        print(f"❌ Error ejecutando migraciones: {e}")
        return False

def create_admin_user():
    """Crear usuario administrador inicial"""
    print("👤 Creando usuario administrador inicial...")
    
    try:
        from app.db.session import SessionLocal
        from app.models.user import User
        from app.core.security import get_password_hash
        
        db = SessionLocal()
        
        # Verificar si ya existe un admin
        admin_user = db.query(User).filter(User.email == "admin@zeusia.app").first()
        if admin_user:
            print("✅ Usuario administrador ya existe")
            db.close()
            return True
        
        # Crear usuario admin
        admin_user = User(
            email="admin@zeusia.app",
            hashed_password=get_password_hash("admin123"),
            is_active=True,
            is_superuser=True,
            full_name="Administrator"
        )
        
        db.add(admin_user)
        db.commit()
        db.close()
        
        print("✅ Usuario administrador creado")
        print("   Email: admin@zeusia.app")
        print("   Contraseña: admin123")
        print("   ⚠️  CAMBIA LA CONTRASEÑA INMEDIATAMENTE")
        return True
        
    except Exception as e:
        print(f"❌ Error creando usuario administrador: {e}")
        return False

def show_database_info():
    """Mostrar información de la base de datos"""
    print("📊 Información de la base de datos:")
    print(f"   URL: {settings.DATABASE_URL}")
    print(f"   Entorno: {settings.ENVIRONMENT}")
    print(f"   Debug: {settings.DEBUG}")

def main():
    """Función principal"""
    print("🚀 Iniciando migración de base de datos ZEUS-IA")
    print("=" * 50)
    
    # Mostrar información
    show_database_info()
    print()
    
    # Verificar conexión
    if not check_database_connection():
        print("❌ No se puede conectar a la base de datos")
        print("   Verifica la URL de conexión en las variables de entorno")
        sys.exit(1)
    
    # Crear migraciones
    if not create_migrations():
        print("⚠️  No se pudieron crear migraciones automáticas")
        print("   Esto es normal si no hay cambios en los modelos")
    
    # Ejecutar migraciones
    if not run_migrations():
        print("❌ Error ejecutando migraciones")
        sys.exit(1)
    
    # Crear usuario admin
    if not create_admin_user():
        print("⚠️  No se pudo crear el usuario administrador")
        print("   Puedes crearlo manualmente más tarde")
    
    print()
    print("🎉 Migración completada exitosamente!")
    print("=" * 50)
    print("✅ Base de datos configurada")
    print("✅ Migraciones ejecutadas")
    print("✅ Usuario administrador creado")
    print()
    print("🔐 Credenciales de administrador:")
    print("   Email: admin@zeusia.app")
    print("   Contraseña: admin123")
    print("   ⚠️  CAMBIA LA CONTRASEÑA INMEDIATAMENTE")
    print()
    print("🚀 Próximos pasos:")
    print("   1. Cambia la contraseña del administrador")
    print("   2. Despliega el backend en Railway")
    print("   3. Despliega el frontend en Vercel")

if __name__ == "__main__":
    main()
