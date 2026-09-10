"""users.role y user_companies.role: de texto libre a valores controlados

Hallazgo de la auditoría feature/auditoria-real-nucleo (capa BD): no existía
ninguna tabla ni restricción de rol, solo columnas String libres. Se
confirmó por grep exhaustivo de todo el código (app/, services/ y también
tests/, que reveló un tercer valor real no documentado) que los valores que
se escriben realmente son:
- users.role: 'owner' | 'employee' (validado explícitamente en
  app/api/v1/endpoints/admin.py antes de cualquier escritura).
- user_companies.role: 'company_admin' | 'member' en código de producción,
  más 'owner' usado de forma consistente en 9 suites de tests
  (tests/test_zeus_*.py, test_afrodita_real_execution_v1.py,
  test_thalos_safe_v1.py, test_thalos_workspace_writer_v1.py,
  test_time_cost_engine_v1.py) — se incluye como valor válido en vez de
  romper esos tests.

Antes de aplicar el CHECK constraint, se normalizan defensivamente filas con
valores NULL o fuera de ese conjunto (no debería haber ninguna en datos
reales, pero la migración no debe poder fallar ni perder cuentas si las
hubiera) a los valores por defecto del modelo ('owner' / 'company_admin').

Usa batch_alter_table para ser segura tanto en SQLite (que requiere recrear
la tabla para añadir un CHECK) como en Postgres (donde batch mode ejecuta un
ALTER TABLE normal sin recrear nada).

Revision ID: 0044
Revises: 0043
"""
from alembic import op
import sqlalchemy as sa

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    inspector = inspect(bind)

    if "users" in inspector.get_table_names():
        # Normalización defensiva: nunca debe fallar la migración por datos existentes.
        bind.execute(
            sa.text(
                "UPDATE users SET role = 'owner' WHERE role IS NULL OR role NOT IN ('owner', 'employee')"
            )
        )
        existing_ck = {c["name"] for c in inspector.get_check_constraints("users")}
        if "ck_users_role" not in existing_ck:
            with op.batch_alter_table("users", schema=None) as batch_op:
                batch_op.create_check_constraint(
                    "ck_users_role", "role IN ('owner', 'employee')"
                )

    if "user_companies" in inspector.get_table_names():
        bind.execute(
            sa.text(
                "UPDATE user_companies SET role = 'company_admin' "
                "WHERE role IS NULL OR role NOT IN ('company_admin', 'member', 'owner')"
            )
        )
        existing_ck = {c["name"] for c in inspector.get_check_constraints("user_companies")}
        if "ck_user_companies_role" not in existing_ck:
            with op.batch_alter_table("user_companies", schema=None) as batch_op:
                batch_op.create_check_constraint(
                    "ck_user_companies_role", "role IN ('company_admin', 'member', 'owner')"
                )


def downgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    inspector = inspect(bind)

    if "user_companies" in inspector.get_table_names():
        existing_ck = {c["name"] for c in inspector.get_check_constraints("user_companies")}
        if "ck_user_companies_role" in existing_ck:
            with op.batch_alter_table("user_companies", schema=None) as batch_op:
                batch_op.drop_constraint("ck_user_companies_role", type_="check")

    if "users" in inspector.get_table_names():
        existing_ck = {c["name"] for c in inspector.get_check_constraints("users")}
        if "ck_users_role" in existing_ck:
            with op.batch_alter_table("users", schema=None) as batch_op:
                batch_op.drop_constraint("ck_users_role", type_="check")
