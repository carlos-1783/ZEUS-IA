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

Idempotente: GRANT/ALTER DEFAULT PRIVILEGES repetidos no fallan ni duplican nada; corre igual sobre una BD
legacy construida por create_all (sello 0069 + upgrade).

Downgrade: deja los privilegios de `zeus_app` como los deja la cadena de migraciones hasta 0070 (0049:
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


def upgrade() -> None:
    bind = op.get_bind()
    if not _is_postgres(bind):
        return
    op.execute(_GRANTS_SQL)


def downgrade() -> None:
    bind = op.get_bind()
    if not _is_postgres(bind):
        return
    op.execute(_RESTORE_CHAIN_GRANTS_SQL)
