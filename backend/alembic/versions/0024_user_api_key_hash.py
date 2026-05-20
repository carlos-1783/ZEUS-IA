"""api_key_hash en user_settings para claves API personales

Revision ID: 0024
Revises: 0023
"""
from alembic import op
import sqlalchemy as sa

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    insp = inspect(bind)
    if "user_settings" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("user_settings")}
    if "api_key_hash" not in cols:
        op.add_column("user_settings", sa.Column("api_key_hash", sa.String(64), nullable=True))
    if "api_key_prefix" not in cols:
        op.add_column("user_settings", sa.Column("api_key_prefix", sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column("user_settings", "api_key_prefix")
    op.drop_column("user_settings", "api_key_hash")
