"""Migrar a Alembic real las columnas de `users` que solo creaba
ensure_schema_patches() en caliente (app/db/base.py::_migrate_user_columns).

Hallazgo AUDIT_STAGING_POSTGRES_REAL.md (sección 3 / 9.5, confirmado por
revisor-independiente): estas 13 columnas nunca tuvieron una migración
Alembic real — solo existían si el mecanismo de "parches idempotentes de
arranque" lograba ejecutar su `ALTER TABLE` con éxito. Bajo un rol de
runtime sin privilegios de dueño de tabla (`zeus_app`, el rol recomendado
para producción tras `dec54c0`), ese `ALTER TABLE` falla con
`InsufficientPrivilege: must be owner of table users` y las columnas nunca
se crean — incluso en una base de datos NUEVA migrada solo con
`alembic upgrade head`. Confirmado en vivo: tras un `alembic upgrade head`
limpio (antes de esta migración), `users` no tenía ninguna de estas 13
columnas.

Barrido completo de `ensure_schema_patches()` (`app/db/base.py`, todas las
funciones `_migrate_*`) confirmando qué falta y qué ya tiene migración real:
todo lo demás (`document_approvals` vía 0003/0015/0016/0025, `expenses` vía
0025, `tpv_products`/`tpv_sales`/`invoices.company_id` vía 0012,
`companies.company_type` vía 0022, `company_employees.tpv_pin_hash` vía
0019, `time_tracking_records.extra_hours` + `time_control_events`/
`time_control_alerts` vía 0017, `company_employees.hourly_rate` +
`employee_work_sessions.*` + `time_cost_checkins` vía 0026,
`cashflow_ledger` vía 0027, `agent_activities.company_id` vía 0043,
`zeus_events`/`zeus_alerts`/`zeus_automations`/`zeus_automation_logs` vía
0046, `zeus_domain_events` vía 0042, constraints de rol vía 0044, renombrado
de columnas vía 0045, `companies.tax_id`/`legal_name`/`iban_encrypted` vía
0051, `invoices.tpv_sale_id` vía 0050) ya tiene migración real y no
necesita nada nuevo aquí. Las 13 columnas de esta migración son el ÚNICO
hueco real encontrado en el barrido.

Tipos/nullable/índices tomados literalmente de `app/models/user.py` (única
fuente de verdad del ORM) para que el resultado sea idéntico al que produce
`Base.metadata.create_all()` en una base nueva.

Revision ID: 0056
Revises: 0055
Create Date: 2026-09-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None


# (nombre, tipo, index)
_COLUMNS = [
    ("email_gestor_fiscal", sa.String(), False),
    ("email_gestor_laboral", sa.String(), False),
    ("email_asesor_legal", sa.String(), False),
    ("autoriza_envio_documentos_a_asesores", sa.Boolean(), False),
    ("company_name", sa.String(), False),
    ("employees", sa.Integer(), False),
    ("plan", sa.String(), False),
    ("stripe_customer_id", sa.String(), True),
    ("stripe_subscription_id", sa.String(), False),
    ("tpv_business_profile", sa.String(), True),
    ("tpv_config", sa.Text(), False),
    ("control_horario_business_profile", sa.String(), True),
    ("control_horario_config", sa.Text(), False),
]


def _existing_columns(bind) -> set:
    insp = sa.inspect(bind)
    if not insp.has_table("users"):
        return set()
    return {c["name"] for c in insp.get_columns("users")}


def upgrade() -> None:
    bind = op.get_bind()
    cols = _existing_columns(bind)
    if not cols:
        return

    for name, col_type, indexed in _COLUMNS:
        if name in cols:
            continue
        default = sa.false() if name == "autoriza_envio_documentos_a_asesores" else None
        op.add_column(
            "users",
            sa.Column(name, col_type, nullable=True, server_default=default),
        )
        if indexed:
            op.create_index(op.f(f"ix_users_{name}"), "users", [name], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    cols = _existing_columns(bind)
    if not cols:
        return

    for name, _col_type, indexed in reversed(_COLUMNS):
        if name not in cols:
            continue
        if indexed:
            try:
                op.drop_index(op.f(f"ix_users_{name}"), table_name="users")
            except Exception:
                pass
        op.drop_column("users", name)
