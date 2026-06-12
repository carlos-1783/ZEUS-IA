"""ZEUS time cost engine v1: checkins, hourly_rate, session cost

Revision ID: 0026
Revises: 0025
"""
from alembic import op
import sqlalchemy as sa

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    insp = inspect(bind)
    tables = set(insp.get_table_names())

    if "company_employees" in tables:
        cols = {c["name"] for c in insp.get_columns("company_employees")}
        if "hourly_rate" not in cols:
            op.add_column(
                "company_employees",
                sa.Column("hourly_rate", sa.Float(), nullable=True, server_default="0"),
            )

    if "employee_work_sessions" in tables:
        cols = {c["name"] for c in insp.get_columns("employee_work_sessions")}
        for name, col in (
            ("total_hours", sa.Column("total_hours", sa.Float(), nullable=True)),
            ("total_cost", sa.Column("total_cost", sa.Float(), nullable=True)),
            ("partial_cost", sa.Column("partial_cost", sa.Float(), nullable=True)),
            ("pause_minutes", sa.Column("pause_minutes", sa.Float(), nullable=True, server_default="0")),
        ):
            if name not in cols:
                op.add_column("employee_work_sessions", col)

    if "time_cost_checkins" not in tables:
        op.create_table(
            "time_cost_checkins",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("employee_id", sa.String(100), nullable=False),
            sa.Column("company_employee_id", sa.Integer(), sa.ForeignKey("company_employees.id", ondelete="SET NULL"), nullable=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("type", sa.String(32), nullable=False),
            sa.Column("method", sa.String(32), nullable=False),
            sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
            sa.Column("time_tracking_record_id", sa.Integer(), sa.ForeignKey("time_tracking_records.id", ondelete="SET NULL"), nullable=True),
            sa.Column("work_session_id", sa.Integer(), sa.ForeignKey("employee_work_sessions.id", ondelete="SET NULL"), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("client_ip", sa.String(64), nullable=True),
            sa.Column("device_id", sa.String(128), nullable=True),
            sa.Column("user_agent", sa.String(512), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_time_cost_checkins_company_id", "time_cost_checkins", ["company_id"])
        op.create_index("ix_time_cost_checkins_employee_id", "time_cost_checkins", ["employee_id"])
        op.create_index("ix_time_cost_checkins_timestamp", "time_cost_checkins", ["timestamp"])


def downgrade() -> None:
    op.drop_table("time_cost_checkins")
    for table, col in (
        ("employee_work_sessions", "pause_minutes"),
        ("employee_work_sessions", "partial_cost"),
        ("employee_work_sessions", "total_cost"),
        ("employee_work_sessions", "total_hours"),
        ("company_employees", "hourly_rate"),
    ):
        try:
            op.drop_column(table, col)
        except Exception:
            pass
