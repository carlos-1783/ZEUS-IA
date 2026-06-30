"""zeus_domain_events — cross-module event bus

Revision ID: 0042
Revises: 0041
"""
from alembic import op
import sqlalchemy as sa

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    if "zeus_domain_events" not in inspect(bind).get_table_names():
        op.create_table(
            "zeus_domain_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("public_id", sa.String(36), nullable=False, unique=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
            sa.Column("event_name", sa.String(64), nullable=False),
            sa.Column("source_module", sa.String(32), nullable=False),
            sa.Column("payload_json", sa.Text(), nullable=True),
            sa.Column("propagated_to", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_zeus_domain_events_event_name", "zeus_domain_events", ["event_name"])


def downgrade() -> None:
    op.drop_index("ix_zeus_domain_events_event_name", table_name="zeus_domain_events")
    op.drop_table("zeus_domain_events")
