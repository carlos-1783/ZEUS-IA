"""
ZEUS-IA - Database Initialization
Script para inicializar la base de datos
"""

import sys
from pathlib import Path

# Agregar directorio raíz al path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from backend.models.database import init_db, engine
from backend.models import User, Decision, AuditLog, Metric, HITLQueue
from sqlalchemy import inspect


def check_tables():
    """Verifica qué tablas existen"""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    return tables


def main():
    print("🏛️ ZEUS-IA - Inicializando Base de Datos")
    print("=" * 60)
    
    # Verificar tablas existentes
    print("\n📊 Verificando tablas existentes...")
    existing_tables = check_tables()
    if existing_tables:
        print(f"✅ Tablas existentes: {', '.join(existing_tables)}")
    else:
        print("⚠️  No hay tablas creadas")
    
    # Crear tablas
    print("\n🔨 Creando tablas...")
    try:
        init_db()
        print("✅ Base de datos inicializada correctamente")
    except Exception as e:
        print(f"❌ Error al inicializar base de datos: {e}")
        return False
    
    # Verificar tablas creadas
    print("\n📊 Verificando tablas creadas...")
    new_tables = check_tables()
    print(f"✅ Tablas creadas: {', '.join(new_tables)}")
    
    # Mostrar esquema
    print("\n📋 Esquema de tablas:")
    print("=" * 60)
    
    tables_info = {
        "users": "Usuarios del sistema",
        "decisions": "Decisiones de agentes IA",
        "audit_logs": "Logs inmutables de auditoría",
        "metrics": "Métricas de rendimiento y costos",
        "hitl_queue": "Cola de aprobaciones humanas (HITL)"
    }
    
    inspector = inspect(engine)
    for table_name in new_tables:
        columns = inspector.get_columns(table_name)
        description = tables_info.get(table_name, "")
        print(f"\n📁 {table_name.upper()}: {description}")
        print(f"   Columnas: {len(columns)}")
        print(f"   Principales: {', '.join([c['name'] for c in columns[:5]])}")
    
    print("\n" + "=" * 60)
    print("✅ Base de datos lista para ZEUS-IA")
    print("🏛️ El Olimpo tiene su fundación")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

