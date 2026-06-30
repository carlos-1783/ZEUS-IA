"""teamflow_items + teamflow_events — full system audit

Revision ID: 0041
Revises: 0040
"""
from alembic import op
import sqlalchemy as sa

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    insp = inspect(bind)
    tables = insp.get_table_names()

    if "teamflow_items" not in tables:
        op.create_table(
            "teamflow_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("public_id", sa.String(36), nullable=False, unique=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True),
            sa.Column("owner_agent", sa.String(64), nullable=False),
            sa.Column("source_agent", sa.String(64), nullable=True),
            sa.Column("target_agent", sa.String(64), nullable=True),
            sa.Column("workflow_id", sa.String(128), nullable=True),
            sa.Column("item_type", sa.String(64), nullable=False, server_default="flow"),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("content_json", sa.Text(), nullable=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
            sa.Column("execution_id", sa.String(36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_teamflow_items_owner_agent", "teamflow_items", ["owner_agent"])
        op.create_index("ix_teamflow_items_status", "teamflow_items", ["status"])

    if "teamflow_events" not in tables:
        op.create_table(
            "teamflow_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("public_id", sa.String(36), nullable=False, unique=True),
            sa.Column("item_id", sa.Integer(), sa.ForeignKey("teamflow_items.id", ondelete="CASCADE"), nullable=False),
            sa.Column("event_type", sa.String(64), nullable=False),
            sa.Column("owner_agent", sa.String(64), nullable=False),
            sa.Column("from_status", sa.String(32), nullable=True),
            sa.Column("to_status", sa.String(32), nullable=True),
            sa.Column("details_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_teamflow_events_item_id", "teamflow_events", ["item_id"])


def downgrade() -> None:
    op.drop_index("ix_teamflow_events_item_id", table_name="teamflow_events")
    op.drop_table("teamflow_events")
    op.drop_index("ix_teamflow_items_status", table_name="teamflow_items")
    op.drop_index("ix_teamflow_items_owner_agent", table_name="teamflow_items")
    op.drop_table("teamflow_items")
