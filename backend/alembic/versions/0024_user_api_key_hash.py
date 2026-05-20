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
    op.add_column("user_settings", sa.Column("api_key_hash", sa.String(64), nullable=True))
    op.add_column("user_settings", sa.Column("api_key_prefix", sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column("user_settings", "api_key_prefix")
    op.drop_column("user_settings", "api_key_hash")
