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


def _is_postgres_url() -> bool:
    return "postgresql" in settings.DATABASE_URL.lower() or "postgres" in settings.DATABASE_URL.lower()


def _current_role_can_alter_schema() -> bool:
    """True si el rol de conexión puede ejecutar `ALTER TABLE` sobre el
    esquema de la aplicación.

    SQLite no tiene modelo de ownership -> siempre True (comportamiento sin
    cambios). En PostgreSQL, hoy en día el 100% de las columnas/tablas que
    `ensure_schema_patches()` intenta añadir ya tienen una migración Alembic
    real (ver AUDIT_FIX_RLS_INSURANCE_SCHEMA.md y la migración 0056, que
    cerró el último hueco real: 13 columnas de `users`). Bajo el rol de
    runtime endurecido recomendado para producción (`zeus_app`, sin
    `SUPERUSER` ni ownership de las tablas), cada `ALTER TABLE` de este
    módulo fallaba con `InsufficientPrivilege`, se registraba como un WARN
    y se ignoraba en silencio -- si la columna en cuestión de verdad faltaba
    (p. ej. una BD a la que aún no se le aplicó `alembic upgrade head`), el
    fallo real no se veía hasta que un endpoint disparaba `UndefinedColumn`
    en mitad de una petición (ver app/db/session.py, 503 schema_missing).

    Con este chequeo, si el rol no es superusuario ni dueño de las tablas,
    `ensure_schema_patches()` se salta por completo en vez de intentar (y
    fallar) columna a columna: el esquema real pasa a depender exclusiva-
    mente de `alembic upgrade head`, ejecutado con un rol propietario, tal
    como ya recomendaba `dec54c0` para separar credenciales de
    migración/DDL de las credenciales de runtime."""
    if not _is_postgres_url():
        return True
    try:
        from sqlalchemy import text

        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT
                        COALESCE((SELECT rolsuper FROM pg_roles WHERE rolname = current_user), false) AS is_super,
                        EXISTS (
                            SELECT 1 FROM pg_class c
                            JOIN pg_roles r ON r.oid = c.relowner
                            WHERE c.relname = 'users' AND r.rolname = current_user
                        ) AS owns_users
                    """
                )
            ).first()
        if row is None:
            # No se pudo evaluar (p.ej. sin permiso de lectura de catálogo) ->
            # asumir que NO se puede alterar, por seguridad: es preferible
            # omitir un parche opcional a lanzar ALTER TABLE a ciegas.
            return False
        return bool(row[0]) or bool(row[1])
    except Exception as e:
        logger.warning(
            "ensure_schema_patches: no se pudo determinar si el rol puede alterar "
            "el esquema (%s); se asume que no, por seguridad", e,
        )
        return False


def ensure_schema_patches():
    """Migraciones idempotentes (legacy sin Alembic real). Seguro llamar en cada arranque."""
    try:
        if not _current_role_can_alter_schema():
            msg = (
                "[SCHEMA] Rol de conexión sin privilegios de ALTER TABLE "
                "(rol de runtime endurecido, p.ej. zeus_app) -- se omiten los "
                "parches de esquema en caliente. Todo lo que hacían ya tiene "
                "migración Alembic real; ejecuta `alembic upgrade head` con un "
                "rol propietario de las tablas antes de arrancar la app con "
                "este rol."
            )
            print(msg)
            logger.info(msg)
            return
        print("[SCHEMA] Aplicando parches de esquema...")
        _migrate_user_columns()
        _migrate_document_approvals_columns()
        _migrate_rafael_fiscal_tables()
        _migrate_tpv_company_columns()
        _migrate_company_type_column()
        _migrate_company_employees_tpv_pin_hash()
        _migrate_invoice_tpv_sale_link()
        _migrate_smart_time_control_tables()
        _migrate_time_cost_engine_v1()
        _migrate_cashflow_ledger()
        _migrate_zeus_domain_events()
        _migrate_zeus_analytics_tables()
        _migrate_agent_activities_company_id()
        _migrate_zeus_approvals_execution_columns()
        _migrate_zeus_approvals_chat_columns()
        _migrate_role_check_constraints()
        _migrate_rename_misleading_company_id_columns()
        _migrate_company_billing_fields()
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
            from app.models.thalos_event import ThalosEvent
            from app.models.thalos_alert import ThalosAlert
            from app.models.zeus_closure_audit import ZeusClosureAudit
            from app.models.thalos_workspace_item import ThalosWorkspaceItem
            from app.models.workspace_file import WorkspaceFile
            from app.models.workspace_playbook import WorkspacePlaybook
            from app.models.ops_route import OpsRoute
            from app.models.zeus_transaction import ZeusTransaction
            from app.models.perseo_job import PerseoJob
            from app.models.legal_document import LegalDocument
            from app.models.compliance_event import ComplianceEvent
            from app.models.teamflow_item import TeamFlowItem
            from app.models.teamflow_event import TeamFlowEvent
            from app.models.zeus_domain_event import ZeusDomainEvent
            from app.models.tpv_operator_session import TPVOperatorSession
            from app.models.insurance import InsurancePolicy, InsuranceClaim
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


def _migrate_company_type_column():
    """companies.company_type — existe en el modelo (Company.company_type)
    desde hace tiempo y tiene migración Alembic (0022), pero nunca tuvo un
    parche de arranque como el resto de columnas de este archivo. En
    cualquier instalación donde esa migración no se haya ejecutado de verdad
    (mismo motivo que el resto de parches de aquí: bases 'legacy' donde
    alembic_conditional_stamp.py hace `stamp head` sin ejecutar), CUALQUIER
    query ORM sobre Company (SELECT * de facto) rompe con
    'no such column: companies.company_type' — incluye GET /onboarding/status
    y POST /onboarding/profile, confirmado reproduciendo el error real."""
    from sqlalchemy import inspect, text
    from sqlalchemy.exc import OperationalError, ProgrammingError

    try:
        inspector = inspect(engine)
        is_postgres = "postgresql" in settings.DATABASE_URL.lower() or "postgres" in settings.DATABASE_URL.lower()
        table_name = "companies"
        if table_name not in inspector.get_table_names():
            return
        cols = {c["name"] for c in inspector.get_columns(table_name)}
        if "company_type" not in cols:
            try:
                with engine.begin() as conn:
                    if is_postgres:
                        conn.execute(
                            text('ALTER TABLE "companies" ADD COLUMN IF NOT EXISTS "company_type" VARCHAR(32)')
                        )
                    else:
                        conn.execute(text("ALTER TABLE companies ADD COLUMN company_type VARCHAR(32)"))
                print("[MIGRATION] [OK] companies.company_type agregada")
            except (OperationalError, ProgrammingError) as e:
                em = str(e).lower()
                if "duplicate column" in em or "already exists" in em:
                    print("[MIGRATION] [INFO] companies.company_type ya existe")
                else:
                    print(f"[MIGRATION] [WARN] No se pudo agregar companies.company_type: {e}")

        try:
            indexes = {ix["name"] for ix in inspector.get_indexes(table_name)}
            idx_name = "ix_companies_company_type"
            if idx_name not in indexes:
                with engine.begin() as conn:
                    if is_postgres:
                        conn.execute(
                            text(f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "companies" (company_type)')
                        )
                    else:
                        conn.execute(
                            text(f"CREATE INDEX IF NOT EXISTS {idx_name} ON companies(company_type)")
                        )
                print(f"[MIGRATION] [OK] Índice {idx_name} creado")
        except Exception as e:
            print(f"[MIGRATION] [WARN] No se pudo crear índice company_type: {e}")

        # Backfill best-effort en Python (evita operadores JSON ->> específicos
        # de Postgres que no son portables a SQLite) — mismo criterio que la
        # migración 0022: business_type/sector -> office | bar_restaurant.
        try:
            from app.models.company import Company

            session = SessionLocal()
            try:
                rows = session.query(Company).filter(Company.company_type.is_(None)).all()
                for co in rows:
                    meta = co.metadata_ if isinstance(co.metadata_, dict) else {}
                    business_type = str(meta.get("business_type") or "").strip().lower()
                    sector = str(co.sector or "").strip().lower()
                    if business_type == "services" or "servicio" in sector or "oficina" in sector:
                        co.company_type = "office"
                    else:
                        co.company_type = "bar_restaurant"
                    session.add(co)
                if rows:
                    session.commit()
                    print(f"[MIGRATION] [OK] companies.company_type backfill aplicado a {len(rows)} filas")
            finally:
                session.close()
        except Exception as e:
            print(f"[MIGRATION] [WARN] backfill companies.company_type: {e}")
    except Exception as e:
        print(f"[MIGRATION] [WARN] No se pudo verificar companies.company_type: {e}")
        import traceback
        traceback.print_exc()


def _migrate_invoice_tpv_sale_link():
    """invoices.tpv_sale_id — enlace real factura <-> venta TPV (puente TPV -> RAFAEL, 1 factura por venta)."""
    from sqlalchemy import inspect, text
    from sqlalchemy.exc import OperationalError, ProgrammingError

    try:
        inspector = inspect(engine)
        if "invoices" not in inspector.get_table_names():
            return
        is_postgres = "postgresql" in settings.DATABASE_URL.lower() or "postgres" in settings.DATABASE_URL.lower()
        cols = {c["name"] for c in inspector.get_columns("invoices")}
        if "tpv_sale_id" not in cols:
            try:
                with engine.begin() as conn:
                    if is_postgres:
                        conn.execute(
                            text('ALTER TABLE "invoices" ADD COLUMN IF NOT EXISTS "tpv_sale_id" INTEGER')
                        )
                    else:
                        conn.execute(text("ALTER TABLE invoices ADD COLUMN tpv_sale_id INTEGER"))
                print("[MIGRATION] [OK] invoices.tpv_sale_id agregada")
            except (OperationalError, ProgrammingError) as e:
                em = str(e).lower()
                if "duplicate column" in em or "already exists" in em:
                    print("[MIGRATION] [INFO] invoices.tpv_sale_id ya existe")
                else:
                    print(f"[MIGRATION] [WARN] No se pudo agregar invoices.tpv_sale_id: {e}")

        try:
            indexes = {ix["name"] for ix in inspector.get_indexes("invoices")}
            idx_name = "ix_invoices_tpv_sale_id"
            if idx_name not in indexes:
                with engine.begin() as conn:
                    if is_postgres:
                        conn.execute(
                            text(f'CREATE UNIQUE INDEX IF NOT EXISTS "{idx_name}" ON "invoices" (tpv_sale_id)')
                        )
                    else:
                        conn.execute(
                            text(f"CREATE UNIQUE INDEX IF NOT EXISTS {idx_name} ON invoices(tpv_sale_id)")
                        )
                print(f"[MIGRATION] [OK] Índice único {idx_name} creado (1 factura por venta TPV)")
        except Exception as e:
            print(f"[MIGRATION] [WARN] No se pudo crear índice único tpv_sale_id en invoices: {e}")
    except Exception as e:
        print(f"[MIGRATION] [WARN] No se pudo verificar invoices.tpv_sale_id: {e}")


def _migrate_company_employees_tpv_pin_hash():
    """company_employees.tpv_pin_hash — misma historia que company_type:
    columna añadida por la migración 0019 (op.add_column, no create_table),
    sin parche de arranque. Bloqueaba GET /onboarding/status (cuenta de
    empleados vía COUNT(*) sobre company_employees, que selecciona todas
    las columnas) con 'no such column: company_employees.tpv_pin_hash' en
    cualquier instalación donde esa migración no se ejecutó de verdad."""
    from sqlalchemy import inspect, text
    from sqlalchemy.exc import OperationalError, ProgrammingError

    try:
        inspector = inspect(engine)
        is_postgres = "postgresql" in settings.DATABASE_URL.lower() or "postgres" in settings.DATABASE_URL.lower()
        table_name = "company_employees"
        if table_name not in inspector.get_table_names():
            return
        cols = {c["name"] for c in inspector.get_columns(table_name)}
        if "tpv_pin_hash" in cols:
            return
        try:
            with engine.begin() as conn:
                if is_postgres:
                    conn.execute(
                        text('ALTER TABLE "company_employees" ADD COLUMN IF NOT EXISTS "tpv_pin_hash" VARCHAR(255)')
                    )
                else:
                    conn.execute(text("ALTER TABLE company_employees ADD COLUMN tpv_pin_hash VARCHAR(255)"))
            print("[MIGRATION] [OK] company_employees.tpv_pin_hash agregada")
        except (OperationalError, ProgrammingError) as e:
            em = str(e).lower()
            if "duplicate column" in em or "already exists" in em:
                print("[MIGRATION] [INFO] company_employees.tpv_pin_hash ya existe")
            else:
                print(f"[MIGRATION] [WARN] No se pudo agregar company_employees.tpv_pin_hash: {e}")
    except Exception as e:
        print(f"[MIGRATION] [WARN] No se pudo verificar company_employees.tpv_pin_hash: {e}")
        import traceback
        traceback.print_exc()


def _migrate_zeus_approvals_execution_columns():
    """result_json / executed_at en zeus_pending_approvals (J2, alembic 0059).
    Igual que otros parches: en despliegues con `stamp head` este parche
    idempotente es el que realmente anade las columnas."""
    from sqlalchemy import inspect, text

    try:
        inspector = inspect(engine)
        table_name = "zeus_pending_approvals"
        if table_name not in inspector.get_table_names():
            return
        is_postgres = "postgres" in settings.DATABASE_URL.lower()
        cols = {c["name"] for c in inspector.get_columns(table_name)}
        wanted = {
            "result_json": "TEXT",
            "executed_at": "TIMESTAMP WITH TIME ZONE" if is_postgres else "DATETIME",
        }
        for col, ddl in wanted.items():
            if col in cols:
                continue
            with engine.begin() as conn:
                if is_postgres:
                    conn.execute(text(f'ALTER TABLE "{table_name}" ADD COLUMN IF NOT EXISTS "{col}" {ddl}'))
                else:
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col} {ddl}"))
            print(f"[MIGRATION] [OK] {table_name}.{col} agregada")
    except Exception as e:
        print(f"[MIGRATION] [WARN] zeus_pending_approvals ejecucion: {e}")


def _migrate_zeus_approvals_chat_columns():
    """thread_id / expires_at en zeus_pending_approvals (J3b, alembic 0060). Idempotente."""
    from sqlalchemy import inspect, text

    try:
        inspector = inspect(engine)
        table_name = "zeus_pending_approvals"
        if table_name not in inspector.get_table_names():
            return
        is_postgres = "postgres" in settings.DATABASE_URL.lower()
        cols = {c["name"] for c in inspector.get_columns(table_name)}
        wanted = {
            "thread_id": "VARCHAR(128)",
            "expires_at": "TIMESTAMP WITH TIME ZONE" if is_postgres else "DATETIME",
        }
        for col, ddl in wanted.items():
            if col in cols:
                continue
            with engine.begin() as conn:
                if is_postgres:
                    conn.execute(text(f'ALTER TABLE "{table_name}" ADD COLUMN IF NOT EXISTS "{col}" {ddl}'))
                else:
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col} {ddl}"))
            print(f"[MIGRATION] [OK] {table_name}.{col} agregada")
        with engine.begin() as conn:
            conn.execute(text(
                f"CREATE INDEX IF NOT EXISTS ix_zeus_pending_approvals_thread_id ON {table_name} (thread_id)"
            ))
    except Exception as e:
        print(f"[MIGRATION] [WARN] zeus_pending_approvals chat: {e}")


def _migrate_agent_activities_company_id():
    """company_id en agent_activities (aislamiento multi-tenant de la actividad
    de agentes IA). Necesario porque en despliegues existentes (Railway con
    `users` ya presente) alembic_conditional_stamp.py hace `stamp head` sin
    ejecutar las migraciones — este parche idempotente es el único mecanismo
    que realmente añade la columna ahí, igual que _migrate_tpv_company_columns
    para invoices/tpv_*."""
    from sqlalchemy import inspect, text
    from sqlalchemy.exc import OperationalError, ProgrammingError

    try:
        inspector = inspect(engine)
        is_postgres = "postgresql" in settings.DATABASE_URL.lower() or "postgres" in settings.DATABASE_URL.lower()
        table_name = "agent_activities"
        if table_name not in inspector.get_table_names():
            return
        cols = {c["name"] for c in inspector.get_columns(table_name)}
        if "company_id" not in cols:
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

        # Backfill best-effort desde user_email -> users -> user_companies
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        UPDATE agent_activities
                        SET company_id = (
                            SELECT uc.company_id FROM user_companies uc
                            JOIN users u ON u.id = uc.user_id
                            WHERE u.email = agent_activities.user_email
                            ORDER BY uc.id ASC LIMIT 1
                        )
                        WHERE company_id IS NULL AND user_email IS NOT NULL
                        """
                    )
                )
            print("[MIGRATION] [OK] agent_activities.company_id backfill desde user_email")
        except Exception as e:
            print(f"[MIGRATION] [WARN] backfill agent_activities.company_id: {e}")
    except Exception as e:
        print(f"[MIGRATION] [WARN] No se pudo verificar agent_activities.company_id: {e}")
        import traceback
        traceback.print_exc()


def _migrate_role_check_constraints():
    """CHECK constraint real en users.role y user_companies.role (antes texto
    libre). Solo se aplica aquí en Postgres: en SQLite, añadir un CHECK a una
    tabla existente exige recrearla (lo que Alembic hace de forma segura vía
    batch_alter_table en la migración 0044); reimplementar esa recreación a
    mano en un patch de arranque es riesgo innecesario para las tablas
    users/user_companies. En local, la migración de Alembic es la vía
    correcta para aplicar este constraint."""
    from sqlalchemy import inspect, text
    from sqlalchemy.exc import OperationalError, ProgrammingError

    is_postgres = "postgresql" in settings.DATABASE_URL.lower() or "postgres" in settings.DATABASE_URL.lower()
    if not is_postgres:
        return

    try:
        inspector = inspect(engine)

        if "users" in inspector.get_table_names():
            existing_ck = {c["name"] for c in inspector.get_check_constraints("users")}
            if "ck_users_role" in existing_ck:
                print("[MIGRATION] [INFO] ck_users_role ya existe")
            else:
                try:
                    with engine.begin() as conn:
                        conn.execute(
                            text("UPDATE users SET role = 'owner' WHERE role IS NULL OR role NOT IN ('owner', 'employee')")
                        )
                        conn.execute(
                            text(
                                "ALTER TABLE users ADD CONSTRAINT ck_users_role "
                                "CHECK (role IN ('owner', 'employee'))"
                            )
                        )
                    print("[MIGRATION] [OK] ck_users_role creado")
                except (OperationalError, ProgrammingError) as e:
                    if "already exists" in str(e).lower():
                        print("[MIGRATION] [INFO] ck_users_role ya existe")
                    else:
                        print(f"[MIGRATION] [WARN] No se pudo crear ck_users_role: {e}")

        if "user_companies" in inspector.get_table_names():
            existing_ck = {c["name"] for c in inspector.get_check_constraints("user_companies")}
            if "ck_user_companies_role" in existing_ck:
                print("[MIGRATION] [INFO] ck_user_companies_role ya existe")
            else:
                try:
                    with engine.begin() as conn:
                        conn.execute(
                            text(
                                "UPDATE user_companies SET role = 'company_admin' "
                                "WHERE role IS NULL OR role NOT IN ('company_admin', 'member', 'owner')"
                            )
                        )
                        conn.execute(
                            text(
                                "ALTER TABLE user_companies ADD CONSTRAINT ck_user_companies_role "
                                "CHECK (role IN ('company_admin', 'member', 'owner'))"
                            )
                        )
                    print("[MIGRATION] [OK] ck_user_companies_role creado")
                except (OperationalError, ProgrammingError) as e:
                    if "already exists" in str(e).lower():
                        print("[MIGRATION] [INFO] ck_user_companies_role ya existe")
                    else:
                        print(f"[MIGRATION] [WARN] No se pudo crear ck_user_companies_role: {e}")
    except Exception as e:
        print(f"[MIGRATION] [WARN] No se pudo verificar role check constraints: {e}")


def _migrate_rename_misleading_company_id_columns():
    """payroll_drafts.company_id -> owner_user_id, automation_readiness.company_id
    -> user_id. Ambas columnas apuntan (y siempre apuntaron) a users.id, nunca a
    companies.id — solo se corrige el nombre engañoso, ver alembic/versions/
    0045_fix_misleading_company_id_naming.py para el detalle completo."""
    from sqlalchemy import inspect, text
    from sqlalchemy.exc import OperationalError, ProgrammingError

    try:
        inspector = inspect(engine)
        renames = (
            ("payroll_drafts", "company_id", "owner_user_id"),
            ("automation_readiness", "company_id", "user_id"),
        )
        for table_name, old_col, new_col in renames:
            if table_name not in inspector.get_table_names():
                continue
            cols = {c["name"] for c in inspector.get_columns(table_name)}
            if new_col in cols:
                continue
            if old_col not in cols:
                continue
            try:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE {table_name} RENAME COLUMN {old_col} TO {new_col}"))
                print(f"[MIGRATION] [OK] {table_name}.{old_col} renombrada a {new_col}")
            except (OperationalError, ProgrammingError) as e:
                print(f"[MIGRATION] [WARN] No se pudo renombrar {table_name}.{old_col}: {e}")
    except Exception as e:
        print(f"[MIGRATION] [WARN] No se pudo verificar rename de columnas company_id: {e}")


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


def _migrate_zeus_domain_events():
    """Tabla zeus_domain_events si falta (event bus v1 / migration 0042)."""
    from sqlalchemy import inspect

    try:
        if "zeus_domain_events" in inspect(engine).get_table_names():
            return
        from app.models.zeus_domain_event import ZeusDomainEvent

        ZeusDomainEvent.__table__.create(bind=engine, checkfirst=True)
        print("[MIGRATION] [OK] zeus_domain_events creada")
    except Exception as e:
        print(f"[MIGRATION] [WARN] zeus_domain_events migrate: {e}")


def _migrate_zeus_analytics_tables():
    """Tablas zeus_events, zeus_alerts, zeus_automations (executive analytics)."""
    from sqlalchemy import inspect

    try:
        from app.models.zeus_analytics import ZeusAlert, ZeusAutomation, ZeusAutomationLog, ZeusEvent

        inspector = inspect(engine)
        names = set(inspector.get_table_names())
        for model in (ZeusEvent, ZeusAlert, ZeusAutomation, ZeusAutomationLog):
            if model.__tablename__ not in names:
                model.__table__.create(bind=engine, checkfirst=True)
                print(f"[MIGRATION] [OK] {model.__tablename__} creada")
    except Exception as e:
        print(f"[MIGRATION] [WARN] zeus_analytics tables migrate: {e}")


def _migrate_company_billing_fields():
    """Columnas tax_id/legal_name/iban_encrypted en companies (migration 0043)."""
    from sqlalchemy import inspect, text
    from sqlalchemy.exc import OperationalError, ProgrammingError

    try:
        inspector = inspect(engine)
        if "companies" not in inspector.get_table_names():
            return
        is_postgres = "postgresql" in settings.DATABASE_URL.lower() or "postgres" in settings.DATABASE_URL.lower()
        cols = {c["name"] for c in inspector.get_columns("companies")}

        additions = [
            ("tax_id", "VARCHAR(20)"),
            ("legal_name", "VARCHAR(255)"),
            ("iban_encrypted", "TEXT"),
        ]
        for col_name, col_type in additions:
            if col_name in cols:
                continue
            try:
                with engine.begin() as conn:
                    if is_postgres:
                        conn.execute(
                            text(f'ALTER TABLE "companies" ADD COLUMN IF NOT EXISTS "{col_name}" {col_type}')
                        )
                    else:
                        conn.execute(text(f"ALTER TABLE companies ADD COLUMN {col_name} {col_type}"))
                print(f"[MIGRATION] [OK] companies.{col_name} agregada")
            except (OperationalError, ProgrammingError) as e:
                em = str(e).lower()
                if "duplicate column" in em or "already exists" in em:
                    print(f"[MIGRATION] [INFO] companies.{col_name} ya existe")
                else:
                    print(f"[MIGRATION] [WARN] No se pudo agregar companies.{col_name}: {e}")

        try:
            indexes = {ix["name"] for ix in inspector.get_indexes("companies")}
            if "ix_companies_tax_id" not in indexes:
                with engine.begin() as conn:
                    if is_postgres:
                        conn.execute(
                            text('CREATE INDEX IF NOT EXISTS "ix_companies_tax_id" ON "companies" (tax_id)')
                        )
                    else:
                        conn.execute(
                            text("CREATE INDEX IF NOT EXISTS ix_companies_tax_id ON companies(tax_id)")
                        )
        except Exception as e:
            print(f"[MIGRATION] [WARN] No se pudo crear índice tax_id en companies: {e}")
    except Exception as e:
        print(f"[MIGRATION] [WARN] No se pudo verificar company billing fields: {e}")


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

# get_db está ahora en session.py con manejo de errores mejorado.
# Mantener esta función por compatibilidad (nadie en app/ la importa ya tras
# E5: los dos únicos consumidores que quedaban -- app/core/auth.py y
# app/api/v1/endpoints/commands.py -- se migraron a `from app.db.session
# import get_db`), pero NO convertirla en un simple re-export
# (`from app.db.session import get_db`) a nivel de módulo: `session.py` hace
# `from app.db.base import SessionLocal` en su propia cabecera, así que un
# re-export a nivel de módulo aquí crearía un import circular que revienta
# o no según qué módulo se importe primero en el arranque. Por eso el import
# se mantiene diferido dentro de la función (solo se ejecuta cuando FastAPI
# ya resolvió ambos módulos).
#
# Aviso importante para quien reintroduzca un import de este `get_db`: esta
# función NO es el mismo objeto que `app.db.session.get_db`, aunque delega
# en ella. FastAPI cachea dependencias dentro de una misma request por
# identidad de función (`Dependant.cache_key = (self.call, scopes)`,
# ver fastapi/dependencies/models.py) -- si en la misma request conviven
# `Depends(app.db.base.get_db)` y `Depends(app.db.session.get_db)` (p.ej.
# porque un endpoint usa `Depends(get_current_active_user)` que depende de
# uno de los dos, y el propio endpoint declara `db: Session = Depends(...)`
# con el otro), FastAPI NO las deduplica y se crean DOS sesiones de
# SQLAlchemy independientes para la misma request (la causa raíz exacta del
# 500 de doble sesión corregido puntualmente en onboarding, commit 038096f).
# Usa siempre `from app.db.session import get_db` en código nuevo.
def get_db():
    """Función de compatibilidad - usar session.get_db() en su lugar"""
    from app.db.session import get_db as get_db_with_retry
    yield from get_db_with_retry()
