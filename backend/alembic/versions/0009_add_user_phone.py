"""Add phone column to users (registro)

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-27

"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone", sa.String(32), nullable=True))
    op.create_index("ix_users_phone", "users", ["phone"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_users_phone", table_name="users")
    op.drop_column("users", "phone")
