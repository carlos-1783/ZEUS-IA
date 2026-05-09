"""TPV operator switch session + optional PIN on company_employees

Revision ID: 0019
Revises: 0018
Create Date: 2026-05-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "company_employees",
        sa.Column("tpv_pin_hash", sa.String(255), nullable=True),
    )
    op.create_table(
        "tpv_operator_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("employee_code", sa.String(80), nullable=False, index=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("tpv_operator_sessions")
    op.drop_column("company_employees", "tpv_pin_hash")
