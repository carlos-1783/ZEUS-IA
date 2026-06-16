"""scan_events table — zeus_full_real_flow_v3

Revision ID: 0029
Revises: 0028
"""
from alembic import op
import sqlalchemy as sa

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    insp = inspect(bind)
    if "scan_events" in insp.get_table_names():
        return

    op.create_table(
        "scan_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("scan_type", sa.String(16), nullable=False),
        sa.Column("agent_name", sa.String(32), nullable=True),
        sa.Column("raw_payload", sa.Text(), nullable=False),
        sa.Column("parsed_json", sa.Text(), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_scan_events_company_id", "scan_events", ["company_id"])
    op.create_index("ix_scan_events_scan_type", "scan_events", ["scan_type"])


def downgrade() -> None:
    op.drop_index("ix_scan_events_scan_type", table_name="scan_events")
    op.drop_index("ix_scan_events_company_id", table_name="scan_events")
    op.drop_table("scan_events")
