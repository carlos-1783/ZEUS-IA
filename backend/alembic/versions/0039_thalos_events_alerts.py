"""thalos_events + thalos_alerts — THALOS force real mode

Revision ID: 0039
Revises: 0038
"""
from alembic import op
import sqlalchemy as sa

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    insp = inspect(bind)
    tables = insp.get_table_names()

    if "thalos_events" not in tables:
        op.create_table(
            "thalos_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("event_type", sa.String(64), nullable=False),
            sa.Column("severity", sa.String(16), nullable=False, server_default="info"),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("source", sa.String(128), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_thalos_events_event_type", "thalos_events", ["event_type"])
        op.create_index("ix_thalos_events_severity", "thalos_events", ["severity"])
        op.create_index("ix_thalos_events_created_at", "thalos_events", ["created_at"])

    if "thalos_alerts" not in tables:
        op.create_table(
            "thalos_alerts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("event_id", sa.Integer(), sa.ForeignKey("thalos_events.id", ondelete="CASCADE"), nullable=True),
            sa.Column("level", sa.String(16), nullable=False, server_default="medium"),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("rule_id", sa.String(64), nullable=True),
            sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_thalos_alerts_event_id", "thalos_alerts", ["event_id"])
        op.create_index("ix_thalos_alerts_level", "thalos_alerts", ["level"])
        op.create_index("ix_thalos_alerts_resolved", "thalos_alerts", ["resolved"])


def downgrade() -> None:
    op.drop_index("ix_thalos_alerts_resolved", table_name="thalos_alerts")
    op.drop_index("ix_thalos_alerts_level", table_name="thalos_alerts")
    op.drop_index("ix_thalos_alerts_event_id", table_name="thalos_alerts")
    op.drop_table("thalos_alerts")
    op.drop_index("ix_thalos_events_created_at", table_name="thalos_events")
    op.drop_index("ix_thalos_events_severity", table_name="thalos_events")
    op.drop_index("ix_thalos_events_event_type", table_name="thalos_events")
    op.drop_table("thalos_events")
