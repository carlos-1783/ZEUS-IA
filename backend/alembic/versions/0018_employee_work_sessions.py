"""Employee work sessions + tpv_sales.work_session_id

Revision ID: 0018
Revises: 0017
Create Date: 2026-05-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "employee_work_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("employee_code", sa.String(100), nullable=False, index=True),
        sa.Column("time_tracking_record_id", sa.Integer(), sa.ForeignKey("time_tracking_records.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active", index=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_reason", sa.String(64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index(
        "ix_employee_work_sessions_user_active",
        "employee_work_sessions",
        ["user_id", "status"],
    )
    op.add_column(
        "tpv_sales",
        sa.Column("work_session_id", sa.Integer(), sa.ForeignKey("employee_work_sessions.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_tpv_sales_work_session_id", "tpv_sales", ["work_session_id"])


def downgrade() -> None:
    op.drop_index("ix_tpv_sales_work_session_id", table_name="tpv_sales")
    op.drop_column("tpv_sales", "work_session_id")
    op.drop_index("ix_employee_work_sessions_user_active", table_name="employee_work_sessions")
    op.drop_table("employee_work_sessions")
