"""agent_activities: crear tabla si no existe (con company_id) o añadir company_id

Hasta ahora agent_activities dependía por completo de Base.metadata.create_all()
(app/db/base.py:create_tables()), sin ninguna migración Alembic — confirmado en
la auditoría feature/auditoria-real-nucleo, capa 1. Esta migración la deja bajo
control de versiones real y añade el aislamiento multi-tenant que faltaba
(GET /api/v1/metrics/dashboard consultaba AgentActivity de todos los tenants).

Revision ID: 0043
Revises: 0042
"""
from alembic import op
import sqlalchemy as sa

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    inspector = inspect(bind)

    if "agent_activities" not in inspector.get_table_names():
        # Entorno sin create_all() previo (p. ej. Postgres limpio corriendo
        # solo `alembic upgrade head`): crear la tabla completa tal como la
        # define el modelo actual, con company_id ya incluida.
        op.create_table(
            "agent_activities",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True),
            sa.Column("agent_name", sa.String(), nullable=False),
            sa.Column("action_type", sa.String(), nullable=False),
            sa.Column("action_description", sa.Text(), nullable=False),
            sa.Column("details", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(), server_default="completed", nullable=True),
            sa.Column("metrics", sa.JSON(), nullable=True),
            sa.Column("user_email", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("priority", sa.String(), server_default="normal", nullable=True),
            sa.Column("visible_to_client", sa.Boolean(), server_default=sa.true(), nullable=True),
        )
        op.create_index("ix_agent_activities_company_id", "agent_activities", ["company_id"])
        op.create_index("ix_agent_activities_agent_name", "agent_activities", ["agent_name"])
        op.create_index("ix_agent_activities_action_type", "agent_activities", ["action_type"])
        op.create_index("ix_agent_activities_user_email", "agent_activities", ["user_email"])
        return

    # Tabla ya creada vía create_all() en instalaciones existentes (local,
    # Railway actual): solo añadir la columna si todavía no existe.
    cols = {c["name"] for c in inspector.get_columns("agent_activities")}
    if "company_id" not in cols:
        op.add_column(
            "agent_activities",
            sa.Column("company_id", sa.Integer(), nullable=True),
        )
        op.create_index(
            "ix_agent_activities_company_id", "agent_activities", ["company_id"], unique=False
        )
        # SQLite no soporta ADD CONSTRAINT fuera de modo batch; Postgres (producción)
        # sí. Aplicar la FK solo en dialectos que la soportan de verdad — en
        # SQLite la relación queda garantizada a nivel de aplicación (ORM) igual
        # que el resto de columnas *_id nullable de este proyecto.
        if bind.dialect.name != "sqlite":
            op.create_foreign_key(
                "fk_agent_activities_company_id",
                "agent_activities",
                "companies",
                ["company_id"],
                ["id"],
                ondelete="SET NULL",
            )

    # Backfill best-effort: para filas existentes con user_email pero sin
    # company_id, resolver la empresa principal del usuario vía user_companies.
    connection = op.get_bind()
    connection.execute(
        sa.text(
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


def downgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    inspector = inspect(bind)
    if "agent_activities" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("agent_activities")}
    if "company_id" in cols:
        op.drop_index("ix_agent_activities_company_id", table_name="agent_activities")
        # batch_alter_table: en SQLite el FK puede haber quedado embebido en el
        # CREATE TABLE original (rama sin create_all previo, arriba), por lo que
        # un DROP COLUMN directo falla ("unknown column in foreign key
        # definition") aunque la propia FK nunca se creara con ALTER. El modo
        # batch recrea la tabla sin esa columna/constraint y es un no-op
        # equivalente a un ALTER directo en Postgres.
        with op.batch_alter_table("agent_activities") as batch_op:
            if bind.dialect.name != "sqlite":
                batch_op.drop_constraint("fk_agent_activities_company_id", type_="foreignkey")
            batch_op.drop_column("company_id")
