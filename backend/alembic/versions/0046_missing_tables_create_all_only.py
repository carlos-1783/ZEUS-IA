"""Migraciones reales para tablas que solo existían vía Base.metadata.create_all()

Hallazgo de la auditoría feature/auditoria-real-nucleo (capa BD): 10 tablas
dependían por completo de create_all() en cada arranque (app/db/base.py),
sin ningún historial de Alembic — "no es un descuido silencioso: el propio
código lo documenta como deuda técnica". agent_activities ya se resolvió en
la migración 0043 (necesitaba además la columna company_id nueva). Esta
migración cubre las 9 restantes: agent_operational_state, agent_decision_log,
agent_short_term_buffer, automation_readiness, payroll_drafts, zeus_events,
zeus_alerts, zeus_automations, zeus_automation_logs.

Mismo patrón que 0042/0043: crea la tabla solo si no existe ya (instalaciones
reales, como la actual, ya la tienen vía create_all — esta migración no les
hace nada, solo dejarlas "bajo control de versiones real" a partir de ahora;
en Postgres/SQLite genuinamente limpios, sí las crea).

payroll_drafts y automation_readiness se crean aquí ya con los nombres de
columna corregidos por la migración 0045 (owner_user_id / user_id) — no
tendría sentido crearlas con el nombre engañoso viejo solo para renombrarlas
en el mismo `alembic upgrade head`.

Revision ID: 0046
Revises: 0045
"""
from alembic import op
import sqlalchemy as sa

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    existing = set(inspect(bind).get_table_names())

    if "agent_operational_state" not in existing:
        op.create_table(
            "agent_operational_state",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.String(64), nullable=False, server_default="default"),
            sa.Column("agent_id", sa.String(64), nullable=False),
            sa.Column("thread_id", sa.String(128), nullable=False),
            sa.Column("current_task", sa.Text(), nullable=True),
            sa.Column("status", sa.String(32), nullable=True),
            sa.Column("next_action", sa.Text(), nullable=True),
            sa.Column("artifacts", sa.JSON(), nullable=True),
            sa.Column("blocked", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_agent_operational_state_company_id", "agent_operational_state", ["company_id"])
        op.create_index("ix_agent_operational_state_agent_id", "agent_operational_state", ["agent_id"])
        op.create_index("ix_agent_operational_state_thread_id", "agent_operational_state", ["thread_id"])

    if "agent_decision_log" not in existing:
        op.create_table(
            "agent_decision_log",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.String(64), nullable=False, server_default="default"),
            sa.Column("agent_id", sa.String(64), nullable=False),
            sa.Column("thread_id", sa.String(128), nullable=False),
            sa.Column("decision_type", sa.String(64), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_agent_decision_log_company_id", "agent_decision_log", ["company_id"])
        op.create_index("ix_agent_decision_log_agent_id", "agent_decision_log", ["agent_id"])
        op.create_index("ix_agent_decision_log_thread_id", "agent_decision_log", ["thread_id"])

    if "agent_short_term_buffer" not in existing:
        op.create_table(
            "agent_short_term_buffer",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.String(64), nullable=False, server_default="default"),
            sa.Column("agent_id", sa.String(64), nullable=False),
            sa.Column("thread_id", sa.String(128), nullable=False),
            sa.Column("messages", sa.JSON(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_agent_short_term_buffer_company_id", "agent_short_term_buffer", ["company_id"])
        op.create_index("ix_agent_short_term_buffer_agent_id", "agent_short_term_buffer", ["agent_id"])
        op.create_index("ix_agent_short_term_buffer_thread_id", "agent_short_term_buffer", ["thread_id"])

    if "automation_readiness" not in existing:
        op.create_table(
            "automation_readiness",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("leads_last_30_days", sa.Integer(), server_default="0"),
            sa.Column("avg_response_time_hours", sa.Float(), server_default="0"),
            sa.Column("active_channels", sa.Integer(), server_default="0"),
            sa.Column("monthly_revenue_estimate", sa.Float(), server_default="0"),
            sa.Column("has_defined_offer", sa.Boolean(), server_default=sa.false()),
            sa.Column("has_sales_process", sa.Boolean(), server_default=sa.false()),
            sa.Column("team_size", sa.Integer(), server_default="0"),
            sa.Column("score", sa.Integer(), server_default="0"),
            sa.Column("status", sa.String(50), nullable=True),
            sa.Column("evaluated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_automation_readiness_user_id", "automation_readiness", ["user_id"])

    if "payroll_drafts" not in existing:
        op.create_table(
            "payroll_drafts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("employee_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("gross_salary", sa.Float(), nullable=False),
            sa.Column("irpf_estimated", sa.Float(), server_default="0"),
            sa.Column("social_security_estimated", sa.Float(), server_default="0"),
            sa.Column("net_salary_estimated", sa.Float(), server_default="0"),
            sa.Column("month", sa.String(20), nullable=True),
            sa.Column("year", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(50), nullable=False, server_default="BORRADOR_GENERADO"),
            sa.Column("pdf_path", sa.String(500), nullable=True),
            sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_payroll_drafts_owner_user_id", "payroll_drafts", ["owner_user_id"])
        op.create_index("ix_payroll_drafts_employee_id", "payroll_drafts", ["employee_id"])

    if "zeus_events" not in existing:
        op.create_table(
            "zeus_events",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("type", sa.String(64), nullable=False),
            sa.Column("agent", sa.String(64), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="success"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_zeus_events_user_id", "zeus_events", ["user_id"])
        op.create_index("ix_zeus_events_type", "zeus_events", ["type"])
        op.create_index("ix_zeus_events_agent", "zeus_events", ["agent"])
        op.create_index("ix_zeus_events_status", "zeus_events", ["status"])
        op.create_index("ix_zeus_events_created_at", "zeus_events", ["created_at"])

    if "zeus_alerts" not in existing:
        op.create_table(
            "zeus_alerts",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("level", sa.String(16), nullable=False, server_default="medium"),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_zeus_alerts_user_id", "zeus_alerts", ["user_id"])
        op.create_index("ix_zeus_alerts_level", "zeus_alerts", ["level"])
        op.create_index("ix_zeus_alerts_resolved", "zeus_alerts", ["resolved"])
        op.create_index("ix_zeus_alerts_created_at", "zeus_alerts", ["created_at"])

    if "zeus_automations" not in existing:
        op.create_table(
            "zeus_automations",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("name", sa.String(128), nullable=False, unique=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="active"),
            sa.Column("last_run", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_zeus_automations_name", "zeus_automations", ["name"], unique=True)
        op.create_index("ix_zeus_automations_status", "zeus_automations", ["status"])

    if "zeus_automation_logs" not in existing:
        op.create_table(
            "zeus_automation_logs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("automation_name", sa.String(128), nullable=False),
            sa.Column("agent", sa.String(64), nullable=False, server_default="unknown"),
            sa.Column("trigger_type", sa.String(32), nullable=False, server_default="manual"),
            sa.Column("status", sa.String(32), nullable=False, server_default="unknown"),
            sa.Column("input_data", sa.JSON(), nullable=True),
            sa.Column("output_data", sa.JSON(), nullable=True),
            sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_zeus_automation_logs_user_id", "zeus_automation_logs", ["user_id"])
        op.create_index("ix_zeus_automation_logs_automation_name", "zeus_automation_logs", ["automation_name"])
        op.create_index("ix_zeus_automation_logs_agent", "zeus_automation_logs", ["agent"])
        op.create_index("ix_zeus_automation_logs_trigger_type", "zeus_automation_logs", ["trigger_type"])
        op.create_index("ix_zeus_automation_logs_status", "zeus_automation_logs", ["status"])
        op.create_index("ix_zeus_automation_logs_executed_at", "zeus_automation_logs", ["executed_at"])


def downgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    existing = set(inspect(bind).get_table_names())

    for table in (
        "zeus_automation_logs",
        "zeus_automations",
        "zeus_alerts",
        "zeus_events",
        "payroll_drafts",
        "automation_readiness",
        "agent_short_term_buffer",
        "agent_decision_log",
        "agent_operational_state",
    ):
        if table in existing:
            op.drop_table(table)
