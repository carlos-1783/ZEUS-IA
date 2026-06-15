"""Cashflow ledger table

Revision ID: 0027
Revises: 0026
"""
from alembic import op
import sqlalchemy as sa

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    insp = inspect(bind)
    if "cashflow_ledger" in insp.get_table_names():
        return
    op.create_table(
        "cashflow_ledger",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("invoice_id", sa.Integer(), nullable=True),
        sa.Column("tpv_sale_id", sa.Integer(), nullable=True),
        sa.Column("ticket_id", sa.String(128), nullable=True),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("direction", sa.String(8), nullable=False, server_default="in"),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("payment_method", sa.String(64), nullable=True),
        sa.Column("reference", sa.String(255), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_cashflow_ledger_company_id", "cashflow_ledger", ["company_id"])
    op.create_index("ix_cashflow_ledger_created_at", "cashflow_ledger", ["created_at"])
    op.create_index("ix_cashflow_ledger_source", "cashflow_ledger", ["source"])


def downgrade() -> None:
    op.drop_table("cashflow_ledger")
