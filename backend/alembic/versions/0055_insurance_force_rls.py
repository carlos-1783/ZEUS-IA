"""insurance_policies / insurance_claims — FORCE ROW LEVEL SECURITY

0043_insurance_policies_claims.py ya activó RLS real (`ENABLE ROW LEVEL
SECURITY` + policy `USING (...)` fail-closed) para ambas tablas, pero no
incluía `FORCE ROW LEVEL SECURITY`. Sin `FORCE`, Postgres exime de la
política RLS al propietario de la tabla (el rol con el que normalmente
corre Alembic/las migraciones) — solo los roles NO propietarios (como
`zeus_app`, creado en 0043 sin privilegios de superusuario) quedaban
protegidos. Este es el mismo patrón ya establecido en el núcleo para el
resto de tablas multi-tenant (ver, solo para consulta, no copiado literal,
`feature/multi-tenant-bd:backend/alembic/versions/...`: `ENABLE ROW LEVEL
SECURITY` + `FORCE ROW LEVEL SECURITY` en `invoices`, `agent_activities`,
`companies`, `users`).

Solo PostgreSQL: no-op completo en SQLite (`_is_postgres()`), igual que el
resto del bloque RLS de 0043.

Revision ID: 0045
Revises: 0044
"""
from alembic import op

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if not _is_postgres():
        return
    op.execute("ALTER TABLE insurance_policies FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE insurance_claims FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    if not _is_postgres():
        return
    op.execute("ALTER TABLE insurance_policies NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE insurance_claims NO FORCE ROW LEVEL SECURITY")
