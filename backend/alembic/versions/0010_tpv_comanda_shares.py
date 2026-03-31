"""TPV comanda share snapshots for employee comandero link

Revision ID: 0010
Revises: 0009
Create Date: 2026-03-31

"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tpv_comanda_shares",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_tpv_comanda_shares_owner_user_id", "tpv_comanda_shares", ["owner_user_id"])


def downgrade() -> None:
    op.drop_index("ix_tpv_comanda_shares_owner_user_id", table_name="tpv_comanda_shares")
    op.drop_table("tpv_comanda_shares")
