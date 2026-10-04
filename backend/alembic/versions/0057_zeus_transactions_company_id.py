"""zeus_transactions: añadir company_id (tenant owner)

Hallazgo N2 (confirmado por dos auditorías independientes): GET
/zeus/transactions/{id} y POST /zeus/transactions/{id}/execute no
comprobaban que la transacción perteneciera a la empresa del usuario
autenticado -- `zeus_transactions` no tenía ninguna columna de tenant, así
que el filtrado era imposible sin esta migración. Mismo patrón que
`0052_thalos_tables_company_id.py` y `0043_agent_activities_company_id.py`:
columna nullable + índice + FK solo en dialectos que la soportan de verdad
(no en SQLite) + backfill best-effort.

## Backfill -- señal usada

`context_json` guarda siempre `user_id` (string) desde que
`create_transaction` lo fija server-side (services/zeus_transaction_system_v1.py).
Se parsea ese JSON en Python (no hay JSON funtions portables entre SQLite y
Postgres en este repo) y se resuelve `user_id -> user_companies.company_id`
(primera empresa del usuario, mismo criterio que
`crm_office_service.primary_company_id`). Las filas cuyo `context_json` no
tiene `user_id` resoluble, o cuyo usuario no tiene ninguna empresa vinculada,
quedan `company_id IS NULL` de forma honesta -- el control de acceso de
aplicación cae de vuelta al propio `user_id` embebido en `context_json` para
esas filas (ver `_assert_transaction_access` en
`services/zeus_transaction_system_v1.py`).

Revision ID: 0057
Revises: 0056
"""
from __future__ import annotations

import json
from typing import Optional

from alembic import op
import sqlalchemy as sa

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None


def _resolve_primary_company(connection, user_id: Optional[str]) -> Optional[int]:
    if not user_id:
        return None
    row = connection.execute(
        sa.text(
            """
            SELECT company_id FROM user_companies
            WHERE user_id = :user_id
            ORDER BY id ASC LIMIT 1
            """
        ),
        {"user_id": int(user_id)},
    ).fetchone()
    return row[0] if row else None


def upgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    inspector = inspect(bind)
    if "zeus_transactions" not in inspector.get_table_names():
        return

    cols = {c["name"] for c in inspector.get_columns("zeus_transactions")}
    if "company_id" not in cols:
        op.add_column("zeus_transactions", sa.Column("company_id", sa.Integer(), nullable=True))
        op.create_index(
            "ix_zeus_transactions_company_id", "zeus_transactions", ["company_id"], unique=False
        )
        if bind.dialect.name != "sqlite":
            op.create_foreign_key(
                "fk_zeus_transactions_company_id",
                "zeus_transactions",
                "companies",
                ["company_id"],
                ["id"],
                ondelete="SET NULL",
            )

    connection = bind
    rows = connection.execute(
        sa.text("SELECT id, context_json FROM zeus_transactions WHERE company_id IS NULL")
    ).fetchall()
    for row_id, context_json in rows:
        if not context_json:
            continue
        try:
            ctx = json.loads(context_json)
        except (TypeError, ValueError):
            continue
        if not isinstance(ctx, dict):
            continue
        user_id = ctx.get("user_id")
        company_id = _resolve_primary_company(connection, user_id)
        if company_id:
            connection.execute(
                sa.text("UPDATE zeus_transactions SET company_id = :cid WHERE id = :id"),
                {"cid": company_id, "id": row_id},
            )


def downgrade() -> None:
    from sqlalchemy import inspect

    bind = op.get_bind()
    inspector = inspect(bind)
    if "zeus_transactions" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("zeus_transactions")}
    if "company_id" in cols:
        if bind.dialect.name != "sqlite":
            op.drop_constraint("fk_zeus_transactions_company_id", "zeus_transactions", type_="foreignkey")
        op.drop_index("ix_zeus_transactions_company_id", table_name="zeus_transactions")
        op.drop_column("zeus_transactions", "company_id")
