"""zeus_transactions orchestration table

Revision ID: 0037
Revises: 0036
"""
from alembic import op
import sqlalchemy as sa

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    if "zeus_transactions" in inspect(bind).get_table_names():
        return
    op.create_table(
        "zeus_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("transaction_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("execution_mode_at_start", sa.String(32), nullable=True),
        sa.Column("initiator_json", sa.Text(), nullable=True),
        sa.Column("context_json", sa.Text(), nullable=True),
        sa.Column("modules_involved_json", sa.Text(), nullable=True),
        sa.Column("steps_json", sa.Text(), nullable=True),
        sa.Column("locks_json", sa.Text(), nullable=True),
        sa.Column("validation_json", sa.Text(), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("errors_json", sa.Text(), nullable=True),
        sa.Column("metrics_json", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_zeus_transactions_transaction_id", "zeus_transactions", ["transaction_id"], unique=True)
    op.create_index("ix_zeus_transactions_status", "zeus_transactions", ["status"])
    op.create_index("ix_zeus_transactions_idempotency_key", "zeus_transactions", ["idempotency_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_zeus_transactions_idempotency_key", table_name="zeus_transactions")
    op.drop_index("ix_zeus_transactions_status", table_name="zeus_transactions")
    op.drop_index("ix_zeus_transactions_transaction_id", table_name="zeus_transactions")
    op.drop_table("zeus_transactions")
