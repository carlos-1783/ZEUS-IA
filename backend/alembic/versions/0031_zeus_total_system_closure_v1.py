"""zeus_closure_audits + reglas DB inmutables — zeus_total_system_closure_v1

Revision ID: 0031
Revises: 0030
"""
from alembic import op
import sqlalchemy as sa

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    insp = inspect(bind)
    tables = insp.get_table_names()

    if "zeus_closure_audits" not in tables:
        op.create_table(
            "zeus_closure_audits",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("layer", sa.String(32), nullable=False),
            sa.Column("domain", sa.String(32), nullable=False),
            sa.Column("action", sa.String(64), nullable=False),
            sa.Column("actor_id", sa.String(64), nullable=True),
            sa.Column("actor_email", sa.String(255), nullable=True),
            sa.Column("target_id", sa.String(64), nullable=True),
            sa.Column("company_id", sa.Integer(), nullable=True),
            sa.Column("result", sa.String(32), nullable=False),
            sa.Column("execution_mode", sa.String(16), nullable=False, server_default="real"),
            sa.Column("human_message", sa.String(500), nullable=True),
            sa.Column("details_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_zeus_closure_audits_layer", "zeus_closure_audits", ["layer"])
        op.create_index("ix_zeus_closure_audits_domain", "zeus_closure_audits", ["domain"])
        op.create_index("ix_zeus_closure_audits_action", "zeus_closure_audits", ["action"])
        op.create_index("ix_zeus_closure_audits_company_id", "zeus_closure_audits", ["company_id"])

    dialect = bind.dialect.name
    if dialect == "postgresql":
        op.execute(
            """
            CREATE OR REPLACE FUNCTION zeus_prevent_superuser_deactivate()
            RETURNS TRIGGER AS $$
            BEGIN
              IF NEW.is_active = false AND (OLD.is_superuser = true OR OLD.role = 'superuser') THEN
                RAISE EXCEPTION 'zeus_guard: cannot deactivate superuser';
              END IF;
              RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute("DROP TRIGGER IF EXISTS trg_zeus_superuser_deactivate ON users;")
        op.execute(
            """
            CREATE TRIGGER trg_zeus_superuser_deactivate
            BEFORE UPDATE OF is_active ON users
            FOR EACH ROW EXECUTE PROCEDURE zeus_prevent_superuser_deactivate();
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_zeus_superuser_deactivate ON users;")
        op.execute("DROP FUNCTION IF EXISTS zeus_prevent_superuser_deactivate();")

    op.drop_index("ix_zeus_closure_audits_company_id", table_name="zeus_closure_audits")
    op.drop_index("ix_zeus_closure_audits_action", table_name="zeus_closure_audits")
    op.drop_index("ix_zeus_closure_audits_domain", table_name="zeus_closure_audits")
    op.drop_index("ix_zeus_closure_audits_layer", table_name="zeus_closure_audits")
    op.drop_table("zeus_closure_audits")
