"""ops_routes.distance admite NULL (distancia no calculada)

Revision ID: 0064
Revises: 0063
Create Date: 2026-10-12

Fase 2 / Step 2 (sin simulacion): AFRODITA guardaba en ops_routes.distance una distancia
inventada (8/32 km + 4,2 km por parada) porque el optimizador de rutas era un stub. Sin
servicio de rutas integrado, la distancia pasa a NULL = "no calculada".

Solo relaja la restriccion NOT NULL: no modifica filas. Las rutas antiguas conservan su
valor (inventado); si se quieren limpiar, es una decision aparte:
    UPDATE ops_routes SET distance = NULL;   -- no se ejecuta aqui

Rollback: `alembic downgrade 0063` pone a 0 los NULL y restaura NOT NULL.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0064"
down_revision = "0063"
branch_labels = None
depends_on = None

_TABLE = "ops_routes"


def _distance_nullable() -> bool | None:
    insp = inspect(op.get_bind())
    if _TABLE not in insp.get_table_names():
        return None
    for col in insp.get_columns(_TABLE):
        if col["name"] == "distance":
            return bool(col["nullable"])
    return None


def upgrade() -> None:
    if _distance_nullable() is False:
        with op.batch_alter_table(_TABLE) as batch:
            batch.alter_column("distance", existing_type=sa.Float(), nullable=True)


def downgrade() -> None:
    if _distance_nullable() is True:
        op.execute(sa.text("UPDATE ops_routes SET distance = 0 WHERE distance IS NULL"))
        with op.batch_alter_table(_TABLE) as batch:
            batch.alter_column("distance", existing_type=sa.Float(), nullable=False)
