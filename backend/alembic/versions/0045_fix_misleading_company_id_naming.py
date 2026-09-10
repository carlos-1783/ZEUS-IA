"""payroll_drafts.company_id -> owner_user_id, automation_readiness.company_id -> user_id

Hallazgo de la auditoría feature/auditoria-real-nucleo (capa BD): ambas
columnas se llamaban "company_id" pero su ForeignKey siempre apuntó a
users.id, nunca a companies.id — naming engañoso que sugiere aislamiento
multi-empresa real donde en realidad el alcance es por usuario individual
(diseño previo al modelo Company/UserCompany). Confirmado leyendo los
callers reales:
- services/payroll_assistant_service.py y
  services/automation/handlers/zeus_payroll_draft.py: resuelven el valor con
  `user.id`, consultan la tabla `users`, nunca `companies`.
- services/automation/handlers/zeus_automation_readiness.py ya documentaba
  esto en su propio comentario: "Resolver company_id (user_id)".

No se cambia el modelo de negocio (sigue siendo un FK a users.id) — solo se
corrige el nombre para que dañe de verdad lo que representa. Se usa
batch_alter_table para renombrar de forma segura en SQLite (recrea la tabla)
y Postgres (ALTER TABLE ... RENAME COLUMN normal).

Revision ID: 0045
Revises: 0044
"""
from alembic import op

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    inspector = inspect(bind)

    if "payroll_drafts" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("payroll_drafts")}
        if "company_id" in cols and "owner_user_id" not in cols:
            with op.batch_alter_table("payroll_drafts", schema=None) as batch_op:
                batch_op.alter_column("company_id", new_column_name="owner_user_id")

    if "automation_readiness" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("automation_readiness")}
        if "company_id" in cols and "user_id" not in cols:
            with op.batch_alter_table("automation_readiness", schema=None) as batch_op:
                batch_op.alter_column("company_id", new_column_name="user_id")


def downgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    inspector = inspect(bind)

    if "automation_readiness" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("automation_readiness")}
        if "user_id" in cols and "company_id" not in cols:
            with op.batch_alter_table("automation_readiness", schema=None) as batch_op:
                batch_op.alter_column("user_id", new_column_name="company_id")

    if "payroll_drafts" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("payroll_drafts")}
        if "owner_user_id" in cols and "company_id" not in cols:
            with op.batch_alter_table("payroll_drafts", schema=None) as batch_op:
                batch_op.alter_column("owner_user_id", new_column_name="company_id")
