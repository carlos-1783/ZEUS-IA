"""DB hardening phase 2 — triggers adicionales zeus_phase_2

Revision ID: 0032
Revises: 0031
"""
from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(
        """
        CREATE OR REPLACE FUNCTION zeus_prevent_superuser_delete()
        RETURNS TRIGGER AS $$
        BEGIN
          IF OLD.is_superuser = true OR OLD.role = 'superuser' THEN
            RAISE EXCEPTION 'zeus_guard: cannot delete superuser';
          END IF;
          RETURN OLD;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_zeus_superuser_delete ON users;")
    op.execute(
        """
        CREATE TRIGGER trg_zeus_superuser_delete
        BEFORE DELETE ON users
        FOR EACH ROW EXECUTE PROCEDURE zeus_prevent_superuser_delete();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION zeus_prevent_superuser_role_escalation()
        RETURNS TRIGGER AS $$
        BEGIN
          IF NEW.is_superuser = true AND (OLD.is_superuser IS DISTINCT FROM true) THEN
            RAISE EXCEPTION 'zeus_guard: cannot escalate to superuser via update';
          END IF;
          IF NEW.role = 'superuser' AND (OLD.role IS DISTINCT FROM 'superuser') THEN
            RAISE EXCEPTION 'zeus_guard: cannot set role superuser via update';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_zeus_superuser_escalation ON users;")
    op.execute(
        """
        CREATE TRIGGER trg_zeus_superuser_escalation
        BEFORE UPDATE OF is_superuser, role ON users
        FOR EACH ROW EXECUTE PROCEDURE zeus_prevent_superuser_role_escalation();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION zeus_cashflow_company_required()
        RETURNS TRIGGER AS $$
        BEGIN
          IF NEW.company_id IS NULL THEN
            RAISE EXCEPTION 'zeus_guard: cashflow_ledger requires company_id';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_zeus_cashflow_company ON cashflow_ledger;")
    op.execute(
        """
        CREATE TRIGGER trg_zeus_cashflow_company
        BEFORE INSERT OR UPDATE ON cashflow_ledger
        FOR EACH ROW EXECUTE PROCEDURE zeus_cashflow_company_required();
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP TRIGGER IF EXISTS trg_zeus_cashflow_company ON cashflow_ledger;")
    op.execute("DROP FUNCTION IF EXISTS zeus_cashflow_company_required();")
    op.execute("DROP TRIGGER IF EXISTS trg_zeus_superuser_escalation ON users;")
    op.execute("DROP FUNCTION IF EXISTS zeus_prevent_superuser_role_escalation();")
    op.execute("DROP TRIGGER IF EXISTS trg_zeus_superuser_delete ON users;")
    op.execute("DROP FUNCTION IF EXISTS zeus_prevent_superuser_delete();")
