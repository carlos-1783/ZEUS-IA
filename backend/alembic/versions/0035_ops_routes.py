"""ops_routes — AFRODITA OPS route persistence

Revision ID: 0035
Revises: 0034
"""
from alembic import op
import sqlalchemy as sa

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    if "ops_routes" in inspect(bind).get_table_names():
        return

    op.create_table(
        "ops_routes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("origin", sa.String(255), nullable=False),
        sa.Column("destination", sa.String(255), nullable=False),
        sa.Column("distance", sa.Float(), nullable=False, server_default="0"),
        sa.Column("route_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ops_routes_user_id", "ops_routes", ["user_id"])
    op.create_index("ix_ops_routes_company_id", "ops_routes", ["company_id"])


def downgrade() -> None:
    op.drop_index("ix_ops_routes_company_id", table_name="ops_routes")
    op.drop_index("ix_ops_routes_user_id", table_name="ops_routes")
    op.drop_table("ops_routes")
