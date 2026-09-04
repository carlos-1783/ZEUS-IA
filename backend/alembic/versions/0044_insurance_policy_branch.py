"""insurance_policies.branch — ramos de Mati (piloto Catalana Occidente)

Piloto real con una agente exclusiva de Catalana Occidente (feature/ramos-
seguros-mati, sobre feature/vertical-seguros): añade el ramo de la póliza
como columna real con un enum de 6 valores (hogar, comunidad, coche, vida,
decesos, salud). No se añade columna de aseguradora emisora — Mati solo
vende productos de una compañía, así que no aplica en este piloto.

No se necesita ninguna columna nueva para los campos específicos de
Coche/Vida/Salud (matrícula/conductor/marca-modelo; beneficiario/capital
asegurado; nº asegurados/cuadro médico): se guardan dentro de la columna
JSON ya existente `insured_risk`, que ya es libre por diseño (ver
0043_insurance_policies_claims.py / app/models/insurance.py). Tampoco se
necesita ninguna migración de esquema para el DNI/NIF del cliente: se
reutiliza `customers.tax_id`, ya existente desde 0001_initial_migration.py.

Se añade con `server_default='hogar'` para que `ALTER TABLE ... ADD COLUMN
... NOT NULL` no falle si la tabla ya tuviera filas (no las hay en este
piloto, pero es la forma correcta de añadir una columna NOT NULL sin
downtime); el valor por defecto no se usa nunca en la práctica porque la
API siempre exige `branch` explícito en la creación de la póliza
(InsurancePolicyCreate.branch es obligatorio, sin default).

Revision ID: 0044
Revises: 0043
"""
from alembic import op
import sqlalchemy as sa

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None

_BRANCH_VALUES = ("hogar", "comunidad", "coche", "vida", "decesos", "salud")


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    columns = {c["name"] for c in inspect(bind).get_columns("insurance_policies")}
    if "branch" in columns:
        return

    op.add_column(
        "insurance_policies",
        sa.Column(
            "branch",
            sa.Enum(*_BRANCH_VALUES, name="insurance_policy_branch"),
            nullable=False,
            server_default="hogar",
        ),
    )
    op.create_index("ix_insurance_policies_branch", "insurance_policies", ["branch"])

    # El server_default solo existía para poder añadir la columna NOT NULL
    # sin downtime; se retira tras el backfill implícito (no hay filas en
    # este piloto) para que la API sea la única fuente de verdad del valor.
    if _is_postgres():
        op.alter_column("insurance_policies", "branch", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_insurance_policies_branch", table_name="insurance_policies")
    op.drop_column("insurance_policies", "branch")
    if _is_postgres():
        op.execute("DROP TYPE IF EXISTS insurance_policy_branch")
