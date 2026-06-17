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
    # Pool por proceso: con Gunicorn (N workers) limitar para no agotar conexiones Postgres en Railway.
    _pool = int(os.getenv("ZEUS_DB_POOL_SIZE", "3"))
    _overflow = int(os.getenv("ZEUS_DB_MAX_OVERFLOW", "5"))
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        poolclass=QueuePool,
        pool_size=_pool,
        max_overflow=_overflow,
        pool_pre_ping=True,  # Verificar conexiones antes de usarlas
        pool_recycle=3600,   # Reciclar conexiones cada hora
        connect_args={
            "connect_timeout": int(os.getenv("ZEUS_DB_CONNECT_TIMEOUT", "30")),
            "options": "-c statement_timeout=30000"  # Timeout de 30 segundos por query
        }
    )
    logger.info("🔌 Engine PostgreSQL pool_size=%s max_overflow=%s", _pool, _overflow)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def ensure_schema_patches():
    """Migraciones idempotentes (legacy sin Alembic real). Seguro llamar en cada arranque."""
    try:
        print("[SCHEMA] Aplicando parches de esquema...")
        _migrate_user_columns()
        _migrate_document_approvals_columns()
        _migrate_rafael_fiscal_tables()
        _migrate_tpv_company_columns()
        _migrate_smart_time_control_tables()
        _migrate_time_cost_engine_v1()
        _migrate_cashflow_ledger()
        print("[SCHEMA] Parches de esquema completados")
    except Exception as e:
        logger.warning("ensure_schema_patches: %s", e)
        import traceback
        traceback.print_exc()


def create_tables():
    """Crear todas las tablas en la base de datos"""
    import time
    # Postgres "sleeping" / cold start en Railway: más intentos y backoff.
    max_retries = int(os.getenv("ZEUS_DB_CREATE_TABLES_RETRIES", "8"))
    retry_delay = int(os.getenv("ZEUS_DB_CREATE_TABLES_RETRY_DELAY", "3"))
    
    for attempt in range(max_retries):
        try:
            print(f"[DATABASE] Intento {attempt + 1}/{max_retries}: Creando tablas...")
            
            ensure_schema_patches()

            # Importar modelos aquí para evitar importación circular
            from app.models.user import User, RefreshToken, PasswordResetToken
            from app.models.user_settings import UserSettings
            from app.models.company import Company, UserCompany
            from app.models.customer import Customer
            from app.models.erp import Invoice, Product, Payment, TPVProduct
            from app.models.fiscal import TaxRate, FiscalProfile, TPVSale, TPVSaleItem
            from app.models.expense import Expense
            from app.models.agent_activity import AgentActivity
            from app.models.document_approval import DocumentApproval
            from app.models.agent_memory import AgentOperationalState, AgentDecisionLog, AgentShortTermBuffer
            from app.models.automation_readiness import AutomationReadiness
            from app.models.payroll_draft import PayrollDraft
            from app.models.reservation import Reservation
            from app.models.tpv_comanda_share import TPVComandaShare
            from app.models.tpv_table import TPVTable
            from app.models.crm_office import CrmActivityLog, CrmSaleLink, CustomerRecord
            from app.models.chat_message import ChatMessage
            from app.models.employee_work_session import EmployeeWorkSession
            from app.models.time_cost_checkin import TimeCostCheckin
            from app.models.cashflow_ledger import CashflowLedgerEntry
            from app.models.crm_lead import CrmLead
            from app.models.zeus_pending_approval import ZeusPendingApproval
            from app.models.scan_event import ScanEvent
            from app.models.thalos_security_event import ThalosSecurityEvent, ThalosLoginAttempt
            from app.models.zeus_closure_audit import ZeusClosureAudit
            from app.models.thalos_workspace_item import ThalosWorkspaceItem
            from app.models.tpv_operator_session import TPVOperatorSession
            from app.models.time_tracking import (
                TimeTrackingRecord,
                EmployeeSchedule,
                AttendanceReport,
                TimeControlEvent,
                TimeControlAlert,
            )

            Base.metadata.create_all(bind=engine)
            print("[DATABASE] [OK] Tablas creadas correctamente")
            
            ensure_schema_patches()
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
            "file_path": "VARCHAR(500)" if is_postgres else "TEXT",
            "file_size_bytes": "INTEGER",
            "mime_type": "VARCHAR(100)" if is_postgres else "TEXT",
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


def _migrate_rafael_fiscal_tables():
    """Tabla expenses y metadatos de archivo fiscal (RAFAEL v2) si Alembic no corrió."""
    from sqlalchemy import inspect, text
    from sqlalchemy.exc import OperationalError, ProgrammingError

    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        is_postgres = "postgresql" in settings.DATABASE_URL.lower() or "postgres" in settings.DATABASE_URL.lower()

        if "expenses" not in tables:
            try:
                from app.models.expense import Expense

                Expense.__table__.create(bind=engine, checkfirst=True)
                print("[MIGRATION] [OK] Tabla expenses creada")
            except Exception as e:
                print(f"[MIGRATION] [WARN] No se pudo crear expenses con ORM: {e}")
                try:
                    with engine.begin() as conn:
                        if is_postgres:
                            conn.execute(
                                text(
                                    """
                                    CREATE TABLE IF NOT EXISTS expenses (
                                        id SERIAL PRIMARY KEY,
                                        company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                                        supplier_name VARCHAR(200) NOT NULL,
                                        description TEXT,
                                        issue_date TIMESTAMP NOT NULL,
                                        base_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
                                        tax_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
                                        tax_rate DOUBLE PRECISION NOT NULL DEFAULT 21,
                                        category VARCHAR(100),
                                        invoice_ref VARCHAR(100),
                                        created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                                        created_at TIMESTAMP NOT NULL DEFAULT NOW()
                                    )
                                    """
                                )
                            )
                            conn.execute(
                                text(
                                    "CREATE INDEX IF NOT EXISTS ix_expenses_company_id ON expenses (company_id)"
                                )
                            )
                        else:
                            conn.execute(
                                text(
                                    """
                                    CREATE TABLE IF NOT EXISTS expenses (
                                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                                        company_id INTEGER NOT NULL,
                                        supplier_name TEXT NOT NULL,
                                        description TEXT,
                                        issue_date TIMESTAMP NOT NULL,
                                        base_amount REAL NOT NULL DEFAULT 0,
                                        tax_amount REAL NOT NULL DEFAULT 0,
                                        tax_rate REAL NOT NULL DEFAULT 21,
                                        category TEXT,
                                        invoice_ref TEXT,
                                        created_by INTEGER,
                                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                                        FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE,
                                        FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE SET NULL
                                    )
                                    """
                                )
                            )
                            conn.execute(
                                text(
                                    "CREATE INDEX IF NOT EXISTS ix_expenses_company_id ON expenses(company_id)"
                                )
                            )
                    print("[MIGRATION] [OK] Tabla expenses creada (SQL)")
                except (OperationalError, ProgrammingError) as sql_err:
                    print(f"[MIGRATION] [WARN] No se pudo crear expenses: {sql_err}")
        else:
            print("[MIGRATION] [OK] Tabla expenses ya existe")
    except Exception as e:
        print(f"[MIGRATION] [WARN] No se pudo verificar tablas fiscales RAFAEL: {e}")


def _migrate_tpv_company_columns():
    """Alinea tablas multi-tenant con company_id (TPV + facturas)."""
    from sqlalchemy import inspect, text
    from sqlalchemy.exc import OperationalError, ProgrammingError

    try:
        inspector = inspect(engine)
        is_postgres = "postgresql" in settings.DATABASE_URL.lower() or "postgres" in settings.DATABASE_URL.lower()
        tables = ("tpv_products", "tpv_sales", "invoices")
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

        if "invoices" in inspector.get_table_names():
            inv_cols = {c["name"] for c in inspector.get_columns("invoices")}
            if "company_id" in inv_cols and "created_by" in inv_cols:
                try:
                    with engine.begin() as conn:
                        conn.execute(
                            text(
                                """
                                UPDATE invoices SET company_id = (
                                    SELECT uc.company_id FROM user_companies uc
                                    WHERE uc.user_id = invoices.created_by
                                    ORDER BY uc.id ASC LIMIT 1
                                ) WHERE company_id IS NULL AND created_by IS NOT NULL
                                """
                            )
                        )
                    print("[MIGRATION] [OK] invoices.company_id backfill desde created_by")
                except Exception as e:
                    print(f"[MIGRATION] [WARN] backfill invoices.company_id: {e}")
    except Exception as e:
        print(f"[MIGRATION] [WARN] No se pudo verificar tpv company_id: {e}")
        import traceback
        traceback.print_exc()


def _migrate_smart_time_control_tables():
    """Columna extra_hours y tablas time_control_* si faltan (SQLite / Postgres sin alembic)."""
    from sqlalchemy import inspect, text
    from sqlalchemy.exc import OperationalError, ProgrammingError

    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        is_postgres = "postgresql" in settings.DATABASE_URL.lower() or "postgres" in settings.DATABASE_URL.lower()

        if "time_tracking_records" in tables:
            cols = {c["name"] for c in inspector.get_columns("time_tracking_records")}
            if "extra_hours" not in cols:
                try:
                    with engine.begin() as conn:
                        if is_postgres:
                            conn.execute(
                                text(
                                    'ALTER TABLE time_tracking_records '
                                    'ADD COLUMN IF NOT EXISTS "extra_hours" DOUBLE PRECISION'
                                )
                            )
                        else:
                            conn.execute(text("ALTER TABLE time_tracking_records ADD COLUMN extra_hours FLOAT"))
                    print("[MIGRATION] [OK] time_tracking_records.extra_hours agregada")
                except (OperationalError, ProgrammingError) as e:
                    em = str(e).lower()
                    if "duplicate column" in em or "already exists" in em:
                        print("[MIGRATION] [INFO] extra_hours ya existe")
                    else:
                        print(f"[MIGRATION] [WARN] extra_hours: {e}")

        if "time_control_events" not in tables:
            print("[MIGRATION] [INFO] time_control_events se creará vía create_all si el modelo está importado")
        if "time_control_alerts" not in tables:
            print("[MIGRATION] [INFO] time_control_alerts se creará vía create_all si el modelo está importado")
    except Exception as e:
        print(f"[MIGRATION] [WARN] smart time control migrate: {e}")


def _migrate_time_cost_engine_v1():
    """Columnas coste laboral + tabla time_cost_checkins (legacy sin Alembic)."""
    from sqlalchemy import inspect, text
    from sqlalchemy.exc import OperationalError, ProgrammingError

    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        is_postgres = "postgresql" in settings.DATABASE_URL.lower() or "postgres" in settings.DATABASE_URL.lower()

        if "company_employees" in tables:
            cols = {c["name"] for c in inspector.get_columns("company_employees")}
            if "hourly_rate" not in cols:
                try:
                    with engine.begin() as conn:
                        if is_postgres:
                            conn.execute(
                                text(
                                    "ALTER TABLE company_employees "
                                    "ADD COLUMN IF NOT EXISTS hourly_rate DOUBLE PRECISION DEFAULT 0"
                                )
                            )
                        else:
                            conn.execute(text("ALTER TABLE company_employees ADD COLUMN hourly_rate FLOAT DEFAULT 0"))
                    print("[MIGRATION] [OK] company_employees.hourly_rate agregada")
                except (OperationalError, ProgrammingError) as e:
                    em = str(e).lower()
                    if "duplicate column" not in em and "already exists" not in em:
                        print(f"[MIGRATION] [WARN] hourly_rate: {e}")

        if "employee_work_sessions" in tables:
            cols = {c["name"] for c in inspector.get_columns("employee_work_sessions")}
            for col_name, ddl_pg, ddl_sqlite in (
                ("total_hours", "DOUBLE PRECISION", "FLOAT"),
                ("total_cost", "DOUBLE PRECISION", "FLOAT"),
                ("partial_cost", "DOUBLE PRECISION", "FLOAT"),
                ("pause_minutes", "DOUBLE PRECISION DEFAULT 0", "FLOAT DEFAULT 0"),
            ):
                if col_name not in cols:
                    try:
                        with engine.begin() as conn:
                            if is_postgres:
                                conn.execute(
                                    text(
                                        f'ALTER TABLE employee_work_sessions '
                                        f'ADD COLUMN IF NOT EXISTS "{col_name}" {ddl_pg}'
                                    )
                                )
                            else:
                                conn.execute(
                                    text(f"ALTER TABLE employee_work_sessions ADD COLUMN {col_name} {ddl_sqlite}")
                                )
                        print(f"[MIGRATION] [OK] employee_work_sessions.{col_name} agregada")
                    except (OperationalError, ProgrammingError) as e:
                        em = str(e).lower()
                        if "duplicate column" not in em and "already exists" not in em:
                            print(f"[MIGRATION] [WARN] employee_work_sessions.{col_name}: {e}")

        if "time_cost_checkins" not in tables:
            print("[MIGRATION] [INFO] time_cost_checkins se creará vía create_all si el modelo está importado")
    except Exception as e:
        print(f"[MIGRATION] [WARN] time cost engine v1 migrate: {e}")


def _migrate_cashflow_ledger():
    """Tabla cashflow_ledger si falta (legacy sin Alembic)."""
    from sqlalchemy import inspect

    try:
        inspector = inspect(engine)
        if "cashflow_ledger" in inspector.get_table_names():
            return
        print("[MIGRATION] [INFO] cashflow_ledger se creará vía create_all si el modelo está importado")
    except Exception as e:
        print(f"[MIGRATION] [WARN] cashflow_ledger migrate: {e}")


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
