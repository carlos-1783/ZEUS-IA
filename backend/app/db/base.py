import logging
import os

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool, QueuePool
from app.core.config import settings

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
            "connect_timeout": int(os.getenv("ZEUS_DB_CONNECT_TIMEOUT", "30")),
            "options": "-c statement_timeout=30000"  # Timeout de 30 segundos por query
        }
    )
    logger.info(f"🔌 Engine PostgreSQL configurado con pool_size=5, max_overflow=10")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def create_tables():
    """Crear todas las tablas en la base de datos"""
    import time
    # Postgres "sleeping" / cold start en Railway: más intentos y backoff.
    max_retries = int(os.getenv("ZEUS_DB_CREATE_TABLES_RETRIES", "8"))
    retry_delay = int(os.getenv("ZEUS_DB_CREATE_TABLES_RETRY_DELAY", "3"))
    
    for attempt in range(max_retries):
        try:
            print(f"[DATABASE] Intento {attempt + 1}/{max_retries}: Creando tablas...")
            
            # IMPORTANTE: Ejecutar migración ANTES de crear tablas
            # Esto asegura que las columnas existan antes de que SQLAlchemy intente usarlas
            _migrate_user_columns()
            _migrate_document_approvals_columns()
            _migrate_tpv_company_columns()
            
            # Importar modelos aquí para evitar importación circular
            from app.models.user import User, RefreshToken, PasswordResetToken
            from app.models.company import Company, UserCompany
            from app.models.customer import Customer
            from app.models.erp import Invoice, Product, Payment, TPVProduct, TaxRate, FiscalProfile, TPVSale, TPVSaleItem
            from app.models.agent_activity import AgentActivity
            from app.models.document_approval import DocumentApproval
            from app.models.agent_memory import AgentOperationalState, AgentDecisionLog, AgentShortTermBuffer
            from app.models.automation_readiness import AutomationReadiness
            from app.models.payroll_draft import PayrollDraft
            from app.models.reservation import Reservation
            from app.models.tpv_comanda_share import TPVComandaShare
            from app.models.tpv_table import TPVTable
            from app.models.company_employee import CompanyEmployee

            Base.metadata.create_all(bind=engine)
            print("[DATABASE] [OK] Tablas creadas correctamente")
            
            # Ejecutar migración nuevamente después de crear tablas (por si acaso)
            _migrate_user_columns()
            _migrate_document_approvals_columns()
            _migrate_tpv_company_columns()
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
        # IMPORTANTE: para PostgreSQL no incluir DEFAULT en column_type aquí.
        # Si lo incluimos y además lo añadimos luego, acabamos generando SQL inválido
        # (p. ej. "BOOLEAN DEFAULT FALSE DEFAULT FALSE"), lo que deja la BD sin migrar.
        columns_to_add = {
            "email_gestor_fiscal": "VARCHAR(255)" if is_postgres else "TEXT",
            "email_gestor_laboral": "VARCHAR(255)" if is_postgres else "TEXT",
            "email_asesor_legal": "VARCHAR(255)" if is_postgres else "TEXT",
            "autoriza_envio_documentos_a_asesores": "BOOLEAN" if is_postgres else "BOOLEAN",
            "company_name": "VARCHAR(255)" if is_postgres else "TEXT",
            "employees": "INTEGER",
            "plan": "VARCHAR(50)" if is_postgres else "TEXT",
            "tpv_business_profile": "VARCHAR(100)" if is_postgres else "TEXT",
            "tpv_config": "TEXT",  # JSON config
            "control_horario_business_profile": "VARCHAR(100)" if is_postgres else "TEXT",
            "control_horario_config": "TEXT",  # JSON config
            "stripe_customer_id": "VARCHAR(255)" if is_postgres else "TEXT",
            "stripe_subscription_id": "VARCHAR(255)" if is_postgres else "TEXT",
            "role": "VARCHAR(20)" if is_postgres else "TEXT",
            "public_site_enabled": "BOOLEAN" if is_postgres else "BOOLEAN",
            "public_site_slug": "VARCHAR(100)" if is_postgres else "TEXT",
            "phone": "VARCHAR(32)" if is_postgres else "TEXT",
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
                            # Defaults (solo cuando procede)
                            if column_name in ("autoriza_envio_documentos_a_asesores", "public_site_enabled"):
                                sql += " DEFAULT FALSE"
                            elif column_name == "employees":
                                sql += " DEFAULT 0"
                            elif column_name == "role":
                                sql += " DEFAULT 'owner'"
                        else:
                            # SQLite syntax
                            sql = f"ALTER TABLE users ADD COLUMN {column_name} {column_type}"
                            if column_name in ("autoriza_envio_documentos_a_asesores", "public_site_enabled"):
                                sql += " DEFAULT 0"
                            elif column_name == "employees":
                                sql += " DEFAULT 0"
                            elif column_name == "role":
                                sql += " DEFAULT 'owner'"
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


def _migrate_document_approvals_columns():
    """Alinea document_approvals con el modelo (SQLite/PostgreSQL) de forma idempotente."""
    from sqlalchemy import inspect, text
    from sqlalchemy.exc import OperationalError, ProgrammingError

    try:
        inspector = inspect(engine)
        if "document_approvals" not in inspector.get_table_names():
            print("[MIGRATION] Tabla 'document_approvals' no existe aún; se creará con create_all")
            return

        existing_columns = {col["name"] for col in inspector.get_columns("document_approvals")}
        is_postgres = "postgresql" in settings.DATABASE_URL.lower() or "postgres" in settings.DATABASE_URL.lower()

        vis_sql = (
            "BOOLEAN NOT NULL DEFAULT true"
            if is_postgres
            else "INTEGER NOT NULL DEFAULT 1"
        )
        columns_to_add = {
            "ticket_id": "VARCHAR(100)" if is_postgres else "TEXT",
            "fiscal_document_type": "VARCHAR(50)" if is_postgres else "TEXT",
            "export_format": "VARCHAR(20)" if is_postgres else "TEXT",
            "exported_at": "TIMESTAMP WITH TIME ZONE" if is_postgres else "TIMESTAMP",
            "filed_external_at": "TIMESTAMP WITH TIME ZONE" if is_postgres else "TIMESTAMP",
            "approved_at": "TIMESTAMP WITH TIME ZONE" if is_postgres else "TIMESTAMP",
            "sent_at": "TIMESTAMP WITH TIME ZONE" if is_postgres else "TIMESTAMP",
            "audit_log_json": "TEXT",
            "company_id": "INTEGER",
            "visible_in_workspace": vis_sql,
        }

        added = []
        for column_name, column_type in columns_to_add.items():
            if column_name in existing_columns:
                continue
            try:
                with engine.begin() as conn:
                    if is_postgres:
                        sql = (
                            f'ALTER TABLE document_approvals '
                            f'ADD COLUMN IF NOT EXISTS "{column_name}" {column_type}'
                        )
                    else:
                        sql = f"ALTER TABLE document_approvals ADD COLUMN {column_name} {column_type}"
                    conn.execute(text(sql))
                added.append(column_name)
                existing_columns.add(column_name)
                print(f"[MIGRATION] [OK] document_approvals.{column_name} agregada")
            except (OperationalError, ProgrammingError) as e:
                em = str(e).lower()
                if "duplicate column" in em or "already exists" in em:
                    print(f"[MIGRATION] [INFO] document_approvals.{column_name} ya existe")
                else:
                    print(f"[MIGRATION] [WARN] No se pudo agregar document_approvals.{column_name}: {e}")

        # Índice útil para trazabilidad de tickets
        try:
            indexes = {ix["name"] for ix in inspector.get_indexes("document_approvals")}
            if "ix_document_approvals_ticket_id" not in indexes and "ticket_id" in existing_columns:
                with engine.begin() as conn:
                    if is_postgres:
                        conn.execute(
                            text(
                                "CREATE INDEX IF NOT EXISTS ix_document_approvals_ticket_id "
                                "ON document_approvals (ticket_id)"
                            )
                        )
                    else:
                        conn.execute(
                            text(
                                "CREATE INDEX IF NOT EXISTS ix_document_approvals_ticket_id "
                                "ON document_approvals(ticket_id)"
                            )
                        )
                print("[MIGRATION] [OK] Índice ix_document_approvals_ticket_id creado")
        except Exception as e:
            print(f"[MIGRATION] [WARN] No se pudo crear índice ticket_id en document_approvals: {e}")

        try:
            indexes = {ix["name"] for ix in inspector.get_indexes("document_approvals")}
            if "ix_document_approvals_company_id" not in indexes and "company_id" in existing_columns:
                with engine.begin() as conn:
                    if is_postgres:
                        conn.execute(
                            text(
                                "CREATE INDEX IF NOT EXISTS ix_document_approvals_company_id "
                                "ON document_approvals (company_id)"
                            )
                        )
                    else:
                        conn.execute(
                            text(
                                "CREATE INDEX IF NOT EXISTS ix_document_approvals_company_id "
                                "ON document_approvals(company_id)"
                            )
                        )
                print("[MIGRATION] [OK] Índice ix_document_approvals_company_id creado")
        except Exception as e:
            print(f"[MIGRATION] [WARN] No se pudo crear índice company_id en document_approvals: {e}")

        if added:
            print(f"[MIGRATION] [OK] document_approvals alineada. Nuevas columnas: {', '.join(added)}")
        else:
            print("[MIGRATION] [OK] document_approvals ya estaba alineada")
    except Exception as e:
        print(f"[MIGRATION] [WARN] No se pudo verificar document_approvals: {e}")
        import traceback
        traceback.print_exc()


def _migrate_tpv_company_columns():
    """Alinea tpv_products/tpv_sales con columnas company_id esperadas por el ORM."""
    from sqlalchemy import inspect, text
    from sqlalchemy.exc import OperationalError, ProgrammingError

    try:
        inspector = inspect(engine)
        is_postgres = "postgresql" in settings.DATABASE_URL.lower() or "postgres" in settings.DATABASE_URL.lower()
        tables = ("tpv_products", "tpv_sales")
        for table_name in tables:
            if table_name not in inspector.get_table_names():
                continue
            cols = {c["name"] for c in inspector.get_columns(table_name)}
            if "company_id" in cols:
                continue
            try:
                with engine.begin() as conn:
                    if is_postgres:
                        conn.execute(
                            text(f'ALTER TABLE "{table_name}" ADD COLUMN IF NOT EXISTS "company_id" INTEGER')
                        )
                    else:
                        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN company_id INTEGER"))
                print(f"[MIGRATION] [OK] {table_name}.company_id agregada")
            except (OperationalError, ProgrammingError) as e:
                em = str(e).lower()
                if "duplicate column" in em or "already exists" in em:
                    print(f"[MIGRATION] [INFO] {table_name}.company_id ya existe")
                else:
                    print(f"[MIGRATION] [WARN] No se pudo agregar {table_name}.company_id: {e}")

            # índice útil para consultas por empresa en TPV
            try:
                indexes = {ix["name"] for ix in inspector.get_indexes(table_name)}
                idx_name = f"ix_{table_name}_company_id"
                if idx_name not in indexes:
                    with engine.begin() as conn:
                        if is_postgres:
                            conn.execute(
                                text(f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "{table_name}" (company_id)')
                            )
                        else:
                            conn.execute(
                                text(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table_name}(company_id)")
                            )
                    print(f"[MIGRATION] [OK] Índice {idx_name} creado")
            except Exception as e:
                print(f"[MIGRATION] [WARN] No se pudo crear índice company_id en {table_name}: {e}")
    except Exception as e:
        print(f"[MIGRATION] [WARN] No se pudo verificar tpv company_id: {e}")
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
