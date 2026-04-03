"""TPV tables per company (persistent floor plan)

Revision ID: 0011
Revises: 0010
Create Date: 2026-04-01

"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tpv_tables",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="free"),
        sa.Column("order_total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("cart_snapshot", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("company_id", "number", name="uq_tpv_tables_company_number"),
    )
    op.create_index("ix_tpv_tables_company_id", "tpv_tables", ["company_id"])


def downgrade() -> None:
    op.drop_index("ix_tpv_tables_company_id", table_name="tpv_tables")
    op.drop_table("tpv_tables")
