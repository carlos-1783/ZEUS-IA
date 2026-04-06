"""ZEUS_MULTITENANT_MIGRATION_SAFE_001: company_id on tpv_products, tpv_sales, invoices

Revision ID: 0012
Revises: 0011
Create Date: 2026-04-01

"""
from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def _exec(connection, sql: str, params=None):
    connection.execute(text(sql), params or {})


def _backfill_orphan_owners(connection, table: str, user_col: str) -> None:
    """Create minimal company + user_companies for owners with rows still missing company_id."""
    rows = connection.execute(
        text(
            f"""
            SELECT DISTINCT t.{user_col} AS uid
            FROM {table} t
            WHERE t.company_id IS NULL
              AND t.{user_col} IS NOT NULL
              AND NOT EXISTS (
                SELECT 1 FROM user_companies uc WHERE uc.user_id = t.{user_col}
              )
            """
        )
    ).fetchall()
    meta = json.dumps({"source": "0012_migration_auto_company"})
    for (uid,) in rows:
        if uid is None:
            continue
        urow = connection.execute(
            text(
                "SELECT email, COALESCE(company_name, '') FROM users WHERE id = :uid"
            ),
            {"uid": uid},
        ).fetchone()
        if not urow:
            continue
        email, cn = urow[0] or "", (urow[1] or "").strip()
        label = (cn or email or f"user-{uid}")[:255]
        slug = f"u{int(uid)}-mig-tpv"[:100]
        # Slug collision: append suffix
        for suf in ("", "-2", "-3", "-4", "-5"):
            try_slug = (slug[: 100 - len(suf)] + suf) if suf else slug
            exists = connection.execute(
                text("SELECT 1 FROM companies WHERE slug = :s LIMIT 1"),
                {"s": try_slug},
            ).first()
            if not exists:
                slug = try_slug
                break
        cid = connection.execute(
            text(
                """
                INSERT INTO companies (company_name, slug, pilot_company, status, country, currency, metadata, created_at)
                VALUES (:name, :slug, 0, 'active', 'ES', 'EUR', :meta, CURRENT_TIMESTAMP)
                RETURNING id
                """
            ),
            {"name": label, "slug": slug, "meta": meta},
        ).scalar()
        if cid is None:
            continue
        connection.execute(
            text(
                """
                INSERT INTO user_companies (user_id, company_id, role, created_at)
                VALUES (:uid, :cid, 'company_admin', CURRENT_TIMESTAMP)
                """
            ),
            {"uid": uid, "cid": cid},
        )


def upgrade() -> None:
    op.add_column(
        "tpv_products",
        sa.Column("company_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_tpv_products_company_id"), "tpv_products", ["company_id"], unique=False
    )
    op.create_foreign_key(
        "fk_tpv_products_company_id",
        "tpv_products",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "tpv_sales",
        sa.Column("company_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_tpv_sales_company_id"), "tpv_sales", ["company_id"], unique=False
    )
    op.create_foreign_key(
        "fk_tpv_sales_company_id",
        "tpv_sales",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "invoices",
        sa.Column("company_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_invoices_company_id"), "invoices", ["company_id"], unique=False
    )
    op.create_foreign_key(
        "fk_invoices_company_id",
        "invoices",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="SET NULL",
    )

    connection = op.get_bind()

    _exec(
        connection,
        """
        UPDATE tpv_products SET company_id = (
            SELECT uc.company_id FROM user_companies uc
            WHERE uc.user_id = tpv_products.user_id
            ORDER BY uc.id ASC LIMIT 1
        ) WHERE company_id IS NULL
        """,
    )

    _exec(
        connection,
        """
        UPDATE tpv_products SET company_id = (
            SELECT c.id FROM companies c
            WHERE (LOWER(c.slug) LIKE '%circo%' OR LOWER(c.company_name) LIKE '%circo%')
            ORDER BY c.id ASC LIMIT 1
        )
        WHERE EXISTS (
            SELECT 1 FROM companies c2
            WHERE LOWER(c2.slug) LIKE '%circo%' OR LOWER(c2.company_name) LIKE '%circo%'
        )
        AND user_id IN (
            SELECT u.id FROM users u
            WHERE LOWER(COALESCE(u.email, '')) LIKE '%marketing%'
               OR LOWER(COALESCE(u.full_name, '')) LIKE '%marketing%'
        )
        """,
    )

    _backfill_orphan_owners(connection, "tpv_products", "user_id")
    _exec(
        connection,
        """
        UPDATE tpv_products SET company_id = (
            SELECT uc.company_id FROM user_companies uc
            WHERE uc.user_id = tpv_products.user_id
            ORDER BY uc.id ASC LIMIT 1
        ) WHERE company_id IS NULL
        """,
    )

    _exec(
        connection,
        """
        UPDATE tpv_sales SET company_id = (
            SELECT uc.company_id FROM user_companies uc
            WHERE uc.user_id = tpv_sales.user_id
            ORDER BY uc.id ASC LIMIT 1
        ) WHERE company_id IS NULL
        """,
    )
    _backfill_orphan_owners(connection, "tpv_sales", "user_id")
    _exec(
        connection,
        """
        UPDATE tpv_sales SET company_id = (
            SELECT uc.company_id FROM user_companies uc
            WHERE uc.user_id = tpv_sales.user_id
            ORDER BY uc.id ASC LIMIT 1
        ) WHERE company_id IS NULL
        """,
    )

    _exec(
        connection,
        """
        UPDATE invoices SET company_id = (
            SELECT uc.company_id FROM user_companies uc
            WHERE uc.user_id = invoices.created_by
            ORDER BY uc.id ASC LIMIT 1
        ) WHERE company_id IS NULL AND created_by IS NOT NULL
        """,
    )
    _backfill_orphan_owners(connection, "invoices", "created_by")
    _exec(
        connection,
        """
        UPDATE invoices SET company_id = (
            SELECT uc.company_id FROM user_companies uc
            WHERE uc.user_id = invoices.created_by
            ORDER BY uc.id ASC LIMIT 1
        ) WHERE company_id IS NULL AND created_by IS NOT NULL
        """,
    )


def downgrade() -> None:
    op.drop_constraint("fk_invoices_company_id", "invoices", type_="foreignkey")
    op.drop_index(op.f("ix_invoices_company_id"), table_name="invoices")
    op.drop_column("invoices", "company_id")

    op.drop_constraint("fk_tpv_sales_company_id", "tpv_sales", type_="foreignkey")
    op.drop_index(op.f("ix_tpv_sales_company_id"), table_name="tpv_sales")
    op.drop_column("tpv_sales", "company_id")

    op.drop_constraint("fk_tpv_products_company_id", "tpv_products", type_="foreignkey")
    op.drop_index(op.f("ix_tpv_products_company_id"), table_name="tpv_products")
    op.drop_column("tpv_products", "company_id")
