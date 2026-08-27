"""Row Level Security (PostgreSQL) para tablas con datos por tenant

Hallazgo de la auditoría feature/auditoria-real-nucleo + petición explícita
del bloque de cierre multi-tenant: el aislamiento entre empresas dependía
por completo de que cada endpoint recordara filtrar por company_id. Esta
migración añade una segunda capa de protección real a nivel de PostgreSQL
que no depende de que el código de la aplicación acierte siempre.

Solo se ejecuta en PostgreSQL — es un no-op completo en SQLite (RLS no
existe ahí; local/tests siguen exactamente igual). Ver
app/db/tenant_context.py para cómo la aplicación establece el contexto de
sesión que estas policies leen.

## Diseño: "fail-open cuando no hay contexto"

Cada policy dice, en esencia: "si nadie estableció el contexto de tenant
para esta transacción, deja ver todo (igual que antes de esta migración); si
SÍ se estableció, filtra de verdad". Esto es deliberado y crítico: significa
que activar RLS no puede romper NINGUNA query existente que no haya sido
migrada explícitamente a `get_db_scoped()` (workers de fondo, scripts,
Alembic mismo, endpoints todavía sin tocar). Da protección real solo donde
la aplicación ya se lo pide explícitamente, y dejarlo así de conservador es
la única forma responsable de activarlo sin poder probarlo contra un
PostgreSQL real en esta sesión (no había Postgres/Docker disponible en el
entorno de desarrollo local — SOLO SQLite). Ver AUDIT_FIX_BLOQUE2.md para
el detalle de qué se verificó y qué queda pendiente de probar en staging
antes de confiar en esto para la demo de septiembre.

## Tablas cubiertas y su policy

- invoices / agent_activities: tienen company_id propio (Integer). Visible
  si no hay contexto, o company_id coincide con el contexto, o company_id es
  NULL y la fila es del usuario actual (created_by / user_email) — mismo
  criterio "legacy" que ya usan los filtros a nivel de aplicación.
- companies: una fila es la propia empresa/tenant. Visible si no hay
  contexto, si su id coincide con el contexto, o si el usuario actual
  pertenece a ella (vía user_companies).
- users: no tiene company_id propio (relación N:M vía user_companies).
  Visible si no hay contexto, si es la propia fila del usuario, o si
  comparte alguna empresa con el usuario actual (colegas del mismo tenant).

Revision ID: 0047
Revises: 0046
"""
from alembic import op

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def _is_postgres() -> bool:
    bind = op.get_bind()
    return bind.dialect.name == "postgresql"


def upgrade() -> None:
    if not _is_postgres():
        return

    # --- invoices ---
    op.execute("ALTER TABLE invoices ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE invoices FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_invoices ON invoices
        USING (
            NULLIF(current_setting('app.current_company_id', true), '') IS NULL
            OR company_id::text = current_setting('app.current_company_id', true)
            OR (
                company_id IS NULL
                AND created_by::text = NULLIF(current_setting('app.current_user_id', true), '')
            )
        )
        """
    )

    # --- agent_activities ---
    op.execute("ALTER TABLE agent_activities ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE agent_activities FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_agent_activities ON agent_activities
        USING (
            NULLIF(current_setting('app.current_company_id', true), '') IS NULL
            OR company_id::text = current_setting('app.current_company_id', true)
            OR (
                company_id IS NULL
                AND user_email = NULLIF(current_setting('app.current_user_email', true), '')
            )
        )
        """
    )

    # --- companies ---
    op.execute("ALTER TABLE companies ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE companies FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_companies ON companies
        USING (
            NULLIF(current_setting('app.current_company_id', true), '') IS NULL
            OR id::text = current_setting('app.current_company_id', true)
            OR EXISTS (
                SELECT 1 FROM user_companies uc
                WHERE uc.company_id = companies.id
                  AND uc.user_id::text = NULLIF(current_setting('app.current_user_id', true), '')
            )
        )
        """
    )

    # --- users ---
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_users ON users
        USING (
            NULLIF(current_setting('app.current_user_id', true), '') IS NULL
            OR id::text = current_setting('app.current_user_id', true)
            OR EXISTS (
                SELECT 1 FROM user_companies uc1
                JOIN user_companies uc2 ON uc1.company_id = uc2.company_id
                WHERE uc1.user_id = users.id
                  AND uc2.user_id::text = NULLIF(current_setting('app.current_user_id', true), '')
            )
        )
        """
    )


def downgrade() -> None:
    if not _is_postgres():
        return

    op.execute("DROP POLICY IF EXISTS tenant_isolation_users ON users")
    op.execute("ALTER TABLE users NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")

    op.execute("DROP POLICY IF EXISTS tenant_isolation_companies ON companies")
    op.execute("ALTER TABLE companies NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE companies DISABLE ROW LEVEL SECURITY")

    op.execute("DROP POLICY IF EXISTS tenant_isolation_agent_activities ON agent_activities")
    op.execute("ALTER TABLE agent_activities NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE agent_activities DISABLE ROW LEVEL SECURITY")

    op.execute("DROP POLICY IF EXISTS tenant_isolation_invoices ON invoices")
    op.execute("ALTER TABLE invoices NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE invoices DISABLE ROW LEVEL SECURITY")
