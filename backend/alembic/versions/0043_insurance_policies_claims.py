"""insurance_policies / insurance_claims — vertical Seguros (Multirriesgo)

Primer trabajo de la vertical Seguros (AUDITORIA_100_COMPLETA.md: 0% de
código, ningún modelo de datos, ninguna rama propia). Crea las dos tablas
base del ciclo captación -> venta -> gestión -> siniestros y activa Row
Level Security nativo de PostgreSQL desde el primer momento, con un rol de
aplicación (`zeus_app`) sin privilegios de superusuario.

## Nota de entorno — importante para quien aplique esta migración

El desarrollo local de este proyecto corre sobre SQLite (`zeus.db`); RLS no
existe en SQLite. Todo el bloque de RLS/rol de esta migración se ejecuta
SOLO si el dialecto es PostgreSQL (`op.get_bind().dialect.name ==
"postgresql"`) — en SQLite es un no-op completo, igual que antes de esta
migración. La creación de las dos tablas sí es multi-dialecto (SQLAlchemy
Core, funciona en ambos).

## Diseño de las policies — fail-closed (deny por defecto)

A diferencia de la migración de referencia consultada
(`feature/multi-tenant-bd:backend/alembic/versions/0047_row_level_security.py`,
solo para consulta, no copiada literal — cubre otras tablas y usa un
diseño "fail-open cuando no hay contexto"), aquí se optó deliberadamente
por **fail-closed**: si la sesión no ha establecido
`app.current_company_id` (vía `SET`/`set_config`), la policy no deja ver
NINGUNA fila, en vez de dejar ver todo. Motivo: estas son tablas nuevas,
sin ningún consumidor legacy que dependa de verlas sin contexto — no hay
riesgo de romper nada existente, y el diseño fail-closed es más estricto
y no depende de que cada endpoint recuerde establecer el contexto para
tener protección real (si se le olvida, la query no ve nada en vez de
verlo todo).

## Rol `zeus_app`

Se crea (si no existe ya) sin `SUPERUSER`, sin `BYPASSRLS`, con los GRANT
mínimos sobre estas dos tablas y sus secuencias de `id`. Deliberadamente
SIN contraseña fijada en esta migración (fijar una contraseña en texto
plano en un fichero versionado sería el mismo antipatrón de credenciales
hardcodeadas ya señalado como hallazgo en CICLO_PRODUCCION.md, Ciclo 6) —
la contraseña real debe fijarse fuera de banda con
`ALTER ROLE zeus_app WITH PASSWORD '...'` usando el gestor de secretos del
entorno (Railway env var), no en el control de versiones.

Si la creación del rol falla por privilegios insuficientes del usuario que
aplica la migración (habitual si Alembic conecta con un rol que no puede
`CREATE ROLE`), se captura y se registra un `NOTICE` en vez de abortar toda
la migración — las tablas y las policies de RLS quedan creadas igualmente;
solo el rol de aplicación queda pendiente de crear manualmente.

Revision ID: 0043
Revises: 0042
"""
from alembic import op
import sqlalchemy as sa

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    existing_tables = set(inspect(bind).get_table_names())

    if "insurance_policies" not in existing_tables:
        op.create_table(
            "insurance_policies",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "company_id",
                sa.Integer(),
                sa.ForeignKey("companies.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "customer_id",
                sa.Integer(),
                sa.ForeignKey("customers.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("policy_number", sa.String(50), nullable=False, unique=True),
            sa.Column("coverages", sa.JSON(), nullable=False),
            sa.Column("insured_risk", sa.JSON(), nullable=True),
            sa.Column("premium_amount", sa.Numeric(10, 2), nullable=False),
            sa.Column("start_date", sa.Date(), nullable=False),
            sa.Column("renewal_date", sa.Date(), nullable=True),
            sa.Column(
                "status",
                sa.Enum("draft", "active", "cancelled", "expired", name="insurance_policy_status"),
                nullable=False,
            ),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column(
                "created_by",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_insurance_policies_company_id", "insurance_policies", ["company_id"])
        op.create_index("ix_insurance_policies_customer_id", "insurance_policies", ["customer_id"])
        op.create_index("ix_insurance_policies_policy_number", "insurance_policies", ["policy_number"], unique=True)

    if "insurance_claims" not in existing_tables:
        op.create_table(
            "insurance_claims",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "policy_id",
                sa.Integer(),
                sa.ForeignKey("insurance_policies.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "company_id",
                sa.Integer(),
                sa.ForeignKey("companies.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("claim_date", sa.Date(), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column(
                "status",
                sa.Enum("open", "investigating", "resolved", "rejected", name="insurance_claim_status"),
                nullable=False,
            ),
            sa.Column("estimated_amount", sa.Numeric(10, 2), nullable=True),
            sa.Column("resolved_amount", sa.Numeric(10, 2), nullable=True),
            sa.Column("documents", sa.JSON(), nullable=False),
            sa.Column(
                "created_by",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_insurance_claims_policy_id", "insurance_claims", ["policy_id"])
        op.create_index("ix_insurance_claims_company_id", "insurance_claims", ["company_id"])

    if not _is_postgres():
        return

    # --- Row Level Security real (solo PostgreSQL) ---

    op.execute("ALTER TABLE insurance_policies ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_insurance_policies ON insurance_policies
        USING (
            company_id::text = NULLIF(current_setting('app.current_company_id', true), '')
        )
        """
    )

    op.execute("ALTER TABLE insurance_claims ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_insurance_claims ON insurance_claims
        USING (
            company_id::text = NULLIF(current_setting('app.current_company_id', true), '')
        )
        """
    )

    # --- Rol de aplicación zeus_app: sin SUPERUSER, sin BYPASSRLS ---
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'zeus_app') THEN
                CREATE ROLE zeus_app NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOINHERIT LOGIN;
            END IF;
        EXCEPTION WHEN insufficient_privilege THEN
            RAISE NOTICE 'No se pudo crear el rol zeus_app (privilegios insuficientes) — crearlo manualmente fuera de esta migración';
        END
        $$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            EXECUTE format('GRANT CONNECT ON DATABASE %I TO zeus_app', current_database());
            GRANT USAGE ON SCHEMA public TO zeus_app;
            GRANT SELECT, INSERT, UPDATE, DELETE ON insurance_policies TO zeus_app;
            GRANT SELECT, INSERT, UPDATE, DELETE ON insurance_claims TO zeus_app;
        EXCEPTION WHEN insufficient_privilege OR undefined_object THEN
            RAISE NOTICE 'No se pudo completar el GRANT a zeus_app — revisar manualmente';
        END
        $$;
        """
    )

    op.execute(
        """
        DO $$
        DECLARE seq text;
        BEGIN
            seq := pg_get_serial_sequence('insurance_policies', 'id');
            IF seq IS NOT NULL THEN
                EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE %s TO zeus_app', seq);
            END IF;
            seq := pg_get_serial_sequence('insurance_claims', 'id');
            IF seq IS NOT NULL THEN
                EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE %s TO zeus_app', seq);
            END IF;
        EXCEPTION WHEN insufficient_privilege OR undefined_object THEN
            RAISE NOTICE 'No se pudo completar el GRANT de secuencias a zeus_app — revisar manualmente';
        END
        $$;
        """
    )


def downgrade() -> None:
    if _is_postgres():
        op.execute("DROP POLICY IF EXISTS tenant_isolation_insurance_claims ON insurance_claims")
        op.execute("ALTER TABLE insurance_claims DISABLE ROW LEVEL SECURITY")
        op.execute("DROP POLICY IF EXISTS tenant_isolation_insurance_policies ON insurance_policies")
        op.execute("ALTER TABLE insurance_policies DISABLE ROW LEVEL SECURITY")
        # No se revoca ni elimina el rol zeus_app en downgrade: puede estar en uso
        # por otras tablas/migraciones. Revocar accesos puntuales basta.
        op.execute(
            """
            DO $$
            BEGIN
                REVOKE ALL ON insurance_policies FROM zeus_app;
                REVOKE ALL ON insurance_claims FROM zeus_app;
            EXCEPTION WHEN insufficient_privilege OR undefined_object THEN
                NULL;
            END
            $$;
            """
        )

    op.drop_table("insurance_claims")
    op.drop_table("insurance_policies")

    if _is_postgres():
        op.execute("DROP TYPE IF EXISTS insurance_claim_status")
        op.execute("DROP TYPE IF EXISTS insurance_policy_status")
