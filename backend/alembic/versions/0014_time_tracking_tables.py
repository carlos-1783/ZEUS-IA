"""Crear tablas control horario: time_tracking_records, employee_schedules, attendance_reports

Revision ID: 0014
Revises: 0013
Create Date: 2026-04-06

"""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "time_tracking_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("employee_id", sa.String(100), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True, index=True),
        sa.Column("check_in_time", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("check_out_time", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("check_in_method", sa.String(20), nullable=False, server_default="qr"),
        sa.Column("check_out_method", sa.String(20), nullable=True),
        sa.Column("check_in_location", sa.String(255), nullable=True),
        sa.Column("check_out_location", sa.String(255), nullable=True),
        sa.Column("check_in_latitude", sa.Float(), nullable=True),
        sa.Column("check_in_longitude", sa.Float(), nullable=True),
        sa.Column("check_out_latitude", sa.Float(), nullable=True),
        sa.Column("check_out_longitude", sa.Float(), nullable=True),
        sa.Column("hours_worked", sa.Float(), nullable=True),
        sa.Column("break_duration", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(30), nullable=False, server_default="active", index=True),
        sa.Column("irregularities", sa.JSON(), nullable=True),
        sa.Column("irregularities_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_late_check_in", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_early_check_out", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_missing_break", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("synced_with_afrodita", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("synced_with_rafael", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("afrodita_sync_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rafael_sync_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "employee_schedules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("employee_id", sa.String(100), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True, index=True),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.String(10), nullable=False),
        sa.Column("end_time", sa.String(10), nullable=False),
        sa.Column("shift_type", sa.String(50), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("break_start", sa.String(10), nullable=True),
        sa.Column("break_duration", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("is_flexible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true(), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "attendance_reports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("employee_id", sa.String(100), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True, index=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("period_type", sa.String(20), nullable=False),
        sa.Column("total_hours", sa.Float(), nullable=False, server_default="0"),
        sa.Column("expected_hours", sa.Float(), nullable=False, server_default="0"),
        sa.Column("hours_difference", sa.Float(), nullable=False, server_default="0"),
        sa.Column("check_ins_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("check_outs_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("late_check_ins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("early_check_outs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("missing_breaks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("absences", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_locked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("attendance_reports")
    op.drop_table("employee_schedules")
    op.drop_table("time_tracking_records")
