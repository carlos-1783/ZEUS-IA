"""thalos_security_events + thalos_login_attempts — thalos_safe_audit_v1

Revision ID: 0030
Revises: 0029
"""
from alembic import op
import sqlalchemy as sa

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    insp = inspect(bind)
    tables = insp.get_table_names()

    if "thalos_security_events" not in tables:
        op.create_table(
            "thalos_security_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("event_type", sa.String(64), nullable=False),
            sa.Column("severity", sa.String(16), nullable=False, server_default="info"),
            sa.Column("source", sa.String(64), nullable=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("user_email", sa.String(255), nullable=True),
            sa.Column("ip_address", sa.String(64), nullable=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True),
            sa.Column("details_json", sa.Text(), nullable=True),
            sa.Column("action_taken", sa.String(128), nullable=True),
            sa.Column("decision_rule", sa.String(128), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_thalos_security_events_event_type", "thalos_security_events", ["event_type"])
        op.create_index("ix_thalos_security_events_severity", "thalos_security_events", ["severity"])
        op.create_index("ix_thalos_security_events_company_id", "thalos_security_events", ["company_id"])

    if "thalos_login_attempts" not in tables:
        op.create_table(
            "thalos_login_attempts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("ip_address", sa.String(64), nullable=True),
            sa.Column("success", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_thalos_login_attempts_email", "thalos_login_attempts", ["email"])
        op.create_index("ix_thalos_login_attempts_ip_address", "thalos_login_attempts", ["ip_address"])


def downgrade() -> None:
    op.drop_index("ix_thalos_login_attempts_ip_address", table_name="thalos_login_attempts")
    op.drop_index("ix_thalos_login_attempts_email", table_name="thalos_login_attempts")
    op.drop_table("thalos_login_attempts")
    op.drop_index("ix_thalos_security_events_company_id", table_name="thalos_security_events")
    op.drop_index("ix_thalos_security_events_severity", table_name="thalos_security_events")
    op.drop_index("ix_thalos_security_events_event_type", table_name="thalos_security_events")
    op.drop_table("thalos_security_events")
