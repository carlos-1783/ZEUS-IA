"""Rol de aplicacion zeus_app: privilegios DML completos (base para conectar la app sin superusuario)

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

Idempotente: GRANT/ALTER DEFAULT PRIVILEGES repetidos no fallan ni duplican nada; corre igual sobre una BD
legacy construida por create_all (sello 0069 + upgrade).

Downgrade: elimina las funciones acotadas y deja los privilegios de `zeus_app` como los deja la cadena de migraciones hasta 0070 (0049:
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


def upgrade() -> None:
    bind = op.get_bind()
    if not _is_postgres(bind):
        return
    op.execute(_GRANTS_SQL)
    _create_bounded_functions()


def downgrade() -> None:
    bind = op.get_bind()
    if not _is_postgres(bind):
        return
    _drop_bounded_functions()
    op.execute(_RESTORE_CHAIN_GRANTS_SQL)
