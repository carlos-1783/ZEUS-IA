"""RLS fail-closed + rol de aplicacion zeus_app (privilegios DML) + funciones acotadas para rutas sin empresa

Contexto: produccion conecta hoy como `postgres` (superusuario) y con ese rol la RLS es inerte. Para que la
RLS aisle de verdad, la app debe conectar con un rol sin SUPERUSER ni BYPASSRLS (`zeus_app`, creado en 0049)
y las migraciones/DDL con el rol propietario (`DATABASE_MIGRATION_URL`, ver app/db/base.py y alembic/env.py).

Esta migracion da a `zeus_app` lo que necesita la app para funcionar como rol de runtime:
- SELECT, INSERT, UPDATE, DELETE en todas las tablas del esquema public (alembic_version: solo SELECT, lo
  necesita /health para informar de la revision; la app nunca debe escribirla).
- USAGE en todas las secuencias (nextval de las columnas serial / identity).
- ALTER DEFAULT PRIVILEGES: lo mismo para tablas y secuencias que cree en el futuro el rol que ejecuta las
  migraciones (si no, cada tabla nueva quedaria inaccesible para la app hasta un GRANT manual).
Si el rol `zeus_app` no existe en la BD (p. ej. una BD donde 0049 no pudo crearlo), no se hace nada.

Funciones acotadas (SECURITY DEFINER) para lo que la app hace ANTES de saber quien es el usuario o que
necesita un dato puntual de otra empresa (app/db/rls_context.py). Cada una devuelve lo minimo (un id, un
booleano, un recuento) y nunca filas: auth_user_id_by_email (login, reset, webhook), company_slug_taken
(registro: slug unico global), public_site_user_id_by_slug (web publica), agent_activity_owner (log de
actividad: email y empresa primaria del propietario), user_primary_company_by_email (auditoria THALOS de
intentos de login), outbound_recent_count (limite anti-abuso por telefono en todas las empresas).
Se ejecutan con search_path fijo y `app.rls_mode=system` SOLO durante la funcion (asi funcionan aunque el
propietario no sea superusuario y las tablas tengan FORCE ROW LEVEL SECURITY). EXECUTE: se revoca a
PUBLIC y se concede a zeus_app (y lo conserva el propietario: la app conectada como postgres sigue igual).

Policies FAIL-CLOSED (sustituyen a las fail-open de 0047/0053/0070): sin contexto no se ve ni se escribe
ninguna fila. Contexto (app/db/rls_context.py, alcance transaccion, re-aplicado por after_begin):
app.current_user_id, app.current_user_email, app.current_company_ids (empresas del usuario segun
user_companies, resueltas en servidor), app.current_company_id (primaria) y app.rls_mode ('system' =
vision global explicita y auditada: arranque, superusuario, jobs entre empresas). Lectura segura con
app_ctx_int()/app_ctx_company_ids(): vacio o basura -> NULL -> cero filas, nunca error.
- users: el propio usuario + companeros de sus empresas. companies: solo las del contexto.
- invoices/invoice_counters/thalos_*/agent_activities: solo empresas del contexto (USING y WITH CHECK).
  invoices con company_id NULL (legacy): solo su created_by. agent_activities con company_id NULL: solo
  las del email del contexto. Tablas de log (thalos_*, agent_activities): ademas se puede INSERTAR con
  company_id NULL (evento anonimo/sin empresa), pero no leerlo (sus modelos no usan RETURNING).

Idempotente: GRANT/ALTER DEFAULT PRIVILEGES repetidos no fallan ni duplican nada; corre igual sobre una BD
legacy construida por create_all (sello 0069 + upgrade).

Downgrade: restaura EXACTAMENTE las policies de 0047/0053/0070, elimina las funciones acotadas y deja los privilegios de `zeus_app` como los deja la cadena de migraciones hasta 0070 (0049:
DML en insurance_policies/insurance_claims + USAGE,SELECT en sus secuencias; 0070: SELECT,INSERT,UPDATE en
invoice_counters) y retira los DEFAULT PRIVILEGES. Privilegios concedidos A MANO fuera de las migraciones no
se reconstruyen (no hay forma fiable de distinguirlos).

Revision ID: 0071
Revises: 0070
"""
from alembic import op


revision = "0071"
down_revision = "0070"
branch_labels = None
depends_on = None

APP_ROLE = "zeus_app"


def _is_postgres(bind) -> bool:
    return bind.dialect.name == "postgresql"


_GRANTS_SQL = """
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'zeus_app') THEN
        RAISE NOTICE '0071: rol zeus_app inexistente, se omiten los GRANT';
        RETURN;
    END IF;
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO zeus_app', current_database());
    GRANT USAGE ON SCHEMA public TO zeus_app;
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO zeus_app;
    GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO zeus_app;
    IF to_regclass('public.alembic_version') IS NOT NULL THEN
        REVOKE INSERT, UPDATE, DELETE ON alembic_version FROM zeus_app;
    END IF;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO zeus_app;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE ON SEQUENCES TO zeus_app;
END
$$
"""

_RESTORE_CHAIN_GRANTS_SQL = """
DO $$
DECLARE seq text;
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'zeus_app') THEN
        RETURN;
    END IF;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM zeus_app;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE USAGE ON SEQUENCES FROM zeus_app;
    REVOKE ALL ON ALL TABLES IN SCHEMA public FROM zeus_app;
    REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM zeus_app;
    -- 0049
    IF to_regclass('public.insurance_policies') IS NOT NULL THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON insurance_policies TO zeus_app;
        seq := pg_get_serial_sequence('insurance_policies', 'id');
        IF seq IS NOT NULL THEN EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE %s TO zeus_app', seq); END IF;
    END IF;
    IF to_regclass('public.insurance_claims') IS NOT NULL THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON insurance_claims TO zeus_app;
        seq := pg_get_serial_sequence('insurance_claims', 'id');
        IF seq IS NOT NULL THEN EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE %s TO zeus_app', seq); END IF;
    END IF;
    -- 0070
    IF to_regclass('public.invoice_counters') IS NOT NULL THEN
        GRANT SELECT, INSERT, UPDATE ON invoice_counters TO zeus_app;
    END IF;
END
$$
"""


_BOUNDED_FUNCTIONS = (
    (
        "auth_user_id_by_email(text)",
        """
        CREATE OR REPLACE FUNCTION auth_user_id_by_email(p_email text) RETURNS integer
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = public, pg_temp SET app.rls_mode = 'system'
        AS $$ SELECT id FROM users WHERE lower(email) = lower(trim(p_email)) ORDER BY id LIMIT 1 $$
        """,
    ),
    (
        "company_slug_taken(text)",
        """
        CREATE OR REPLACE FUNCTION company_slug_taken(p_slug text) RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = public, pg_temp SET app.rls_mode = 'system'
        AS $$ SELECT EXISTS (SELECT 1 FROM companies WHERE slug = p_slug) $$
        """,
    ),
    (
        "public_site_user_id_by_slug(text)",
        """
        CREATE OR REPLACE FUNCTION public_site_user_id_by_slug(p_slug text) RETURNS integer
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = public, pg_temp SET app.rls_mode = 'system'
        AS $$ SELECT id FROM users
              WHERE public_site_slug = p_slug AND public_site_enabled IS TRUE AND is_active IS TRUE
              ORDER BY id LIMIT 1 $$
        """,
    ),
    (
        "agent_activity_owner(integer, text)",
        """
        CREATE OR REPLACE FUNCTION agent_activity_owner(p_user_id integer, p_email text)
        RETURNS TABLE(user_email text, company_id integer)
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = public, pg_temp SET app.rls_mode = 'system'
        AS $$ SELECT u.email::text,
                     (SELECT uc.company_id FROM user_companies uc WHERE uc.user_id = u.id ORDER BY uc.id LIMIT 1)
              FROM users u
              WHERE (p_user_id IS NOT NULL AND u.id = p_user_id)
                 OR (p_user_id IS NULL AND u.email = p_email)
              ORDER BY u.id LIMIT 1 $$
        """,
    ),
    (
        "user_primary_company_by_email(text)",
        """
        CREATE OR REPLACE FUNCTION user_primary_company_by_email(p_email text) RETURNS integer
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = public, pg_temp SET app.rls_mode = 'system'
        AS $$ SELECT uc.company_id FROM user_companies uc JOIN users u ON u.id = uc.user_id
              WHERE lower(u.email) = lower(trim(p_email)) ORDER BY uc.id LIMIT 1 $$
        """,
    ),
    (
        "outbound_recent_count(text, text, text, timestamp with time zone, text[])",
        """
        CREATE OR REPLACE FUNCTION outbound_recent_count(
            p_channel text, p_purpose text, p_recipient_hash text, p_since timestamptz, p_statuses text[]
        ) RETURNS integer
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = public, pg_temp SET app.rls_mode = 'system'
        AS $$ SELECT count(*)::integer FROM outbound_messages
              WHERE channel = p_channel AND purpose = p_purpose AND recipient_hash = p_recipient_hash
                AND created_at >= p_since AND status = ANY(p_statuses) $$
        """,
    ),
)


def _create_bounded_functions() -> None:
    for signature, ddl in _BOUNDED_FUNCTIONS:
        op.execute(ddl)
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(
            "DO $$ BEGIN IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'zeus_app') THEN "
            f"GRANT EXECUTE ON FUNCTION {signature} TO zeus_app; END IF; END $$"
        )


def _drop_bounded_functions() -> None:
    for signature, _ddl in _BOUNDED_FUNCTIONS:
        op.execute(f"DROP FUNCTION IF EXISTS {signature}")


# --------------------------------------------------------------------------------------------- policies

_HELPERS_SQL = (
    """
    CREATE OR REPLACE FUNCTION app_rls_system() RETURNS boolean
    LANGUAGE sql STABLE PARALLEL SAFE
    AS $$ SELECT coalesce(current_setting('app.rls_mode', true), '') = 'system' $$
    """,
    """
    CREATE OR REPLACE FUNCTION app_ctx_int(p_name text) RETURNS integer
    LANGUAGE sql STABLE PARALLEL SAFE
    AS $$ SELECT CASE WHEN current_setting(p_name, true) ~ '^[0-9]{1,9}$'
                      THEN current_setting(p_name, true)::integer END $$
    """,
    """
    CREATE OR REPLACE FUNCTION app_ctx_company_ids() RETURNS integer[]
    LANGUAGE sql STABLE PARALLEL SAFE
    AS $$ SELECT CASE
                   WHEN current_setting('app.current_company_ids', true) ~ '^[0-9]{1,9}(,[0-9]{1,9})*$'
                     THEN string_to_array(current_setting('app.current_company_ids', true), ',')::integer[]
                   WHEN public.app_ctx_int('app.current_company_id') IS NOT NULL
                     THEN ARRAY[public.app_ctx_int('app.current_company_id')]
                 END $$
    """,
)
_HELPER_SIGNATURES = ("app_ctx_company_ids()", "app_ctx_int(text)", "app_rls_system()")

_IN_CTX = "company_id = ANY (app_ctx_company_ids())"
_CTX_USER = "app_ctx_int('app.current_user_id')"

# tabla -> expresion USING = WITH CHECK (policy tenant_isolation_<tabla>, FOR ALL)
_T1_POLICIES = {
    "users": (
        f"app_rls_system() OR id = {_CTX_USER} OR EXISTS (SELECT 1 FROM user_companies uc "
        "WHERE uc.user_id = users.id AND uc.company_id = ANY (app_ctx_company_ids()))"
    ),
    "companies": "app_rls_system() OR id = ANY (app_ctx_company_ids())",
    "invoices": f"app_rls_system() OR {_IN_CTX} OR (company_id IS NULL AND created_by = {_CTX_USER})",
    "invoice_counters": f"app_rls_system() OR {_IN_CTX}",
    "agent_activities": (
        f"app_rls_system() OR {_IN_CTX} OR (company_id IS NULL "
        "AND user_email = NULLIF(current_setting('app.current_user_email', true), ''))"
    ),
    "thalos_events": f"app_rls_system() OR {_IN_CTX}",
    "thalos_alerts": f"app_rls_system() OR {_IN_CTX}",
    "thalos_security_events": f"app_rls_system() OR {_IN_CTX}",
    "thalos_login_attempts": f"app_rls_system() OR {_IN_CTX}",
}
# Tablas de log: INSERT con company_id NULL permitido (policy tenant_log_insert_<tabla>, FOR INSERT).
_LOG_INSERT_NULL = ("agent_activities", "thalos_events", "thalos_alerts", "thalos_security_events",
                    "thalos_login_attempts")

# Policies anteriores, texto EXACTO de 0047 / 0053 / 0070 (downgrade).
_LEGACY_POLICIES = {
    "invoices": """
            NULLIF(current_setting('app.current_company_id', true), '') IS NULL
            OR company_id::text = current_setting('app.current_company_id', true)
            OR (
                company_id IS NULL
                AND created_by::text = NULLIF(current_setting('app.current_user_id', true), '')
            )""",
    "agent_activities": """
            NULLIF(current_setting('app.current_company_id', true), '') IS NULL
            OR company_id::text = current_setting('app.current_company_id', true)
            OR (
                company_id IS NULL
                AND user_email = NULLIF(current_setting('app.current_user_email', true), '')
            )""",
    "companies": """
            NULLIF(current_setting('app.current_company_id', true), '') IS NULL
            OR id::text = current_setting('app.current_company_id', true)
            OR EXISTS (
                SELECT 1 FROM user_companies uc
                WHERE uc.company_id = companies.id
                  AND uc.user_id::text = NULLIF(current_setting('app.current_user_id', true), '')
            )""",
    "users": """
            NULLIF(current_setting('app.current_user_id', true), '') IS NULL
            OR id::text = current_setting('app.current_user_id', true)
            OR EXISTS (
                SELECT 1 FROM user_companies uc1
                JOIN user_companies uc2 ON uc1.company_id = uc2.company_id
                WHERE uc1.user_id = users.id
                  AND uc2.user_id::text = NULLIF(current_setting('app.current_user_id', true), '')
            )""",
    "thalos_events": """
            NULLIF(current_setting('app.current_company_id', true), '') IS NULL
            OR company_id::text = current_setting('app.current_company_id', true)""",
    "thalos_alerts": """
            NULLIF(current_setting('app.current_company_id', true), '') IS NULL
            OR company_id::text = current_setting('app.current_company_id', true)""",
    "thalos_security_events": """
            NULLIF(current_setting('app.current_company_id', true), '') IS NULL
            OR company_id::text = current_setting('app.current_company_id', true)""",
    "thalos_login_attempts": """
            NULLIF(current_setting('app.current_company_id', true), '') IS NULL
            OR company_id::text = current_setting('app.current_company_id', true)""",
    "invoice_counters": """
                NULLIF(current_setting('app.current_company_id', true), '') IS NULL
                OR company_id::text = current_setting('app.current_company_id', true)""",
}


def _has_table(bind, table: str) -> bool:
    from sqlalchemy import inspect

    return inspect(bind).has_table(table)


def _fail_closed(table: str, expr: str) -> None:
    """ENABLE + FORCE RLS y policy FOR ALL con la misma expresion en USING y WITH CHECK (idempotente)."""
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
    op.execute(f"CREATE POLICY tenant_isolation_{table} ON {table} USING ({expr}) WITH CHECK ({expr})")


def _log_insert_null(table: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_log_insert_{table} ON {table}")
    op.execute(f"CREATE POLICY tenant_log_insert_{table} ON {table} FOR INSERT WITH CHECK (company_id IS NULL)")


def _upgrade_policies(bind) -> None:
    for ddl in _HELPERS_SQL:
        op.execute(ddl)
    for table, expr in _T1_POLICIES.items():
        if _has_table(bind, table):
            _fail_closed(table, expr)
    for table in _LOG_INSERT_NULL:
        if _has_table(bind, table):
            _log_insert_null(table)


def _downgrade_policies(bind) -> None:
    for table in _LOG_INSERT_NULL:
        if _has_table(bind, table):
            op.execute(f"DROP POLICY IF EXISTS tenant_log_insert_{table} ON {table}")
    for table, legacy in _LEGACY_POLICIES.items():
        if not _has_table(bind, table):
            continue
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.execute(f"CREATE POLICY tenant_isolation_{table} ON {table}\n        USING ({legacy}\n        )")
    for signature in _HELPER_SIGNATURES:
        op.execute(f"DROP FUNCTION IF EXISTS {signature}")


def upgrade() -> None:
    bind = op.get_bind()
    if not _is_postgres(bind):
        return
    op.execute(_GRANTS_SQL)
    _create_bounded_functions()
    _upgrade_policies(bind)


def downgrade() -> None:
    bind = op.get_bind()
    if not _is_postgres(bind):
        return
    _downgrade_policies(bind)
    _drop_bounded_functions()
    op.execute(_RESTORE_CHAIN_GRANTS_SQL)
