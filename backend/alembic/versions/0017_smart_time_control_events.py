"""Smart time control: eventos, alertas, extra_hours.

Revision ID: 0017
Revises: 0016
Create Date: 2026-04-30

"""
from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "time_tracking_records",
        sa.Column("extra_hours", sa.Float(), nullable=True),
    )
    op.create_table(
        "time_control_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("employee_id", sa.String(100), nullable=False, index=True),
        sa.Column("record_id", sa.Integer(), sa.ForeignKey("time_tracking_records.id"), nullable=True, index=True),
        sa.Column("event_type", sa.String(32), nullable=False, index=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("device", sa.String(512), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_table(
        "time_control_alerts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("employee_id", sa.String(100), nullable=True, index=True),
        sa.Column("alert_kind", sa.String(64), nullable=False, index=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="warning"),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("notify_targets", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("time_control_alerts")
    op.drop_table("time_control_events")
    op.drop_column("time_tracking_records", "extra_hours")
