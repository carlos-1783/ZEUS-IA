from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool, QueuePool
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# Configuración del engine con manejo de errores mejorado
if "sqlite" in settings.DATABASE_URL:
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, 
        connect_args={"check_same_thread": False},
        poolclass=NullPool
    )
else:
    # Para PostgreSQL, usar pool con reintentos y timeout
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,  # Verificar conexiones antes de usarlas
        pool_recycle=3600,   # Reciclar conexiones cada hora
        connect_args={
            "connect_timeout": 10,  # Timeout de 10 segundos
            "options": "-c statement_timeout=30000"  # Timeout de 30 segundos por query
        }
    )
    logger.info(f"🔌 Engine PostgreSQL configurado con pool_size=5, max_overflow=10")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def create_tables():
    """Crear todas las tablas en la base de datos"""
    import time
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            print(f"[DATABASE] Intento {attempt + 1}/{max_retries}: Creando tablas...")
            
            # IMPORTANTE: Ejecutar migración ANTES de crear tablas
            # Esto asegura que las columnas existan antes de que SQLAlchemy intente usarlas
            _migrate_user_columns()
            
            # Importar modelos aquí para evitar importación circular
            from app.models.user import User, RefreshToken
            from app.models.customer import Customer
            from app.models.erp import Invoice, Product, Payment, TPVProduct
            from app.models.agent_activity import AgentActivity
            from app.models.document_approval import DocumentApproval
            from app.models.agent_memory import AgentOperationalState, AgentDecisionLog, AgentShortTermBuffer
            
            Base.metadata.create_all(bind=engine)
            print("[DATABASE] [OK] Tablas creadas correctamente")
            
            # Ejecutar migración nuevamente después de crear tablas (por si acaso)
            _migrate_user_columns()
            return  # Éxito, salir de la función
            
        except Exception as e:
            error_msg = str(e)
            is_connection_error = any(keyword in error_msg.lower() for keyword in [
                "conexión", "connection", "timeout", "connection timeout", 
                "connection refused", "connection reset", "operationalerror"
            ])
            
            if is_connection_error and attempt < max_retries - 1:
                print(f"[DATABASE] [ADVERTENCIA] Error de conexión (intento {attempt + 1}/{max_retries}): {error_msg}")
                print(f"[DATABASE] Reintentando en {retry_delay} segundos...")
                logger.warning(f"Error de conexión a BD, reintentando: {error_msg}")
                time.sleep(retry_delay)
                retry_delay *= 2  # Backoff exponencial
                continue
            else:
                print(f"[DATABASE] [ERROR] Error al crear tablas después de {max_retries} intentos: {e}")
                logger.error(f"Error crítico al crear tablas: {e}")
                import traceback
                traceback.print_exc()
                # No lanzar el error, permitir que la aplicación continúe
                print("[DATABASE] [ADVERTENCIA] La aplicación continuará sin base de datos. Algunas funciones pueden no estar disponibles.")
                return


def _migrate_user_columns():
    """Agregar columnas faltantes a la tabla users si no existen (compatible SQLite y PostgreSQL)"""
    from sqlalchemy import inspect, text
    from sqlalchemy.exc import OperationalError, ProgrammingError
    
    try:
        # Verificar si la tabla users existe
        inspector = inspect(engine)
        if "users" not in inspector.get_table_names():
            print("[MIGRATION] Tabla 'users' no existe aún, se creará con el esquema correcto")
            return
        
        # Obtener columnas existentes
        existing_columns = [col["name"] for col in inspector.get_columns("users")]
        print(f"[MIGRATION] Columnas existentes en 'users': {existing_columns}")
        
        # Detectar tipo de base de datos
        is_postgres = "postgresql" in settings.DATABASE_URL.lower() or "postgres" in settings.DATABASE_URL.lower()
        is_sqlite = "sqlite" in settings.DATABASE_URL.lower()
        
        # Columnas a agregar con sus tipos según la base de datos
        columns_to_add = {
            "email_gestor_fiscal": "VARCHAR(255)" if is_postgres else "TEXT",
            "email_asesor_legal": "VARCHAR(255)" if is_postgres else "TEXT",
            "autoriza_envio_documentos_a_asesores": "BOOLEAN" if is_postgres else "BOOLEAN DEFAULT 0",
            "company_name": "VARCHAR(255)" if is_postgres else "TEXT",
            "employees": "INTEGER",
            "plan": "VARCHAR(50)" if is_postgres else "TEXT",
            "tpv_business_profile": "VARCHAR(100)" if is_postgres else "TEXT",
            "tpv_config": "TEXT",  # JSON config
            "control_horario_business_profile": "VARCHAR(100)" if is_postgres else "TEXT",
            "control_horario_config": "TEXT"  # JSON config
        }
        
        added_columns = []
        
        # Ejecutar cada ALTER TABLE en su propia transacción
        for column_name, column_type in columns_to_add.items():
            if column_name not in existing_columns:
                try:
                    with engine.begin() as conn:
                        if is_postgres:
                            # PostgreSQL syntax
                            sql = f'ALTER TABLE users ADD COLUMN "{column_name}" {column_type}'
                            if "BOOLEAN" in column_type:
                                sql += " DEFAULT FALSE"
                            elif column_type == "INTEGER":
                                sql += " DEFAULT 0"
                        else:
                            # SQLite syntax
                            sql = f"ALTER TABLE users ADD COLUMN {column_name} {column_type}"
                        
                        conn.execute(text(sql))
                        added_columns.append(column_name)
                        print(f"[MIGRATION] [OK] Columna '{column_name}' agregada")
                except (OperationalError, ProgrammingError) as e:
                    # Si la columna ya existe o hay otro error, continuar
                    error_msg = str(e)
                    if "already exists" in error_msg.lower() or "duplicate column" in error_msg.lower() or "already exists" in error_msg:
                        print(f"[MIGRATION] [INFO] Columna '{column_name}' ya existe")
                    else:
                        print(f"[MIGRATION] [WARN] Error agregando columna '{column_name}': {e}")
            else:
                print(f"[MIGRATION] [INFO] Columna '{column_name}' ya existe")
        
        if added_columns:
            print(f"[MIGRATION] [OK] Migracion completada. Columnas agregadas: {', '.join(added_columns)}")
        else:
            print("[MIGRATION] [OK] Todas las columnas ya existen.")
                
    except Exception as e:
        print(f"[MIGRATION] [WARN] No se pudo ejecutar migracion: {e}")
        import traceback
        traceback.print_exc()


def _migrate_firewall_columns_legacy():
    """DEPRECATED: Usar _migrate_user_columns() en su lugar"""
    import sqlite3
    import os
    
    try:
        db_path = settings.DATABASE_URL.replace("sqlite:///", "")
        
        # Si es una ruta absoluta, usarla directamente
        if not os.path.isabs(db_path):
            # Si es relativa, buscar en el directorio backend
            backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            db_path = os.path.join(backend_dir, db_path)
        
        # Si la base de datos no existe, SQLAlchemy la creará con el esquema correcto
        # No necesitamos hacer nada aquí
        if not os.path.exists(db_path):
            print("[MIGRATION] Base de datos no existe aún, se creará con el esquema correcto")
            return
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            # Verificar si la tabla users existe
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if not cursor.fetchone():
                print("[MIGRATION] Tabla 'users' no existe aún, se creará con el esquema correcto")
                conn.close()
                return
            
            # Verificar qué columnas existen
            cursor.execute("PRAGMA table_info(users)")
            existing_columns = [row[1] for row in cursor.fetchall()]
            
            # Columnas a agregar (incluyendo company_name y employees que también pueden faltar)
            columns_to_add = [
                ("email_gestor_fiscal", "TEXT"),
                ("email_asesor_legal", "TEXT"),
                ("autoriza_envio_documentos_a_asesores", "BOOLEAN DEFAULT 0"),
                ("company_name", "TEXT"),
                ("employees", "INTEGER")
            ]
            
            added_columns = []
            for column_name, column_type in columns_to_add:
                if column_name not in existing_columns:
                    try:
                        cursor.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}")
                        
                        # Si es BOOLEAN, establecer el valor por defecto para filas existentes
                        if "BOOLEAN" in column_type:
                            cursor.execute(f"UPDATE users SET {column_name} = 0 WHERE {column_name} IS NULL")
                        elif column_type == "INTEGER":
                            cursor.execute(f"UPDATE users SET {column_name} = 0 WHERE {column_name} IS NULL")
                        
                        added_columns.append(column_name)
                        print(f"[MIGRATION] [OK] Columna '{column_name}' agregada")
                    except sqlite3.OperationalError as e:
                        print(f"[MIGRATION] [WARN] Error agregando columna '{column_name}': {e}")
                else:
                    print(f"[MIGRATION] [INFO] Columna '{column_name}' ya existe")
            
            # Crear tabla document_approvals si no existe
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='document_approvals'")
            if not cursor.fetchone():
                print("[MIGRATION] Creando tabla 'document_approvals'...")
                cursor.execute("""
                    CREATE TABLE document_approvals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        agent_name VARCHAR(50) NOT NULL,
                        document_type VARCHAR(100) NOT NULL,
                        document_payload_json TEXT NOT NULL,
                        status VARCHAR(50) NOT NULL DEFAULT 'draft',
                        advisor_email VARCHAR(255),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        approved_at TIMESTAMP,
                        sent_at TIMESTAMP,
                        audit_log_json TEXT,
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    )
                """)
                cursor.execute("CREATE INDEX idx_document_approvals_user_id ON document_approvals(user_id)")
                cursor.execute("CREATE INDEX idx_document_approvals_agent_name ON document_approvals(agent_name)")
                cursor.execute("CREATE INDEX idx_document_approvals_status ON document_approvals(status)")
                print("[MIGRATION] [OK] Tabla 'document_approvals' creada")
            else:
                print("[MIGRATION] [INFO] Tabla 'document_approvals' ya existe")
            
            conn.commit()
            
            if added_columns:
                print(f"[MIGRATION] [OK] Migracion completada. Columnas agregadas: {', '.join(added_columns)}")
            else:
                print("[MIGRATION] [OK] Todas las columnas ya existen.")
                
        except Exception as e:
            conn.rollback()
            print(f"[MIGRATION] [WARN] Error durante la migracion: {e}")
            import traceback
            traceback.print_exc()
        finally:
            conn.close()
    except Exception as e:
        print(f"[MIGRATION] [WARN] No se pudo ejecutar migracion: {e}")
        import traceback
        traceback.print_exc()

# get_db está ahora en session.py con manejo de errores mejorado
# Mantener esta función por compatibilidad, pero usar session.py
def get_db():
    """Función de compatibilidad - usar session.get_db() en su lugar"""
    from app.db.session import get_db as get_db_with_retry
    yield from get_db_with_retry()
