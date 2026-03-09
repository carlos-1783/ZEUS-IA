"""Add user.role (owner|employee) for employee-only TPV + control horario

Revision ID: 0006
Revises: 0005
Create Date: 2026-01-23

"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=20), nullable=False, server_default=sa.text("'owner'")),
    )


def downgrade() -> None:
    op.drop_column("users", "role")
